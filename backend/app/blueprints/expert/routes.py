from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from bson import ObjectId
from datetime import datetime
import re

from app.blueprints.expert import expert_bp
from app.extensions import get_db
from app.utils.decorators import expert_required
from app.utils.helpers import oid, to_str_id
from app.utils.constants import KYCStatus


def _to_object_id(raw_id):
    if isinstance(raw_id, ObjectId):
        return raw_id
    if not raw_id:
        return None
    return oid(raw_id)


def _resolve_domain_name(db, domain_id=None, fallback_name=None):
    domain_name = fallback_name if fallback_name else "Unknown"
    domain_oid = _to_object_id(domain_id)
    if not domain_oid:
        return domain_name

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


def _ensure_super_admin_chat_thread(db, expert_doc):
    thread = db.threads.find_one(
        {"thread_type": "E", "expert_id": expert_doc["_id"]},
        sort=[("updated_at", -1), ("created_at", -1)],
    )
    if thread:
        if not thread.get("super_admin_user_id"):
            super_admin_user_id = _resolve_super_admin_user_id(db)
            if super_admin_user_id:
                db.threads.update_one(
                    {"_id": thread["_id"]},
                    {"$set": {"super_admin_user_id": super_admin_user_id}},
                )
                thread["super_admin_user_id"] = super_admin_user_id
        return thread

    now = datetime.utcnow()
    super_admin_user_id = _resolve_super_admin_user_id(db)
    if not super_admin_user_id:
        return None

    insert_payload = {
        "question_id": None,
        "thread_type": "E",
        "student_id": None,
        "expert_id": expert_doc["_id"],
        "employee_id": None,
        "super_admin_user_id": super_admin_user_id,
        "created_at": now,
        "updated_at": now,
        "expert_last_read_at": None,
        "super_admin_last_read_at": now if super_admin_user_id else None,
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


def _count_expert_unread_messages(db, thread, expert_user_oid):
    if not thread:
        return 0

    query = {
        "thread_id": thread["_id"],
        "sender_user_id": {"$ne": expert_user_oid},
    }
    read_cutoff = thread.get("expert_last_read_at")
    if read_cutoff:
        query["created_at"] = {"$gt": read_cutoff}

    return db.messages.count_documents(query)


@expert_bp.route("/dashboard", methods=["GET"])
@expert_required
def dashboard():
    uid    = get_jwt_identity()
    db     = get_db()
    expert = db.experts.find_one({"user_id": oid(uid)})
    if not expert:
        return jsonify({"error": "Profile not found"}), 404
        
    expert["domain"] = _resolve_domain_name(
        db,
        domain_id=expert.get("domain_id"),
        fallback_name=expert.get("domain")
    )
            
    expert = to_str_id(expert)
    expert["user_id"] = str(expert["user_id"])
    return jsonify(expert), 200


@expert_bp.route("/dashboard/charts", methods=["GET"])
@expert_required
def dashboard_charts():
    from dateutil.relativedelta import relativedelta
    from datetime import datetime
    uid    = get_jwt_identity()
    db     = get_db()
    expert = db.experts.find_one({"user_id": oid(uid)})
    
    # Tasks by status
    pipeline_status = [
        {"$match": {"assigned_expert_id": expert["_id"], "status": {"$in": ["in_progress", "reviewing", "completed"]}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    status_counts = list(db.questions.aggregate(pipeline_status))
    tasks_by_status = {item["_id"]: item["count"] for item in status_counts}
    
    # Monthly earnings (completed tasks)
    now = datetime.utcnow()
    six_months_ago = datetime(now.year, now.month, 1) - relativedelta(months=5)
    
    pipeline_earnings = [
        {"$match": {
            "assigned_expert_id": expert["_id"],
            "status": "completed"
        }},
        {"$lookup": {
            "from": "feedback",
            "localField": "_id",
            "foreignField": "question_id",
            "as": "feedback"
        }},
        # Alternatively, we could use payout completion date or question updated_at.
        # Assuming question completion date is approximately when it was completed.
        # But we don't have completed_at explicitly in question. Let's use created_at of feedback if available, else created_at of question.
        # Wait, payouts collection has task_completed_at!
        {"$lookup": {
            "from": "payouts",
            "localField": "_id",
            "foreignField": "question_id",
            "as": "payout"
        }},
        {"$unwind": {"path": "$payout", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "amount": "$expert_payout",
            # Fallback to question created_at if payout doesn't exist
            "date": {"$cond": [{"$ifNull": ["$payout.task_completed_at", False]}, "$payout.task_completed_at", "$created_at"]}
        }},
        {"$match": {"date": {"$gte": six_months_ago}}},
        {"$project": {
            "month": {"$month": "$date"},
            "year": {"$year": "$date"},
            "amount": 1
        }},
        {"$group": {
            "_id": {"month": "$month", "year": "$year"},
            "earned": {"$sum": "$amount"}
        }}
    ]
    earnings_data = list(db.questions.aggregate(pipeline_earnings))
    
    monthly_earnings = []
    for i in range(5, -1, -1):
        dt = datetime(now.year, now.month, 1) - relativedelta(months=i)
        month_label = dt.strftime("%b")
        earned = sum(item["earned"] for item in earnings_data if item["_id"]["month"] == dt.month and item["_id"]["year"] == dt.year)
        monthly_earnings.append({"month": month_label, "earned": float(earned or 0)})
        
    return jsonify({
        "tasks_by_status": tasks_by_status,
        "monthly_earnings": monthly_earnings
    }), 200


@expert_bp.route("/jobs", methods=["GET"])
@expert_required
def job_board():
    uid    = get_jwt_identity()
    db     = get_db()
    expert = db.experts.find_one({"user_id": oid(uid)})

    if not expert:
        return jsonify({"error": "Profile not found"}), 404

    if expert.get("kyc_status") != KYCStatus.APPROVED:
        return jsonify({"error": "KYC approval required", "kyc_status": expert.get("kyc_status")}), 403

    domain_id = expert.get("domain_id")
    domain_oid = _to_object_id(domain_id)
    domain_name = _resolve_domain_name(
        db,
        domain_id=domain_id,
        fallback_name=(expert.get("domain") or "").strip()
    ).strip()
    
    query = {
        "status": {"$in": ["awaiting_quote", "pending_payment", "in_progress"]},
        "assigned_expert_id": None,
        "interested_expert_ids": {"$ne": expert["_id"]}
    }
    
    # Prefer domain_id as source of truth, while keeping legacy string-domain fallback.
    if domain_oid:
        query["$or"] = [{"domain_id": domain_oid}]
        if domain_name:
            escaped_name = re.escape(domain_name)
            query["$or"].append({"domain": {"$regex": f"^{escaped_name}$", "$options": "i"}})
    elif domain_name:
        escaped_name = re.escape(domain_name)
        query["domain"] = {"$regex": f"^{escaped_name}$", "$options": "i"}
    else:
        # If expert has no domain, they shouldn't see anything? 
        # Or maybe all jobs? Usually experts are tied to domains.
        return jsonify([]), 200

    questions = list(db.questions.find(query).sort("created_at", -1))
    qids = [q["_id"] for q in questions]
    file_counts = list(db.files.aggregate([
        {"$match": {"question_id": {"$in": qids}}},
        {"$group": {"_id": "$question_id", "count": {"$sum": 1}}}
    ]))
    counts_map = {item["_id"]: item["count"] for item in file_counts}

    result = []
    for q in questions:
        result.append({
            "_id":         str(q["_id"]),
            "title":       q["title"],
            "description": q.get("description"),
            "domain":      _resolve_domain_name(
                db,
                domain_id=q.get("domain_id"),
                fallback_name=q.get("domain")
            ),
            "deadline":    str(q["deadline"]) if q.get("deadline") else None,
            "created_at":  str(q["created_at"]),
            "files_count": counts_map.get(q["_id"], 0)
        })
    return jsonify(result), 200


@expert_bp.route("/jobs/applied", methods=["GET"])
@expert_required
def applied_jobs():
    uid    = get_jwt_identity()
    db     = get_db()
    expert = db.experts.find_one({"user_id": oid(uid)})

    if not expert:
        return jsonify({"error": "Profile not found"}), 404

    # Fetch questions where the expert is in the interested list OR directly assigned, 
    # but exclude completed/cancelled ones so they don't clutter the Applied tab
    query = {
        "$and": [
            {
                "$or": [
                    {"interested_expert_ids": expert["_id"]},
                    {"assigned_expert_id": expert["_id"]}
                ]
            },
            {
                "status": {"$nin": ["completed", "cancelled", "refunded"]}
            }
        ]
    }
    questions = list(db.questions.find(query).sort("created_at", -1))
    qids = [q["_id"] for q in questions]
    file_counts = list(db.files.aggregate([
        {"$match": {"question_id": {"$in": qids}}},
        {"$group": {"_id": "$question_id", "count": {"$sum": 1}}}
    ]))
    counts_map = {item["_id"]: item["count"] for item in file_counts}

    result = []
    for q in questions:
        # Determine specific application status
        app_status = "Interested"
        if q.get("assigned_expert_id"):
            if q["assigned_expert_id"] == expert["_id"]:
                app_status = "Assigned to You"
            else:
                app_status = "Assigned to Someone Else"
        elif q["status"] == "cancelled":
            app_status = "Cancelled"
        elif q["status"] != "awaiting_quote":
            app_status = "In Review"

        result.append({
            "_id":          str(q["_id"]),
            "title":        q["title"],
            "description":  q.get("description"),
            "domain":       _resolve_domain_name(
                db,
                domain_id=q.get("domain_id"),
                fallback_name=q.get("domain")
            ),
            "deadline":     str(q["deadline"]) if q.get("deadline") else None,
            "created_at":   str(q["created_at"]),
            "status":       q["status"],
            "app_status":   app_status,
            "files_count":  counts_map.get(q["_id"], 0)
        })
    return jsonify(result), 200


@expert_bp.route("/jobs/<question_id>/interest", methods=["POST"])
@expert_required
def express_interest(question_id):
    uid    = get_jwt_identity()
    db     = get_db()
    expert = db.experts.find_one({"user_id": oid(uid)})
    db.questions.update_one(
        {"_id": oid(question_id)},
        {"$addToSet": {"interested_expert_ids": expert["_id"]}}
    )

    question = db.questions.find_one({"_id": oid(question_id)})
    if question and question.get("assigned_employee_id"):
        employee = db.employees.find_one({"_id": question["assigned_employee_id"]})
        if employee:
            from app.services.notification_service import create_notification
            from app.tasks.notification_tasks import send_notification_async
            send_notification_async.delay(
                user_id=str(employee["user_id"]),
                notif_type="new_interest",
                title="Expert expressed interest",
                body=f"{expert['name']} is interested in: {question['title']}",
                link=f"/admin/cockpit.html?id={question_id}"
            )

    return jsonify({"status": "interested"}), 200


@expert_bp.route("/jobs/<question_id>/interest", methods=["DELETE"])
@expert_required
def withdraw_interest(question_id):
    uid    = get_jwt_identity()
    db     = get_db()
    expert = db.experts.find_one({"user_id": oid(uid)})
    
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Question not found"}), 404
        
    if question.get("assigned_expert_id") == expert["_id"]:
        return jsonify({"error": "Cannot withdraw interest after being assigned."}), 400

    db.questions.update_one(
        {"_id": oid(question_id)},
        {"$pull": {"interested_expert_ids": expert["_id"]}}
    )

    return jsonify({"status": "withdrawn"}), 200


@expert_bp.route("/tasks", methods=["GET"])
@expert_required
def my_tasks():
    uid       = get_jwt_identity()
    db        = get_db()
    expert    = db.experts.find_one({"user_id": oid(uid)})
    questions = list(db.questions.find({"assigned_expert_id": expert["_id"]}))

    result = []
    for q in questions:
        result.append({
            "_id":          str(q["_id"]),
            "title":        q["title"],
            "domain":       _resolve_domain_name(
                db,
                domain_id=q.get("domain_id"),
                fallback_name=q.get("domain")
            ),
            "deadline":     str(q["deadline"]) if q.get("deadline") else None,
            "status":       q["status"],
            "expert_payout": q.get("expert_payout"),
            "expert_currency": q.get("expert_currency", "inr"),
        })
    return jsonify(result), 200


@expert_bp.route("/tasks/<question_id>/thread", methods=["GET"])
@expert_required
def get_thread(question_id):
    uid    = get_jwt_identity()
    db     = get_db()
    expert = db.experts.find_one({"user_id": oid(uid)})

    # Verify the expert is still assigned to this question
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question or question.get("assigned_expert_id") != expert["_id"]:
        return jsonify({"error": "You are not assigned to this task"}), 403

    thread = db.threads.find_one({
        "question_id": oid(question_id),
        "thread_type": "B",
        "expert_id":   expert["_id"]
    })
    if not thread:
        return jsonify({"error": "Thread not found"}), 404
    return jsonify({"thread_id": str(thread["_id"])}), 200


@expert_bp.route("/super-admin-chat/thread", methods=["GET"])
@expert_required
def get_or_create_super_admin_chat_thread():
    uid = get_jwt_identity()
    db = get_db()
    expert = db.experts.find_one({"user_id": oid(uid)})
    if not expert:
        return jsonify({"error": "Profile not found"}), 404

    thread = _ensure_super_admin_chat_thread(db, expert)
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
    unread_count = _count_expert_unread_messages(db, thread, oid(uid))

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


@expert_bp.route("/super-admin-chat/unread-count", methods=["GET"])
@expert_required
def super_admin_chat_unread_count():
    uid = get_jwt_identity()
    db = get_db()
    expert = db.experts.find_one({"user_id": oid(uid)})
    if not expert:
        return jsonify({"error": "Profile not found"}), 404

    thread = db.threads.find_one(
        {"thread_type": "E", "expert_id": expert["_id"]},
        sort=[("updated_at", -1), ("created_at", -1)],
    )
    if not thread:
        return jsonify({"thread_id": None, "unread_count": 0}), 200

    unread_count = _count_expert_unread_messages(db, thread, oid(uid))
    return jsonify({
        "thread_id": str(thread["_id"]),
        "unread_count": unread_count,
    }), 200


@expert_bp.route("/super-admin-chat/read", methods=["POST"])
@expert_required
def mark_super_admin_chat_read():
    uid = get_jwt_identity()
    db = get_db()
    expert = db.experts.find_one({"user_id": oid(uid)})
    if not expert:
        return jsonify({"error": "Profile not found"}), 404

    thread = db.threads.find_one(
        {"thread_type": "E", "expert_id": expert["_id"]},
        sort=[("updated_at", -1), ("created_at", -1)],
    )
    if not thread:
        return jsonify({"status": "ok", "unread_count": 0}), 200

    now = datetime.utcnow()
    db.threads.update_one(
        {"_id": thread["_id"]},
        {"$set": {"expert_last_read_at": now}},
    )
    return jsonify({
        "status": "ok",
        "thread_id": str(thread["_id"]),
        "unread_count": 0,
        "read_at": now.isoformat(),
    }), 200


@expert_bp.route("/tasks/<question_id>", methods=["GET"])
@expert_required
def task_detail(question_id):
    uid    = get_jwt_identity()
    db     = get_db()
    expert = db.experts.find_one({"user_id": oid(uid)})
    question = db.questions.find_one({
        "_id":                oid(question_id),
        "assigned_expert_id": expert["_id"]
    })
    if not question:
        return jsonify({"error": "Not found"}), 404

    domain_name = _resolve_domain_name(
        db,
        domain_id=question.get("domain_id"),
        fallback_name=question.get("domain")
    )

    return jsonify({
        "_id":          str(question["_id"]),
        "title":        question["title"],
        "description":  question.get("description"),
        "domain":       domain_name,
        "deadline":     str(question["deadline"]) if question.get("deadline") else None,
        "status":       question["status"],
        "expert_payout": question.get("expert_payout"),
        "expert_currency": question.get("expert_currency", "inr"),
    }), 200

@expert_bp.route("/tasks/<question_id>/submit", methods=["POST"])
@expert_required
def submit_task(question_id):
    uid    = get_jwt_identity()
    db     = get_db()
    expert = db.experts.find_one({"user_id": oid(uid)})
    
    question = db.questions.find_one({
        "_id":                oid(question_id),
        "assigned_expert_id": expert["_id"]
    })
    
    if not question:
        return jsonify({"error": "Not found"}), 404
        
    db.questions.update_one(
        {"_id": oid(question_id)},
        {"$set": {"status": "reviewing"}}
    )
    
    # Notify admin
    if question.get("assigned_employee_id"):
        from app.services.notification_service import create_notification
        employee = db.employees.find_one({"_id": question["assigned_employee_id"]})
        if employee:
            from app.tasks.notification_tasks import send_notification_async
            send_notification_async.delay(
                user_id=str(employee["user_id"]),
                notif_type="solution_submitted",
                title="Task Submitted for Review",
                body=f"Expert {expert['name']} has marked the task as done: {question['title']}",
                link=f"/admin/cockpit.html?id={question_id}"
            )
            
    return jsonify({"status": "submitted"}), 200
