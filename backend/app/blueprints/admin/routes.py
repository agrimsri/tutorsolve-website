from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request, get_jwt
from datetime import datetime
from bson import ObjectId
import re

from app.blueprints.admin import admin_bp
from app.extensions import get_db
from app.utils.decorators import admin_required, role_required
from app.utils.helpers import oid, to_str_id
from app.services.diamond_engine import set_price_quote, assign_expert
from app.utils.constants import Role
from app.utils.currency import normalize_currency, money_label


def _to_object_id(raw_id):
    if isinstance(raw_id, ObjectId):
        return raw_id
    if not raw_id:
        return None
    return oid(raw_id)


def _get_domain_name_map(db, domain_ids):
    domain_oids = []
    for domain_id in domain_ids:
        domain_oid = _to_object_id(domain_id)
        if domain_oid:
            domain_oids.append(domain_oid)

    if not domain_oids:
        return {}

    domain_docs = list(db.domains.find({"_id": {"$in": list(set(domain_oids))}}, {"name": 1}))
    return {d["_id"]: d.get("name") for d in domain_docs if d.get("name")}


def _resolve_domain_name(db, domain_id=None, fallback_name=None, domain_name_map=None):
    domain_name = fallback_name if fallback_name else "Unknown"
    domain_oid = _to_object_id(domain_id)
    if not domain_oid:
        return domain_name

    if domain_name_map and domain_oid in domain_name_map:
        return domain_name_map[domain_oid]

    domain_doc = db.domains.find_one({"_id": domain_oid}, {"name": 1})
    if domain_doc and domain_doc.get("name"):
        return domain_doc["name"]

    return domain_name


def _super_admin_display_name(user_doc):
    if not user_doc:
        return "Super Admin"
    return (
        user_doc.get("name")
        or ((user_doc.get("email") or "").split("@")[0] if user_doc.get("email") else None)
        or "Super Admin"
    )


def _resolve_super_admin_user_id(db):
    role_query = {"$in": ["super_admin", "superadmin", "super-admin", "super admin"]}

    sa_user = db.users.find_one(
        {
            "role": role_query,
            "is_active": {"$ne": False},
            "is_banned": {"$ne": True},
        },
        sort=[("created_at", 1), ("_id", 1)],
    )
    if sa_user:
        return sa_user["_id"]

    fallback_user = db.users.find_one(
        {"role": role_query},
        sort=[("created_at", 1), ("_id", 1)],
    )
    return fallback_user["_id"] if fallback_user else None


def _ensure_super_admin_chat_thread_for_employee(db, employee_doc):
    thread = db.threads.find_one(
        {"thread_type": "F", "employee_id": employee_doc["_id"]},
        sort=[("updated_at", -1), ("created_at", -1)],
    )
    if thread:
        if not thread.get("super_admin_user_id"):
            super_admin_user_id = _resolve_super_admin_user_id(db)
            if super_admin_user_id:
                now = datetime.utcnow()
                db.threads.update_one(
                    {"_id": thread["_id"]},
                    {
                        "$set": {
                            "super_admin_user_id": super_admin_user_id,
                            "super_admin_last_read_at": now,
                        }
                    },
                )
                thread["super_admin_user_id"] = super_admin_user_id
                thread["super_admin_last_read_at"] = now
        return thread

    now = datetime.utcnow()
    super_admin_user_id = _resolve_super_admin_user_id(db)
    if not super_admin_user_id:
        return None

    insert_payload = {
        "question_id": None,
        "thread_type": "F",
        "student_id": None,
        "expert_id": None,
        "employee_id": employee_doc["_id"],
        "super_admin_user_id": super_admin_user_id,
        "created_at": now,
        "updated_at": now,
        "employee_last_read_at": None,
        "super_admin_last_read_at": now,
    }
    thread_id = db.threads.insert_one(insert_payload).inserted_id
    return db.threads.find_one({"_id": thread_id})


def _get_last_thread_message(db, thread):
    if not thread:
        return None
    return db.messages.find_one(
        {"thread_id": thread["_id"]},
        sort=[("created_at", -1)],
    )


def _count_employee_unread_messages(db, thread, employee_user_oid):
    if not thread:
        return 0

    query = {
        "thread_id": thread["_id"],
        "sender_user_id": {"$ne": employee_user_oid},
    }
    read_cutoff = thread.get("employee_last_read_at")
    if read_cutoff:
        query["created_at"] = {"$gt": read_cutoff}

    return db.messages.count_documents(query)


@admin_bp.route("/orders", methods=["GET"])
@admin_required
def orders():
    db     = get_db()
    status         = request.args.get("status")
    payment_status = request.args.get("payment_status")

    query = {}
    
    uid = get_jwt_identity()
    employee = db.employees.find_one({"user_id": oid(uid)})
    emp_id = employee["_id"] if employee else None
    
    # Filter: Show only orders assigned to this employee, OR unassigned ones so they can pick them up
    query["$or"] = [
        {"assigned_employee_id": emp_id},
        {"assigned_employee_id": {"$in": [None, ""]}},
        {"assigned_employee_id": {"$exists": False}}
    ]

    if status:
        if "," in status:
            query["status"] = {"$in": status.split(",")}
        else:
            query["status"] = status
    
    if payment_status == "advance_paid":
        # Find all questions that have a confirmed advance payment
        paid_payments = list(db.payments.find({"advance_paid": True}, {"question_id": 1}))
        paid_qids = [p["question_id"] for p in paid_payments]
        query["_id"] = {"$in": paid_qids}

    questions = list(db.questions.find(query).sort("created_at", -1).limit(100))
    result    = []

    domain_name_map = _get_domain_name_map(db, [q.get("domain_id") for q in questions])

    for q in questions:
        has_thread_a = db.threads.count_documents({
            "question_id": q["_id"],
            "thread_type": "A"
        }, limit=1) > 0

        result.append({
            "_id":            str(q["_id"]),
            "title":          q["title"],
            "domain":         _resolve_domain_name(
                db,
                domain_id=q.get("domain_id"),
                fallback_name=q.get("domain"),
                domain_name_map=domain_name_map
            ),
            "status":         q["status"],
            "student_price":  q.get("student_price"),
            "student_currency": q.get("student_currency", "inr"),
            "expert_currency": q.get("expert_currency", "inr"),
            "price_approved": q.get("price_approved", False),
            "has_thread_a":   has_thread_a,
            "assigned_employee_id": str(q["assigned_employee_id"]) if q.get("assigned_employee_id") else None,
            "assigned_expert_id": str(q["assigned_expert_id"]) if q.get("assigned_expert_id") else None,
            "created_at":     str(q["created_at"]),
        })

    return jsonify(result), 200


@admin_bp.route("/orders/<question_id>/quote", methods=["POST"])
@admin_required
def set_quote(question_id):
    data = request.get_json() or {}
    db   = get_db()
    uid  = get_jwt_identity()
    
    employee = db.employees.find_one({"user_id": oid(uid)})
    question = db.questions.find_one({"_id": oid(question_id)})

    if not question:
        return jsonify({"error": "Question not found"}), 404
    
    if not employee:
        return jsonify({"error": "Employee record not found"}), 404

    # Verification: Must be the assigned employee
    if str(question.get("assigned_employee_id")) != str(employee["_id"]):
        return jsonify({"error": "You must claim this question before setting a price."}), 403

    from app.utils.constants import OrderStatus
    if question["status"] not in (OrderStatus.AWAITING_QUOTE, OrderStatus.PENDING_PAYMENT):
        return jsonify({"error": f"Cannot edit price in current status: {question['status']}"}), 400

    is_update = (question["status"] == OrderStatus.PENDING_PAYMENT)

    try:
        student_price = float(data.get("student_price"))
        expert_payout = float(data.get("expert_payout"))
        student_currency = normalize_currency(data.get("student_currency") or question.get("student_currency"))
        expert_currency = normalize_currency(data.get("expert_currency") or question.get("expert_currency"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid prices and supported currencies are required."}), 400

    if student_price <= 0 or expert_payout <= 0:
        return jsonify({"error": "Both prices must be greater than zero."}), 400

    from app.services.diamond_engine import set_price_quote
    set_price_quote(question_id, student_price, expert_payout, student_currency, expert_currency)
    
    # Auto-approve the price (replaces Maker-Checker flow)
    from app.services.diamond_engine import approve_price
    approve_price(question_id)

    # Sync with payments record
    from app.services.payment_service import ensure_payment_record
    ensure_payment_record(question_id, student_price, question["student_id"])

    from app.services.email_service import send_price_quote_email

    old_student_price = question.get("student_price")
    old_expert_payout = question.get("expert_payout")
    old_student_currency = normalize_currency(question.get("student_currency"))
    old_expert_currency = normalize_currency(question.get("expert_currency"))
    student_price_changed = (
        old_student_price is None
        or round(float(old_student_price or 0), 2) != round(student_price, 2)
        or old_student_currency != student_currency
    )
    expert_price_changed = (
        old_expert_payout is None
        or round(float(old_expert_payout or 0), 2) != round(expert_payout, 2)
        or old_expert_currency != expert_currency
    )

    def insert_thread_message(thread_type, body):
        thread = db.threads.find_one({
            "question_id": oid(question_id),
            "thread_type": thread_type
        })
        if not thread or not employee:
            return

        now = datetime.utcnow()
        db.messages.insert_one({
            "thread_id":      thread["_id"],
            "sender_user_id": employee["user_id"],
            "body":           body,
            "created_at":     now
        })
        try:
            from app.extensions import socketio
            _tid = str(thread["_id"])
            _payload = {
                "thread_id":      _tid,
                "sender_user_id": str(employee["user_id"]),
                "sender_role":    "employee",
                "body":           body,
                "created_at":     now.isoformat(),
            }
            socketio.start_background_task(
                lambda: socketio.emit("new_message", _payload, room=f"thread_{_tid}")
            )
        except Exception:
            pass

    student_total = money_label(student_price, student_currency)
    student_advance = money_label(student_price / 2, student_currency)
    student_completion = money_label(student_price - student_price / 2, student_currency)
    if (not is_update) or student_price_changed:
        msg_body = (
            f"We've reviewed your question and are pleased to offer you the following:\n\n"
            f"Total Price: {student_total}\n\n"
            f"Advance (50%): {student_advance}\n\n"
            f"Completion (50%): {student_completion}\n\n"
            f"Refresh to see the payment link."
        )
        if is_update:
            msg_body = (
                f"**Quote Updated!**\n\n"
                f"We have updated your quote for this order:\n"
                f"New Total Price: {student_total}\n"
                f"New Advance (50%): {student_advance}\n"
                f"New Completion (50%): {student_completion}\n\n"
                f"Refresh to see the payment link."
            )
        insert_thread_message("A", msg_body)

    if is_update and expert_price_changed and question.get("assigned_expert_id"):
        expert_body = (
            f"**Payout Updated**\n\n"
            f"The expert payout for this order has been updated to "
            f"{money_label(expert_payout, expert_currency)}."
        )
        insert_thread_message("B", expert_body)

    if (not is_update) or student_price_changed:
        student = db.students.find_one({"_id": question["student_id"]})
        if student:
            user = db.users.find_one({"_id": student["user_id"]})
            if user:
                send_price_quote_email(
                    user["email"],
                    student["name"],
                    question["title"],
                    student_price,
                    student_currency
                )
                from app.tasks.notification_tasks import send_notification_async
                print(f"[DEBUG] set_quote: Dispatching send_notification_async.delay to student user_id={user['_id']}")
                try:
                    send_notification_async.delay(
                        user_id=str(user["_id"]),
                        notif_type="quote_ready",
                        title="Your quote has been updated" if is_update else "Your quote is ready",
                        body=f"{student_total} — log in to check.",
                        link=f"/student/order-detail.html?id={question_id}"
                    )
                    print(f"[DEBUG] set_quote: send_notification_async.delay dispatched OK")
                except Exception as e:
                    print(f"[ERROR] set_quote: send_notification_async.delay FAILED: {e}")

    if is_update and expert_price_changed and question.get("assigned_expert_id"):
        expert = db.experts.find_one({"_id": question["assigned_expert_id"]})
        if expert:
            from app.tasks.notification_tasks import send_notification_async
            try:
                send_notification_async.delay(
                    user_id=str(expert["user_id"]),
                    notif_type="expert_payout_updated",
                    title="Payout updated",
                    body=f"Your payout for '{question['title']}' is now {money_label(expert_payout, expert_currency)}.",
                    link=f"/expert/task-detail.html?id={question_id}"
                )
            except Exception as e:
                print(f"[ERROR] set_quote: expert payout notification FAILED: {e}")

    return jsonify({"status": "quote_set_and_approved", "is_update": is_update}), 200


@admin_bp.route("/orders/<question_id>/start-negotiation", methods=["POST"])
@admin_required
def start_negotiation(question_id):
    """
    Creates Thread A (Student <-> Admin).
    Called when admin is ready to negotiate price with the student.
    Must happen BEFORE assignment.
    """
    uid      = get_jwt_identity()
    db       = get_db()

    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Question not found"}), 404

    # Handle existing Thread A (e.g. created automatically on posting)
    existing = db.threads.find_one({
        "question_id": oid(question_id),
        "thread_type": "A"
    })
    
    employee = db.employees.find_one({"user_id": oid(uid)})
    if not employee:
        return jsonify({"error": "Employee record not found"}), 404
    emp_id = employee["_id"]

    # Check if already assigned to someone else
    if question.get("assigned_employee_id") and str(question["assigned_employee_id"]) != str(emp_id):
        return jsonify({"error": "This order has already been claimed by another admin."}), 403

    if existing:
        # Just assign the employee if not already assigned
        if not existing.get("employee_id"):
            db.threads.update_one(
                {"_id": existing["_id"]},
                {"$set": {"employee_id": emp_id}}
            )
        
        # Also update question if not assigned
        if not question.get("assigned_employee_id"):
            db.questions.update_one(
                {"_id": oid(question_id)},
                {"$set": {"assigned_employee_id": emp_id}}
            )
            # Notify student
            from app.tasks.notification_tasks import send_notification_async
            student_profile = db.students.find_one({"_id": question["student_id"]})
            if student_profile:
                send_notification_async.delay(
                    user_id=str(student_profile["user_id"]),
                    notif_type="order_accepted",
                    title="Order Accepted",
                    body=f"Your question '{question['title']}' has been accepted by an admin. Check the dashboard for updates.",
                    link=f"/student/order-detail.html?id={str(question_id)}"
                )

        return jsonify({
            "thread_id": str(existing["_id"]),
            "message":   "Thread updated with admin"
        }), 200

    # Fallback to creating a new one if it somehow doesn't exist
    thread_id = db.threads.insert_one({
        "question_id": oid(question_id),
        "thread_type": "A",
        "student_id":  question["student_id"],
        "expert_id":   None,
        "employee_id": emp_id,
        "created_at":  datetime.utcnow()
    }).inserted_id

    # Mark which employee is handling this order
    db.questions.update_one(
        {"_id": oid(question_id)},
        {"$set": {"assigned_employee_id": emp_id}}
    )

    return jsonify({"thread_id": str(thread_id)}), 201


@admin_bp.route("/orders/<question_id>/assign", methods=["POST"])
@admin_required
def assign(question_id):
    """
    Assigns expert and creates Thread B (Expert <-> Admin).
    Thread A must already exist (via start-negotiation) before calling this.
    """
    uid  = get_jwt_identity()
    data = request.get_json()
    db   = get_db()
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Question not found"}), 404

    employee = db.employees.find_one({"user_id": oid(uid)})
    if not employee or str(question.get("assigned_employee_id")) != str(employee["_id"]):
        return jsonify({"error": "You must claim this question before assigning an expert."}), 403

    assign_expert(question_id, data["expert_id"])

    employee = db.employees.find_one({"user_id": oid(uid)})

    # Thread A is NOT created here — it's created via start-negotiation
    # Create Thread B — Expert <-> Admin only
    existing_b = db.threads.find_one({
        "question_id": oid(question_id),
        "thread_type": "B"
    })
    if not existing_b:
        print(f"[DEBUG] assign: Creating Thread B for question {question_id}")
        try:
            db.threads.insert_one({
                "question_id": oid(question_id),
                "thread_type": "B",
                "student_id":  None,                        # NEVER set on Thread B
                "expert_id":   oid(data["expert_id"]),
                "employee_id": employee["_id"] if employee else None,
                "created_at":  datetime.utcnow()
            })
            print(f"[DEBUG] assign: Thread B created OK")
        except Exception as e:
            print(f"[ERROR] assign: Thread B insert FAILED: {e}")
    else:
        print(f"[DEBUG] assign: Thread B already exists: {existing_b['_id']} (unexpected after unassign)")

    from app.services.email_service import send_expert_assigned_email
    from app.services.notification_service import create_notification

    expert = db.experts.find_one({"_id": oid(data["expert_id"])})
    if expert:
        user = db.users.find_one({"_id": expert["user_id"]})
        question = db.questions.find_one({"_id": oid(question_id)})
        if user and question:
            send_expert_assigned_email(user["email"], expert["name"], question["title"], question.get("expert_payout", 0))
            from app.tasks.notification_tasks import send_notification_async
            print(f"[DEBUG] assign: Dispatching send_notification_async.delay to expert user_id={user['_id']}")
            try:
                send_notification_async.delay(
                    user_id=str(user["_id"]),
                    notif_type="task_assigned",
                    title="New task assigned",
                    body=f"You have been assigned: {question['title']}",
                    link=f"/expert/task-detail.html?id={question_id}"
                )
                print(f"[DEBUG] assign: send_notification_async.delay dispatched OK")
            except Exception as e:
                print(f"[ERROR] assign: send_notification_async.delay FAILED: {e}")

    return jsonify({"status": "assigned"}), 200


@admin_bp.route("/orders/<question_id>/assign", methods=["DELETE"])
@admin_required
def unassign(question_id):
    """
    Unassigns the current expert from the order.
    Deletes Thread B and all its messages so the old expert
    immediately loses chat access and the admin sees a clean slate.
    """
    uid  = get_jwt_identity()
    db   = get_db()
    
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Question not found"}), 404

    employee = db.employees.find_one({"user_id": oid(uid)})
    if not employee or str(question.get("assigned_employee_id")) != str(employee["_id"]):
        return jsonify({"error": "You must claim this question before modifying it."}), 403

    # Delete Thread B and all its messages
    thread_b = db.threads.find_one({"question_id": oid(question_id), "thread_type": "B"})
    if thread_b:
        deleted_msgs = db.messages.delete_many({"thread_id": thread_b["_id"]})
        db.threads.delete_one({"_id": thread_b["_id"]})
        print(f"[DEBUG] unassign: Deleted Thread B and {deleted_msgs.deleted_count} messages")

    # Unassign expert
    db.questions.update_one(
        {"_id": oid(question_id)},
        {"$set": {"assigned_expert_id": None}}
    )

    return jsonify({"status": "unassigned"}), 200


@admin_bp.route("/orders/<question_id>/interested-experts", methods=["GET"])
@admin_required
def interested_experts(question_id):
    db       = get_db()
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Not found"}), 404

    experts = list(db.experts.find({"_id": {"$in": question.get("interested_expert_ids", [])}}))
    result  = []
    domain_name_map = _get_domain_name_map(db, [e.get("domain_id") for e in experts])

    for e in experts:
        result.append({
            "_id":             str(e["_id"]),
            "name":            e["name"],
            "domain":          _resolve_domain_name(
                db,
                domain_id=e.get("domain_id"),
                fallback_name=e.get("domain"),
                domain_name_map=domain_name_map
            ),
            "quality_score":   e.get("quality_score", 0),
            "tasks_completed": e.get("tasks_completed", 0),
        })
    return jsonify(result), 200


@admin_bp.route("/orders/<question_id>/thread-a", methods=["GET"])
@admin_required
def get_thread_a(question_id):
    db     = get_db()
    thread = db.threads.find_one({"question_id": oid(question_id), "thread_type": "A"})
    if not thread:
        return jsonify({"error": "Thread A not found"}), 404
    return jsonify({"thread_id": str(thread["_id"])}), 200


@admin_bp.route("/orders/<question_id>/thread-b", methods=["GET"])
@admin_required
def get_thread_b(question_id):
    db     = get_db()
    thread = db.threads.find_one({"question_id": oid(question_id), "thread_type": "B"})
    if not thread:
        return jsonify({"error": "Thread B not found"}), 404
    return jsonify({"thread_id": str(thread["_id"])}), 200


@admin_bp.route("/super-admin-chat/thread", methods=["GET"])
@admin_required
def get_or_create_super_admin_chat_thread():
    uid = get_jwt_identity()
    db = get_db()
    employee = db.employees.find_one({"user_id": oid(uid)})
    if not employee:
        return jsonify({"error": "Employee profile not found"}), 404

    thread = _ensure_super_admin_chat_thread_for_employee(db, employee)
    if not thread:
        return jsonify({"error": "No super admin account is available for chat yet"}), 503

    super_admin = None
    super_admin_user_id = thread.get("super_admin_user_id")
    if super_admin_user_id:
        super_admin = db.users.find_one(
            {"_id": super_admin_user_id},
            {"name": 1, "email": 1},
        )

    last_msg = _get_last_thread_message(db, thread)
    unread_count = _count_employee_unread_messages(db, thread, oid(uid))

    return jsonify({
        "thread_id": str(thread["_id"]),
        "unread_count": unread_count,
        "last_message_preview": (
            ((last_msg.get("body") or "").strip()[:120] + ("..." if len((last_msg.get("body") or "").strip()) > 120 else ""))
            if last_msg else None
        ),
        "last_message_at": (
            last_msg.get("created_at").isoformat()
            if last_msg and last_msg.get("created_at")
            else None
        ),
        "super_admin": {
            "user_id": str(super_admin["_id"]) if super_admin else None,
            "name": _super_admin_display_name(super_admin),
            "email": super_admin.get("email", "") if super_admin else "",
        },
    }), 200


@admin_bp.route("/super-admin-chat/unread-count", methods=["GET"])
@admin_required
def super_admin_chat_unread_count():
    uid = get_jwt_identity()
    db = get_db()
    employee = db.employees.find_one({"user_id": oid(uid)})
    if not employee:
        return jsonify({"error": "Employee profile not found"}), 404

    thread = db.threads.find_one(
        {"thread_type": "F", "employee_id": employee["_id"]},
        sort=[("updated_at", -1), ("created_at", -1)],
    )
    if not thread:
        return jsonify({"thread_id": None, "unread_count": 0}), 200

    unread_count = _count_employee_unread_messages(db, thread, oid(uid))
    return jsonify({
        "thread_id": str(thread["_id"]),
        "unread_count": unread_count,
    }), 200


@admin_bp.route("/super-admin-chat/read", methods=["POST"])
@admin_required
def mark_super_admin_chat_read():
    uid = get_jwt_identity()
    db = get_db()
    employee = db.employees.find_one({"user_id": oid(uid)})
    if not employee:
        return jsonify({"error": "Employee profile not found"}), 404

    thread = db.threads.find_one(
        {"thread_type": "F", "employee_id": employee["_id"]},
        sort=[("updated_at", -1), ("created_at", -1)],
    )
    if not thread:
        return jsonify({"status": "ok", "unread_count": 0}), 200

    now = datetime.utcnow()
    db.threads.update_one(
        {"_id": thread["_id"]},
        {"$set": {"employee_last_read_at": now}},
    )
    return jsonify({
        "status": "ok",
        "thread_id": str(thread["_id"]),
        "unread_count": 0,
        "read_at": now.isoformat(),
    }), 200



@admin_bp.route("/orders/<question_id>", methods=["GET"])
@admin_required
def order_detail(question_id):
    db       = get_db()
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Not found"}), 404

    # Verification: Must be the assigned employee OR unassigned
    uid = get_jwt_identity()
    employee = db.employees.find_one({"user_id": oid(uid)})
    if not employee:
        return jsonify({"error": "Admin record not found"}), 404
        
    assigned_id = question.get("assigned_employee_id")
    if assigned_id and str(assigned_id) != str(employee["_id"]):
        return jsonify({"error": "Access denied. This order is assigned to another admin."}), 403

    # Get student name
    student = db.students.find_one({"_id": question["student_id"]})
    student_name = student["name"] if student else "Unknown Student"

    # Get expert name if assigned
    expert_name = None
    if question.get("assigned_expert_id"):
        expert = db.experts.find_one({"_id": question["assigned_expert_id"]})
        if expert:
            expert_name = expert["name"]

    # Get Thread A and Thread B IDs
    thread_a = db.threads.find_one({"question_id": oid(question_id), "thread_type": "A"})
    thread_b = db.threads.find_one({"question_id": oid(question_id), "thread_type": "B"})

    # Get payment record
    payment  = db.payments.find_one({"question_id": oid(question_id)})

    # Get file list
    files    = list(db.files.find({"question_id": oid(question_id)}))

    domain_name = _resolve_domain_name(
        db,
        domain_id=question.get("domain_id"),
        fallback_name=question.get("domain")
    )

    # Get interested experts (anonymized)
    interested = []
    for eid in question.get("interested_expert_ids", []):
        exp = db.experts.find_one({"_id": eid})
        if exp:
            interested.append({
                "_id":             str(exp["_id"]),
                "name":            exp["name"],
                "domain":          _resolve_domain_name(
                    db,
                    domain_id=exp.get("domain_id"),
                    fallback_name=exp.get("domain")
                ),
                "quality_score":   exp.get("quality_score", 0),
                "on_time_rate":    exp.get("on_time_rate", 0),
                "tasks_completed": exp.get("tasks_completed", 0),
            })

    return jsonify({
        "_id":              str(question["_id"]),
        "title":            question["title"],
        "description":      question.get("description"),
        "domain":           domain_name,
        "status":           question["status"],
        "student_price":    question.get("student_price"),
        "student_currency": question.get("student_currency", "inr"),
        "expert_payout":    question.get("expert_payout"),   # Admin CAN see this
        "expert_currency":  question.get("expert_currency", "inr"),
        "price_approved":   question.get("price_approved", False),
        "deadline":         str(question["deadline"]) if question.get("deadline") else None,
        "assigned_expert_id": str(question["assigned_expert_id"]) if question.get("assigned_expert_id") else None,
        "assigned_employee_id": str(question["assigned_employee_id"]) if question.get("assigned_employee_id") else None,
        "thread_a_id":      str(thread_a["_id"]) if thread_a else None,
        "thread_b_id":      str(thread_b["_id"]) if thread_b else None,
        "payment":          {
            "advance_paid":    payment.get("advance_paid", False),
            "advance_bypassed": payment.get("advance_bypassed", False),
            "completion_paid": payment.get("completion_paid", False),
            "advance_amount":  payment.get("advance_amount"),
            "completion_amount": payment.get("completion_amount"),
            "total_amount":    payment.get("total_amount"),
            "currency":        payment.get("currency", question.get("student_currency", "inr")),
            "student_currency": payment.get("student_currency", question.get("student_currency", "inr")),
            "expert_currency": payment.get("expert_currency", question.get("expert_currency", "inr")),
            "status":          payment.get("status"),
        } if payment else None,
        "files": [{
            "_id":               str(f["_id"]),
            "original_filename": f["original_filename"],
            "file_type":         f["file_type"],
            "is_locked":         f["is_locked"],
            "uploader_role":     f.get("uploader_role", "student" if f.get("student_user_id") else "expert"),
            "uploader_type":     f.get("uploader_role", "student" if f.get("student_user_id") else "expert"),
            "category":          f.get("category", "attachment" if not f.get("expert_id") else "solution"),
            "forwarded_at":      str(f["forwarded_at"]) if f.get("forwarded_at") else None,
            "uploaded_at":       str(f["uploaded_at"]),
        } for f in files],
        "interested_experts": interested,
        "student_name":     student_name,
        "expert_name":      expert_name,
        "created_at":       str(question["created_at"]),
    }), 200


@admin_bp.route("/orders/<question_id>/refund-flow", methods=["GET"])
def refund_flow_detail(question_id):
    """
    Full refund-context view for admins:
    question -> files -> payments -> both chats.
    """
    db = get_db()
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Not found"}), 404

    verify_jwt_in_request()
    uid = get_jwt_identity()
    claims = get_jwt()
    role = claims.get("role")

    if role not in (Role.EMPLOYEE, Role.SUPER_ADMIN):
        return jsonify({"error": "Forbidden"}), 403

    if role == Role.EMPLOYEE:
        employee = db.employees.find_one({"user_id": oid(uid)})
        if not employee:
            return jsonify({"error": "Admin record not found"}), 404

        assigned_id = question.get("assigned_employee_id")
        if assigned_id and str(assigned_id) != str(employee["_id"]):
            return jsonify({"error": "Access denied. This order is assigned to another admin."}), 403

    student = db.students.find_one({"_id": question["student_id"]})
    user_cache = {}

    def _sender_info(user_id):
        if not user_id:
            return {"name": "System", "role": "system"}
        key = str(user_id)
        if key in user_cache:
            return user_cache[key]
        user_doc = db.users.find_one({"_id": user_id})
        if not user_doc:
            info = {"name": "Unknown", "role": "unknown"}
        else:
            info = {
                "name": user_doc.get("name") or user_doc.get("email") or "Unknown",
                "role": user_doc.get("role", "unknown")
            }
        user_cache[key] = info
        return info

    thread_a = db.threads.find_one({"question_id": oid(question_id), "thread_type": "A"})
    thread_b = db.threads.find_one({"question_id": oid(question_id), "thread_type": "B"})

    def _thread_messages(thread_doc):
        if not thread_doc:
            return []
        msgs = list(db.messages.find({"thread_id": thread_doc["_id"]}).sort("created_at", 1))
        result = []
        for m in msgs:
            sender = _sender_info(m.get("sender_user_id"))
            result.append({
                "_id": str(m["_id"]),
                "body": m.get("body", ""),
                "created_at": str(m.get("created_at")) if m.get("created_at") else None,
                "is_system": bool(m.get("is_system")),
                "sender_name": sender["name"],
                "sender_role": sender["role"],
            })
        return result

    files = list(db.files.find({"question_id": oid(question_id)}).sort("uploaded_at", 1))
    student_files = []
    solution_files = []
    for f in files:
        row = {
            "_id": str(f["_id"]),
            "name": f.get("original_filename", "file"),
            "uploaded_at": str(f.get("uploaded_at")) if f.get("uploaded_at") else None,
            "forwarded_at": str(f.get("forwarded_at")) if f.get("forwarded_at") else None,
            "is_locked": bool(f.get("is_locked", False)),
            "has_preview": bool(f.get("preview_s3_key")),
            "uploader_role": f.get("uploader_role", "student" if f.get("student_user_id") else "expert"),
        }
        if row["uploader_role"] == "expert" or f.get("category") == "solution":
            solution_files.append(row)
        else:
            student_files.append(row)

    payment = db.payments.find_one({"question_id": oid(question_id)})
    payment_payload = None
    if payment:
        payment_payload = {
            "payment_id": str(payment.get("_id")) if payment.get("_id") else None,
            "status": payment.get("status"),
            "advance_amount": payment.get("advance_amount"),
            "completion_amount": payment.get("completion_amount"),
            "total_amount": payment.get("total_amount"),
            "currency": payment.get("currency", question.get("student_currency", "inr")),
            "student_currency": payment.get("student_currency", question.get("student_currency", "inr")),
            "expert_currency": payment.get("expert_currency", question.get("expert_currency", "inr")),
            "advance_paid": bool(payment.get("advance_paid")),
            "advance_bypassed": bool(payment.get("advance_bypassed")),
            "completion_paid": bool(payment.get("completion_paid")),
            "advance_paid_at": str(payment.get("advance_paid_at")) if payment.get("advance_paid_at") else None,
            "advance_bypassed_at": str(payment.get("advance_bypassed_at")) if payment.get("advance_bypassed_at") else None,
            "completion_paid_at": str(payment.get("completion_paid_at")) if payment.get("completion_paid_at") else None,
            "refund_requested_at": str(payment.get("refund_requested_at")) if payment.get("refund_requested_at") else None,
            "refund_type": payment.get("refund_type"),
            "refund_reason": payment.get("refund_reason"),
            "refund_amount": payment.get("refund_amount"),
        }

    domain_name = _resolve_domain_name(
        db,
        domain_id=question.get("domain_id"),
        fallback_name=question.get("domain")
    )

    timeline = [{
        "title": "Question Created",
        "at": str(question.get("created_at")) if question.get("created_at") else None,
        "detail": f"{question.get('title', 'Untitled')} ({domain_name})",
        "state": "done"
    }]
    if payment_payload and payment_payload.get("advance_paid"):
        timeline.append({
            "title": "Advance Payment Completed",
            "at": payment_payload.get("advance_paid_at"),
            "detail": f"{money_label(payment_payload.get('advance_amount', 0), payment_payload.get('currency'))} paid",
            "state": "done"
        })
    elif payment_payload and payment_payload.get("advance_bypassed"):
        timeline.append({
            "title": "Advance Payment Bypassed",
            "at": payment_payload.get("advance_bypassed_at"),
            "detail": "Student will pay the full amount after completion.",
            "state": "done"
        })
    else:
        timeline.append({
            "title": "Advance Payment Pending",
            "at": None,
            "detail": "Student has not completed advance payment yet.",
            "state": "pending"
        })

    if solution_files:
        timeline.append({
            "title": "Solutions Uploaded",
            "at": solution_files[0].get("uploaded_at"),
            "detail": f"{len(solution_files)} file(s) uploaded by expert.",
            "state": "done"
        })

    if payment_payload and payment_payload.get("completion_paid"):
        timeline.append({
            "title": "Final Payment Completed",
            "at": payment_payload.get("completion_paid_at"),
            "detail": f"{money_label(payment_payload.get('completion_amount', 0), payment_payload.get('currency'))} paid",
            "state": "done"
        })
    else:
        timeline.append({
            "title": "Final Payment Pending",
            "at": None,
            "detail": "Completion payment not done yet.",
            "state": "pending"
        })

    if payment_payload and payment_payload.get("status") == "refund_requested":
        timeline.append({
            "title": "Refund Under Review",
            "at": payment_payload.get("refund_requested_at"),
            "detail": payment_payload.get("refund_reason") or "Refund raised by admin.",
            "state": "active"
        })

    # Get assigned employee's user_id if present
    assigned_employee_user_id = None
    if question.get("assigned_employee_id"):
        employee = db.employees.find_one({"_id": question["assigned_employee_id"]})
        if employee and employee.get("user_id"):
            assigned_employee_user_id = str(employee["user_id"])

    return jsonify({
        "question": {
            "_id": str(question["_id"]),
            "title": question.get("title"),
            "description": question.get("description"),
            "domain": domain_name,
            "status": question.get("status"),
            "deadline": str(question.get("deadline")) if question.get("deadline") else None,
            "created_at": str(question.get("created_at")) if question.get("created_at") else None,
            "student_price": question.get("student_price"),
            "student_currency": question.get("student_currency", "inr"),
            "expert_payout": question.get("expert_payout"),
            "expert_currency": question.get("expert_currency", "inr"),
            "student_name": student.get("name") if student else "Unknown Student",
        },
        "payment": payment_payload,
        "student_files": student_files,
        "solution_files": solution_files,
        "chat_student_admin": _thread_messages(thread_a),
        "chat_admin_expert": _thread_messages(thread_b),
        "timeline": timeline,
        "assigned_employee_user_id": assigned_employee_user_id
    }), 200


@admin_bp.route("/orders/<question_id>/quote", methods=["GET"])
@admin_required
def get_quote(question_id):
    db       = get_db()
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "student_price":  question.get("student_price"),
        "student_currency": question.get("student_currency", "inr"),
        "expert_payout":  question.get("expert_payout"),
        "expert_currency": question.get("expert_currency", "inr"),
        "price_approved": question.get("price_approved", False),
    }), 200


@admin_bp.route("/orders/<question_id>/bypass-advance", methods=["POST"])
@admin_required
def bypass_advance_payment(question_id):
    """
    Lets the assigned employee admin move an order forward without collecting
    the 50% advance. The student will owe the full amount at completion.
    """
    uid = get_jwt_identity()
    db = get_db()
    now = datetime.utcnow()

    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Question not found"}), 404

    employee = db.employees.find_one({"user_id": oid(uid)})
    if not employee or str(question.get("assigned_employee_id")) != str(employee["_id"]):
        return jsonify({"error": "Access denied. You are not assigned to this order."}), 403

    if not question.get("price_approved") or not question.get("student_price"):
        return jsonify({"error": "Set and approve the student price before bypassing advance payment."}), 400

    payment = db.payments.find_one({"question_id": oid(question_id)})
    if not payment:
        from app.services.payment_service import ensure_payment_record
        ensure_payment_record(question_id, question["student_price"], question["student_id"])
        payment = db.payments.find_one({"question_id": oid(question_id)})

    if not payment:
        return jsonify({"error": "Unable to create payment record for this order."}), 500

    if payment.get("advance_paid"):
        return jsonify({"error": "Advance payment has already been paid."}), 400

    if payment.get("completion_paid"):
        return jsonify({"error": "Completion payment has already been paid."}), 400

    total_amount = float(question.get("student_price") or payment.get("total_amount") or 0)
    if total_amount <= 0:
        return jsonify({"error": "Student price must be greater than zero."}), 400

    db.payments.update_one(
        {"question_id": oid(question_id)},
        {"$set": {
            "advance_bypassed": True,
            "advance_bypassed_at": now,
            "advance_bypassed_by": employee["_id"],
            "advance_amount": 0,
            "completion_amount": total_amount,
            "total_amount": total_amount,
            "currency": question.get("student_currency", "inr"),
            "student_currency": question.get("student_currency", "inr"),
            "expert_currency": question.get("expert_currency", "inr"),
            "status": "advance_bypassed",
        }}
    )

    db.questions.update_one(
        {"_id": oid(question_id)},
        {"$set": {"status": "in_progress"}}
    )

    thread_a = db.threads.find_one({
        "question_id": oid(question_id),
        "thread_type": "A"
    })
    if thread_a:
        body = (
            "ℹ️ Advance payment has been bypassed for this order. "
            f"You can pay the full amount of {money_label(total_amount, question.get('student_currency'))} after the solution preview is ready."
        )
        msg_result = db.messages.insert_one({
            "thread_id": thread_a["_id"],
            "sender_user_id": employee["user_id"],
            "body": body,
            "is_system": True,
            "created_at": now
        })
        try:
            from app.extensions import socketio
            payload = {
                "_id": str(msg_result.inserted_id),
                "thread_id": str(thread_a["_id"]),
                "sender_user_id": str(employee["user_id"]),
                "body": body,
                "is_system": True,
                "created_at": now.isoformat()
            }
            socketio.start_background_task(
                lambda: socketio.emit("new_message", payload, room=f"thread_{thread_a['_id']}")
            )
        except Exception:
            pass

    student = db.students.find_one({"_id": question["student_id"]})
    if student:
        try:
            from app.tasks.notification_tasks import send_notification_async
            send_notification_async.delay(
                user_id=str(student["user_id"]),
                notif_type="advance_payment_bypassed",
                title="Advance payment deferred",
                body=f"Work can begin on '{question['title']}'. You will pay the full amount after completion.",
                link=f"/student/order-detail.html?id={question_id}"
            )
        except Exception:
            pass

    return jsonify({
        "status": "advance_bypassed",
        "completion_amount": total_amount,
        "total_amount": total_amount,
        "currency": question.get("student_currency", "inr")
    }), 200


@admin_bp.route("/experts/search", methods=["GET"])
@admin_required
def search_experts():
    db     = get_db()
    query  = request.args.get("q", "").strip()
    domain = request.args.get("domain", "").strip()

    if not query and not domain:
        return jsonify([]), 200

    mongo_query = {"kyc_status": "approved"}

    if query:
        # Search by partial name OR exact ID
        # If query is 24-char hex, try ID first
        is_oid = len(query) == 24 and all(c in "0123456789abcdefABCDEF" for c in query)
        
        if is_oid:
            mongo_query["_id"] = oid(query)
        else:
            mongo_query["name"] = {"$regex": query, "$options": "i"}

    if domain:
        escaped_domain = re.escape(domain)
        domain_doc = db.domains.find_one(
            {"name": {"$regex": f"^{escaped_domain}$", "$options": "i"}},
            {"_id": 1}
        )
        if domain_doc:
            domain_filter_query = {
                "$or": [
                    {"domain_id": domain_doc["_id"]},
                    {"domain": {"$regex": f"^{escaped_domain}$", "$options": "i"}}
                ]
            }
        else:
            domain_filter_query = {"domain": {"$regex": f"^{escaped_domain}$", "$options": "i"}}

        mongo_query = {"$and": [mongo_query, domain_filter_query]}

    experts = list(db.experts.find(mongo_query).limit(10))
    domain_name_map = _get_domain_name_map(db, [e.get("domain_id") for e in experts])

    return jsonify([{
        "_id":             str(e["_id"]),
        "name":            e["name"],
        "domain":          _resolve_domain_name(
            db,
            domain_id=e.get("domain_id"),
            fallback_name=e.get("domain"),
            domain_name_map=domain_name_map
        ),
        "quality_score":   e.get("quality_score", 0),
        "on_time_rate":    e.get("on_time_rate", 0),
        "tasks_completed": e.get("tasks_completed", 0),
    } for e in experts]), 200


@admin_bp.route("/orders/<question_id>/forward-solutions", methods=["POST"])
@admin_required
def forward_all_solutions(question_id):
    db = get_db()
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Question not found"}), 404

    # Verification: Must be the assigned employee
    uid = get_jwt_identity()
    employee = db.employees.find_one({"user_id": oid(uid)})
    if not employee or str(question.get("assigned_employee_id")) != str(employee["_id"]):
        return jsonify({"error": "Access denied. You are not assigned to this order."}), 403

    now = datetime.utcnow()
    
    # Find all expert files for this question that haven't been forwarded
    # category="solution" OR uploader_role="expert"
    query = {
        "question_id": oid(question_id),
        "$or": [{"category": "solution"}, {"uploader_role": "expert"}]
    }
    
    expert_files = list(db.files.find(query))
    if not expert_files:
        return jsonify({"error": "No solution files found to forward"}), 404

    # Update all of them at once
    db.files.update_many(
        query,
        {"$set": {"forwarded_at": now}}
    )

    # Update question status to reviewing
    db.questions.update_one(
        {"_id": oid(question_id), "status": "in_progress"},
        {"$set": {"status": "reviewing"}}
    )

    # Notify student (once)
    question = db.questions.find_one({"_id": oid(question_id)})
    if question:
        student = db.students.find_one({"_id": question["student_id"]})
        if student:
            user = db.users.find_one({"_id": student["user_id"]})
            if user:
                from app.services.email_service import send_solution_uploaded_email
                send_solution_uploaded_email(user["email"], student["name"], question["title"])
                
                from app.tasks.notification_tasks import send_notification_async
                send_notification_async.delay(
                    user_id=str(user["_id"]),
                    notif_type="solution_ready",
                    title="Your solution is ready",
                    body="The expert has uploaded the solution. A preview is available. Pay to unlock all files.",
                    link=f"/student/order-detail.html?id={question_id}"
                )

    return jsonify({"status": "forwarded", "count": len(expert_files)}), 200


@admin_bp.route("/files/<file_id>/forward", methods=["POST"])
@admin_required
def forward_file(file_id):
    # Keep this for backward compatibility or individual file actions if needed, 
    # but make it find the question and forward ALL to satisfy "at once" if preferred.
    # Actually, let's just make it call the question-based logic.
    db   = get_db()
    file = db.files.find_one({"_id": oid(file_id)})
    if not file:
        return jsonify({"error": "File not found"}), 404
    
    return forward_all_solutions(str(file["question_id"]))


@admin_bp.route("/files/<file_id>/url", methods=["GET"])
@admin_required
def get_file_url_admin(file_id):
    from app.services.file_service import get_signed_url
    db   = get_db()
    file = db.files.find_one({"_id": oid(file_id)})
    if not file:
        return jsonify({"error": "Not found"}), 404

    # Admin always gets the full file — not the preview
    import mimetypes
    filename = file.get("original_filename", "file")
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    url = get_signed_url(file["s3_key"], filename=filename, content_type=content_type)
    return jsonify({"url": url}), 200


@admin_bp.route("/files/<file_id>/url-shared", methods=["GET"])
@role_required(Role.EMPLOYEE, Role.SUPER_ADMIN)
def get_file_url_shared(file_id):
    from app.services.file_service import get_signed_url
    db = get_db()
    file = db.files.find_one({"_id": oid(file_id)})
    if not file:
        return jsonify({"error": "Not found"}), 404

    import mimetypes
    filename = file.get("original_filename", "file")
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    url = get_signed_url(file["s3_key"], filename=filename, content_type=content_type)
    return jsonify({"url": url}), 200


@admin_bp.route("/orders/<question_id>/feedback", methods=["POST"])
@admin_required
def submit_feedback(question_id):
    uid      = get_jwt_identity()
    data     = request.get_json()
    db       = get_db()

    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Question not found"}), 404

    # Verification: Must be the assigned employee
    employee = db.employees.find_one({"user_id": oid(uid)})
    if not employee or str(question.get("assigned_employee_id")) != str(employee["_id"]):
        return jsonify({"error": "Access denied. You are not assigned to this order."}), 403

    rating      = data.get("rating")        # 1-5, internal only
    public_note = data.get("public_note")   # Shown on student global feed
    grade       = data.get("grade")         # e.g. "A+", "Excellent"

    if rating and (rating < 1 or rating > 5):
        return jsonify({"error": "Rating must be between 1 and 5"}), 400

    question = db.questions.find_one({"_id": oid(question_id)})
    if not question or not question.get("assigned_expert_id"):
        return jsonify({"error": "No expert assigned to this order"}), 400

    employee = db.employees.find_one({"user_id": oid(uid)})

    # Upsert feedback document and mark question as completed
    db.feedback.update_one(
        {"question_id": oid(question_id)},
        {"$set": {
            "question_id": oid(question_id),
            "expert_id":   question["assigned_expert_id"],
            "employee_id": employee["_id"],
            "rating":      rating,
            "public_note": public_note,
            "grade":       grade,
            "created_at":  datetime.utcnow()
        }},
        upsert=True
    )
    db.questions.update_one(
        {"_id": oid(question_id)},
        {"$set": {"status": "completed"}}
    )

    # Update expert's quality score (rolling average)
    if rating:
        expert = db.experts.find_one({"_id": question["assigned_expert_id"]})
        completed = expert.get("tasks_completed", 0)
        old_score = expert.get("quality_score", 0)
        # Weighted rolling average
        new_score = ((old_score * completed) + rating) / (completed + 1)
        db.experts.update_one(
            {"_id": question["assigned_expert_id"]},
            {"$set":  {"quality_score": round(new_score, 2)},
             "$inc":  {"tasks_completed": 1}}
        )

    return jsonify({"status": "feedback_submitted"}), 200


@admin_bp.route("/orders/<question_id>/initiate-refund", methods=["POST"])
@admin_required
def initiate_refund(question_id):
    """
    Admin escalates a refund request to the super admin queue.
    - BUG#8: Validate payment intents exist before marking for refund
    - BUG#9: Check for race conditions (already refund_requested or refunded)
    """
    uid  = get_jwt_identity()
    data = request.get_json()
    db   = get_db()

    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Question not found"}), 404

    # Must be the assigned employee
    employee = db.employees.find_one({"user_id": oid(uid)})
    if not employee or str(question.get("assigned_employee_id")) != str(employee["_id"]):
        return jsonify({"error": "Access denied. You are not assigned to this order."}), 403

    reason = (data.get("reason") or "").strip()
    if not reason:
        return jsonify({"error": "A reason is required to initiate a refund"}), 400

    refund_amount = data.get("refund_amount")
    try:
        refund_amount = float(refund_amount)
    except (TypeError, ValueError):
        return jsonify({"error": "A valid refund amount is required"}), 400

    if refund_amount <= 0:
        return jsonify({"error": "Refund amount must be greater than zero"}), 400

    payment = db.payments.find_one({"question_id": oid(question_id)})
    if not payment:
        return jsonify({"error": "No payment record for this order"}), 400

    if not payment.get("advance_paid") and not payment.get("completion_paid"):
        return jsonify({"error": "No payment made — nothing to refund"}), 400

    # BUG#9: Check for race conditions
    if payment.get("status") == "refunded":
        return jsonify({"error": "This order has already been refunded"}), 400
    
    if payment.get("status") == "refund_requested":
        return jsonify({"error": "A refund is already pending review"}), 409

    # Determine refund type based on what has been paid
    is_completion_refund = payment.get("completion_paid", False)
    refund_type = "completion" if is_completion_refund else "advance"

    # Validate refund amount against the correct payment pool.
    # After completion payment, allow refunding up to the total paid amount.
    if is_completion_refund:
        max_refundable = float(
            payment.get("total_amount")
            or (
                float(payment.get("advance_amount", 0) or 0)
                + float(payment.get("completion_amount", 0) or 0)
            )
        )
        pool_label = "total paid amount"
        if (
            payment.get("advance_paid")
            and refund_amount > float(payment.get("completion_amount", 0) or 0)
        ):
            refund_type = "full"
    else:
        max_refundable = payment.get("advance_amount", 0)
        pool_label = "advance payment"

    if refund_amount > max_refundable:
        currency = payment.get("currency") or question.get("student_currency", "inr")
        return jsonify({
            "error": (
                f"Refund amount ({money_label(refund_amount, currency)}) cannot exceed "
                f"the {pool_label} ({money_label(max_refundable, currency)})"
            )
        }), 400

    # BUG#8: Validate payment intents exist before escalating
    if refund_type == "advance":
        if not payment.get("advance_payment_intent_id"):
            return jsonify({"error": "No Stripe payment intent found for advance payment. Cannot process refund."}), 400
    elif refund_type == "completion":
        if not payment.get("completion_payment_intent_id"):
            return jsonify({"error": "No Stripe payment intent found for completion payment. Cannot process refund."}), 400
    elif refund_type == "full":
        # BUG#8: Validate both payment intents exist for full refunds
        if not payment.get("advance_payment_intent_id"):
            return jsonify({"error": "No Stripe payment intent found for advance payment. Cannot process full refund."}), 400
        if not payment.get("completion_payment_intent_id"):
            return jsonify({"error": "No Stripe payment intent found for completion payment. Cannot process full refund."}), 400

    now = datetime.utcnow()

    # Escalate to super admin by setting refund_requested
    db.payments.update_one(
        {"question_id": oid(question_id)},
        {"$set": {
            "status":                     "refund_requested",
            "refund_type":                refund_type,
            "refund_reason":              reason,
            "refund_amount":              refund_amount,
            "currency":                   payment.get("currency") or question.get("student_currency", "inr"),
            "student_currency":           payment.get("student_currency") or question.get("student_currency", "inr"),
            "expert_currency":            payment.get("expert_currency") or question.get("expert_currency", "inr"),
            "refund_initiated_by":        employee["_id"],
            "refund_initiated_by_name":   employee.get("name", ""),
            "refund_requested_at":        now
        }}
    )
    db.questions.update_one(
        {"_id": oid(question_id)},
        {"$set": {"status": "refund_requested"}}
    )

    # Post automated message to Thread A so student knows
    thread_a = db.threads.find_one({
        "question_id": oid(question_id),
        "thread_type": "A"
    })
    if thread_a:
        auto_msg_body = (
            "ℹ️ [ADMIN] A refund request has been submitted for this order and is "
            "currently under review by our team. We'll notify you once a decision is made."
        )
        from app.extensions import socketio
        msg_result = db.messages.insert_one({
            "thread_id":      thread_a["_id"],
            "sender_user_id": employee["user_id"],
            "body":           auto_msg_body,
            "is_system":      True,
            "created_at":     now
        })
        _payload = {
            "_id":            str(msg_result.inserted_id),
            "thread_id":      str(thread_a["_id"]),
            "sender_user_id": str(employee["user_id"]),
            "body":           auto_msg_body,
            "is_system":      True,
            "created_at":     now.isoformat()
        }
        socketio.start_background_task(
            lambda: socketio.emit("new_message", _payload, room=f"thread_{thread_a['_id']}")
        )

    from app.tasks.notification_tasks import send_notification_async

    # Notify student
    student = db.students.find_one({"_id": question["student_id"]})
    if student:
        send_notification_async.delay(
            user_id=str(student["user_id"]),
            notif_type="refund_under_review",
            title="Refund under review",
            body=f"Your refund request for '{question['title']}' is being reviewed.",
            link=f"/student/order-detail.html?id={question_id}"
        )

    # Notify super admins.
    # Some deployments keep super-admin identities only in users.role=super_admin
    # and may not have mirrored records in super_admins collection.
    super_admin_user_ids = set()
    for sa in db.super_admins.find({}, {"user_id": 1}):
        if sa.get("user_id"):
            super_admin_user_ids.add(str(sa["user_id"]))

    for user in db.users.find({"role": Role.SUPER_ADMIN}, {"_id": 1}):
        super_admin_user_ids.add(str(user["_id"]))

    for user_id in super_admin_user_ids:
        send_notification_async.delay(
            user_id=user_id,
            notif_type="refund_requested_super",
            title="Refund Review Required",
            body=f"Admin {employee.get('name', 'N/A')} initiated a {refund_type} refund for order: {question['title']}",
            link=f"/super-admin/financials.html"
        )

    # Notify the assigned expert
    if question.get("assigned_expert_id"):
        expert = db.experts.find_one({"_id": question["assigned_expert_id"]})
        if expert:
            expert_notif_title = "Refund Requested for Your Task"
            expert_notif_body = (
                f"A post-completion refund has been requested for your task: '{question['title']}'. "
                "This is under review and your payout is pending the outcome."
                if is_completion_refund else
                f"A refund has been requested for your task: '{question['title']}'. "
                "This is under review."
            )
            send_notification_async.delay(
                user_id=str(expert["user_id"]),
                notif_type="refund_requested_expert",
                title=expert_notif_title,
                body=expert_notif_body,
                link=f"/expert/task-detail.html?id={question_id}"
            )

    return jsonify({"status": "refund_escalated_to_superadmin", "refund_type": refund_type}), 200



@admin_bp.route("/dashboard/metrics", methods=["GET"])
@admin_required
def dashboard_metrics():
    db = get_db()
    uid = get_jwt_identity()
    
    employee = db.employees.find_one({"user_id": oid(uid)})
    emp_id = employee["_id"] if employee else None

    # Filter orders to only those handled by this specific employee
    base_query = {
        "assigned_employee_id": emp_id
    }
    
    total_orders = db.questions.count_documents(base_query)
    new_orders = db.questions.count_documents({**base_query, "status": "awaiting_quote"})
    pending_payment = db.questions.count_documents({**base_query, "status": "pending_payment"})
    in_progress = db.questions.count_documents({**base_query, "status": "in_progress"})
    
    
    return jsonify({
        "orders": {
            "total": total_orders,
            "new": new_orders,
            "pending_payment": pending_payment,
            "in_progress": in_progress
        }
    }), 200

@admin_bp.route("/dashboard/charts", methods=["GET"])
@admin_required
def dashboard_charts():
    from dateutil.relativedelta import relativedelta
    from datetime import datetime, timedelta
    db = get_db()
    uid = get_jwt_identity()
    
    # 1. Pipeline (orders assigned to this admin or unassigned)
    employee = db.employees.find_one({"user_id": oid(uid)})
    emp_id = employee["_id"] if employee else None

    base_query = {
        "assigned_employee_id": emp_id
    }

    pipeline_status = list(db.questions.aggregate([
        {"$match": base_query},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]))
    
    pipeline_dict = {item["_id"]: item["count"] for item in pipeline_status}
    
    # Combine refunded and cancelled
    refunded_cancelled = pipeline_dict.get("refunded", 0) + pipeline_dict.get("cancelled", 0)
    
    pipeline = {
        "awaiting_quote": pipeline_dict.get("awaiting_quote", 0),
        "pending_payment": pipeline_dict.get("pending_payment", 0),
        "in_progress": pipeline_dict.get("in_progress", 0),
        "reviewing": pipeline_dict.get("reviewing", 0),
        "completed": pipeline_dict.get("completed", 0),
        "refunded_cancelled": refunded_cancelled
    }
    
    # 2. Orders by Domain
    domain_counts_raw = list(db.questions.aggregate([
        {"$match": {"assigned_employee_id": emp_id}},
        {"$group": {
            "_id": {"domain_id": "$domain_id", "domain": "$domain"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ]))

    domain_name_map = _get_domain_name_map(
        db,
        [item["_id"].get("domain_id") for item in domain_counts_raw if isinstance(item.get("_id"), dict)]
    )

    aggregated_domain_counts = {}
    for item in domain_counts_raw:
        domain_key = item.get("_id") if isinstance(item.get("_id"), dict) else {}
        resolved_domain_name = _resolve_domain_name(
            db,
            domain_id=domain_key.get("domain_id"),
            fallback_name=domain_key.get("domain"),
            domain_name_map=domain_name_map
        )
        aggregated_domain_counts[resolved_domain_name] = aggregated_domain_counts.get(resolved_domain_name, 0) + item["count"]

    domain_counts = sorted(
        [{"domain": d, "count": c} for d, c in aggregated_domain_counts.items()],
        key=lambda x: x["count"],
        reverse=True
    )
    
    orders_by_domain = []
    other_count = 0
    for i, item in enumerate(domain_counts):
        if i < 6:
            orders_by_domain.append(item)
        else:
            other_count += item["count"]
            
    if other_count > 0:
        orders_by_domain.append({"domain": "Other", "count": other_count})
        
    # 3. Orders Created Over Time (last 30 days)
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=29) # 30 days including today
    
    orders_time = list(db.questions.aggregate([
        {"$match": {
            "assigned_employee_id": emp_id,
            "created_at": {"$gte": thirty_days_ago}
        }},
        {"$project": {
            "date": {
                "$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}
            }
        }},
        {"$group": {"_id": "$date", "count": {"$sum": 1}}}
    ]))
    
    orders_time_dict = {item["_id"]: item["count"] for item in orders_time}
    
    orders_over_time = []
    for i in range(29, -1, -1):
        dt = now - timedelta(days=i)
        dt_str = dt.strftime("%Y-%m-%d")
        orders_over_time.append({
            "date": dt.strftime("%b %-d"),
            "count": orders_time_dict.get(dt_str, 0)
        })
        
    # 4. Attention Needed
    employee = db.employees.find_one({"user_id": oid(uid)})
    emp_id = employee["_id"] if employee else None
    
    # Filter for orders assigned to THIS admin
    base_query = {
        "assigned_employee_id": emp_id
    }

    attention_needed = []
    # a. Unassigned (advance paid or bypassed, no expert)
    ready_payment_qids = [p["question_id"] for p in db.payments.find({
        "$or": [
            {"advance_paid": True},
            {"advance_bypassed": True}
        ]
    })]
    unassigned = list(db.questions.find({
        **base_query,
        "_id": {"$in": ready_payment_qids},
        "assigned_expert_id": {"$in": [None, ""]}
    }).limit(10))
    
    for q in unassigned:
        attention_needed.append({
            "_id": str(q["_id"]),
            "title": q["title"],
            "domain": _resolve_domain_name(
                db,
                domain_id=q.get("domain_id"),
                fallback_name=q.get("domain")
            ),
            "status": "unassigned",
            "reason": "Expert not assigned (Advance paid or bypassed)",
            "priority": 1,
            "days_waiting": (now - q["created_at"]).days
        })
        
    # b. awaiting_quote > 24h
    one_day_ago = now - timedelta(hours=24)
    stale_quotes = list(db.questions.find({
        **base_query,
        "status": "awaiting_quote",
        "created_at": {"$lte": one_day_ago}
    }).limit(10))
    
    for q in stale_quotes:
        attention_needed.append({
            "_id": str(q["_id"]),
            "title": q["title"],
            "domain": _resolve_domain_name(
                db,
                domain_id=q.get("domain_id"),
                fallback_name=q.get("domain")
            ),
            "status": q["status"],
            "reason": "Awaiting Quote > 24h",
            "priority": 2,
            "days_waiting": (now - q["created_at"]).days
        })
        
    # c. reviewing > 48h
    two_days_ago = now - timedelta(hours=48)
    # Ideally we'd use status updated_at, but we only have created_at. We'll use created_at as an approximation for now if no updated_at.
    # Actually, we can check feedback or payout? No, it's reviewing, so not completed.
    # We can just check created_at for now.
    stale_reviewing = list(db.questions.find({
        **base_query,
        "status": "reviewing"
    }).limit(10))
    
    for q in stale_reviewing:
        # Approximate: if it's been reviewing but created long ago, we just flag it. 
        # A real system would track `status_updated_at`.
        attention_needed.append({
            "_id": str(q["_id"]),
            "title": q["title"],
            "domain": _resolve_domain_name(
                db,
                domain_id=q.get("domain_id"),
                fallback_name=q.get("domain")
            ),
            "status": q["status"],
            "reason": "In Review",
            "priority": 3,
            "days_waiting": (now - q["created_at"]).days
        })
        
    # Sort by priority
    attention_needed.sort(key=lambda x: x["priority"])
    attention_needed = attention_needed[:10]
    
    return jsonify({
        "pipeline": pipeline,
        "orders_by_domain": orders_by_domain,
        "orders_over_time": orders_over_time,
        "attention_needed": attention_needed
    }), 200
