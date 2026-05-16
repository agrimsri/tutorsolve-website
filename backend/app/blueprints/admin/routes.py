from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from datetime import datetime

from app.blueprints.admin import admin_bp
from app.extensions import get_db
from app.utils.decorators import admin_required
from app.utils.helpers import oid, to_str_id
from app.services.diamond_engine import set_price_quote, assign_expert


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

    for q in questions:
        has_thread_a = db.threads.count_documents({
            "question_id": q["_id"],
            "thread_type": "A"
        }, limit=1) > 0

        result.append({
            "_id":            str(q["_id"]),
            "title":          q["title"],
            "domain":         q["domain"],
            "status":         q["status"],
            "student_price":  q.get("student_price"),
            "price_approved": q.get("price_approved", False),
            "has_thread_a":   has_thread_a,
            "assigned_expert_id": str(q["assigned_expert_id"]) if q.get("assigned_expert_id") else None,
            "created_at":     str(q["created_at"]),
        })

    return jsonify(result), 200


@admin_bp.route("/orders/<question_id>/quote", methods=["POST"])
@admin_required
def set_quote(question_id):
    data = request.get_json()
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
    
    from app.services.diamond_engine import set_price_quote
    set_price_quote(question_id, data["student_price"], data["expert_payout"])
    
    # Auto-approve the price (replaces Maker-Checker flow)
    from app.services.diamond_engine import approve_price
    approve_price(question_id)

    # Sync with payments record
    from app.services.payment_service import ensure_payment_record
    ensure_payment_record(question_id, data["student_price"], question["student_id"])

    from app.services.email_service import send_price_quote_email
    
    if question:
        student_price = float(data.get("student_price") or 0)
        expert_payout = float(data.get("expert_payout") or 0)

        # Send predefined message to Thread A (student ↔ admin)
        thread_a = db.threads.find_one({
            "question_id": oid(question_id),
            "thread_type": "A"
        })
        if thread_a and employee:
            msg_body = (
                f"We've reviewed your question and are pleased to offer you the following:\n\n"
                f"Total Price: ₹{student_price:.2f}\n\n"
                f"Advance (50%): ₹{student_price / 2:.2f} \n\n"
                f"Completion (50%): ₹{student_price - student_price / 2:.2f}\n\n"
                f"Refresh to see the paymnet link."
            )
            if is_update:
                msg_body = (
                    f"**Quote Updated!**\n\n"
                    f"We have updated your quote for this order:\n"
                    f"New Total Price: ₹{student_price:.2f}\n"
                    f"New Advance (50%): ₹{student_price / 2:.2f}\n"
                    f"New Completion (50%): ₹{student_price - student_price / 2:.2f}\n\n"
                    f"Refresh to see the payment link."
                )

            db.messages.insert_one({
                "thread_id":      thread_a["_id"],
                "sender_user_id": employee["user_id"],
                "body":           msg_body,
                "created_at":     datetime.utcnow()
            })
            # Emit via SocketIO using start_background_task to avoid deadlocking
            # the PubSub subscriber greenlet in gevent mode.
            from app.extensions import socketio
            _tid = str(thread_a["_id"])
            _emp_uid = str(employee["user_id"])
            _payload = {
                "thread_id":      _tid,
                "sender_user_id": _emp_uid,
                "sender_role":    "employee",
                "body":           msg_body,
                "created_at":     datetime.utcnow().isoformat(),
            }
            
            def emit_msg():
                try:
                    socketio.emit("new_message", _payload, room=f"thread_{_tid}")
                    print(f"[DEBUG] set_quote: socketio.emit (background) succeeded")
                except Exception as e:
                    print(f"[ERROR] set_quote: socketio.emit (background) FAILED: {e}")

            socketio.start_background_task(emit_msg)

        student = db.students.find_one({"_id": question["student_id"]})
        if student:
            user = db.users.find_one({"_id": student["user_id"]})
            if user:
                send_price_quote_email(user["email"], student["name"], question["title"], student_price)
                from app.tasks.notification_tasks import send_notification_async
                print(f"[DEBUG] set_quote: Dispatching send_notification_async.delay to student user_id={user['_id']}")
                try:
                    send_notification_async.delay(
                        user_id=str(user["_id"]),
                        notif_type="quote_ready",
                        title="Your quote has been updated" if is_update else "Your quote is ready",
                        body=f"\u20b9{student_price:.2f} \u2014 log in to check.",
                        link=f"/student/order-detail.html?id={question_id}"
                    )
                    print(f"[DEBUG] set_quote: send_notification_async.delay dispatched OK")
                except Exception as e:
                    print(f"[ERROR] set_quote: send_notification_async.delay FAILED: {e}")

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
    for e in experts:
        result.append({
            "_id":             str(e["_id"]),
            "name":            e["name"],
            "domain":          e["domain"],
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

    # Get interested experts (anonymized)
    interested = []
    for eid in question.get("interested_expert_ids", []):
        exp = db.experts.find_one({"_id": eid})
        if exp:
            interested.append({
                "_id":             str(exp["_id"]),
                "name":            exp["name"],
                "domain":          exp["domain"],
                "quality_score":   exp.get("quality_score", 0),
                "on_time_rate":    exp.get("on_time_rate", 0),
                "tasks_completed": exp.get("tasks_completed", 0),
            })

    return jsonify({
        "_id":              str(question["_id"]),
        "title":            question["title"],
        "description":      question.get("description"),
        "domain":           question["domain"],
        "status":           question["status"],
        "student_price":    question.get("student_price"),
        "expert_payout":    question.get("expert_payout"),   # Admin CAN see this
        "price_approved":   question.get("price_approved", False),
        "deadline":         str(question["deadline"]) if question.get("deadline") else None,
        "assigned_expert_id": str(question["assigned_expert_id"]) if question.get("assigned_expert_id") else None,
        "assigned_employee_id": str(question["assigned_employee_id"]) if question.get("assigned_employee_id") else None,
        "thread_a_id":      str(thread_a["_id"]) if thread_a else None,
        "thread_b_id":      str(thread_b["_id"]) if thread_b else None,
        "payment":          {
            "advance_paid":    payment.get("advance_paid", False),
            "completion_paid": payment.get("completion_paid", False),
            "advance_amount":  payment.get("advance_amount"),
            "completion_amount": payment.get("completion_amount"),
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


@admin_bp.route("/orders/<question_id>/quote", methods=["GET"])
@admin_required
def get_quote(question_id):
    db       = get_db()
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "student_price":  question.get("student_price"),
        "expert_payout":  question.get("expert_payout"),
        "price_approved": question.get("price_approved", False),
    }), 200


@admin_bp.route("/experts/search", methods=["GET"])
@admin_required
def search_experts():
    db     = get_db()
    query  = request.args.get("q", "").strip()
    domain = request.args.get("domain", "")

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
        # Case-insensitive domain match
        mongo_query["domain"] = {"$regex": f"^{domain}$", "$options": "i"}

    experts = list(db.experts.find(mongo_query).limit(10))
    return jsonify([{
        "_id":             str(e["_id"]),
        "name":            e["name"],
        "domain":          e["domain"],
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
    Requires a 'reason' in the JSON body.
    Can be used proactively by admin or in response to a student refund request.
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

    if not payment.get("advance_paid"):
        return jsonify({"error": "No advance payment made — nothing to refund"}), 400

    advance_amount = payment.get("advance_amount", 0)
    if refund_amount > advance_amount:
        return jsonify({"error": f"Refund amount (₹{refund_amount:.2f}) cannot exceed the advance paid (₹{advance_amount:.2f})"}), 400

    if payment.get("completion_paid"):
        return jsonify({"error": "Order fully paid and completed — cannot initiate refund"}), 400

    now = datetime.utcnow()

    # Escalate to super admin by setting refund_requested
    db.payments.update_one(
        {"question_id": oid(question_id)},
        {"$set": {
            "status":                     "refund_requested",
            "refund_reason":              reason,
            "refund_amount":              refund_amount,
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

    # Notify student
    student = db.students.find_one({"_id": question["student_id"]})
    if student:
        from app.tasks.notification_tasks import send_notification_async
        send_notification_async.delay(
            user_id=str(student["user_id"]),
            notif_type="refund_under_review",
            title="Refund under review",
            body=f"Your refund request for '{question['title']}' is being reviewed.",
            link=f"/student/order-detail.html?id={question_id}"
        )

    # Notify super admins
    super_admins = list(db.super_admins.find({}))
    for sa in super_admins:
        from app.tasks.notification_tasks import send_notification_async
        send_notification_async.delay(
            user_id=str(sa["user_id"]),
            notif_type="refund_requested_super",
            title="Refund Review Required",
            body=f"Admin {employee.get('name', 'N/A')} initiated a refund for order: {question['title']}",
            link=f"/super-admin/financials.html"
        )

    return jsonify({"status": "refund_escalated_to_superadmin"}), 200


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
    domain_counts = list(db.questions.aggregate([
        {"$match": {"assigned_employee_id": emp_id}},
        {"$group": {"_id": "$domain", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]))
    
    orders_by_domain = []
    other_count = 0
    for i, item in enumerate(domain_counts):
        domain_name = item["_id"] or "Unknown"
        if i < 6:
            orders_by_domain.append({"domain": domain_name, "count": item["count"]})
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
    # a. Unassigned (advance paid, no expert)
    # Get questions with advance_paid=True from payments
    advance_paid_qids = [p["question_id"] for p in db.payments.find({"advance_paid": True})]
    unassigned = list(db.questions.find({
        **base_query,
        "_id": {"$in": advance_paid_qids},
        "assigned_expert_id": {"$in": [None, ""]}
    }).limit(10))
    
    for q in unassigned:
        attention_needed.append({
            "_id": str(q["_id"]),
            "title": q["title"],
            "domain": q.get("domain", "Unknown"),
            "status": "unassigned",
            "reason": "Expert not assigned (Advance Paid)",
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
            "domain": q.get("domain", "Unknown"),
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
            "domain": q.get("domain", "Unknown"),
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
