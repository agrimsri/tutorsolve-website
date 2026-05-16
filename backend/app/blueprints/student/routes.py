from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from bson import ObjectId
from datetime import datetime, timezone

from app.blueprints.student import student_bp
from app.extensions import get_db
from app.utils.decorators import student_required
from app.utils.helpers import oid, to_str_id
from app.utils.constants import OrderStatus


@student_bp.route("/dashboard", methods=["GET"])
@student_required
def dashboard():
    uid     = get_jwt_identity()
    db      = get_db()
    student = db.students.find_one({"user_id": oid(uid)})
    if not student:
        return jsonify({"error": "Profile not found"}), 404
    student = to_str_id(student)
    student["user_id"] = str(student["user_id"])
    return jsonify(student), 200


@student_bp.route("/dashboard/charts", methods=["GET"])
@student_required
def dashboard_charts():
    from dateutil.relativedelta import relativedelta
    uid     = get_jwt_identity()
    db      = get_db()
    student = db.students.find_one({"user_id": oid(uid)})
    
    # Orders by Status
    pipeline_status = [
        {"$match": {"student_id": student["_id"]}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    status_counts = list(db.questions.aggregate(pipeline_status))
    orders_by_status = {item["_id"]: item["count"] for item in status_counts}

    # Monthly Spending (last 6 months)
    now = datetime.utcnow()
    six_months_ago = datetime(now.year, now.month, 1) - relativedelta(months=5)
    
    pipeline_spending = [
        {"$match": {
            "student_id": student["_id"],
            "status": {"$in": ["fully_paid", "completed", "reviewing", "in_progress"]}, # Assuming we count all orders they paid for
        }},
        {"$lookup": {
            "from": "payments",
            "localField": "_id",
            "foreignField": "question_id",
            "as": "payment"
        }},
        {"$unwind": {"path": "$payment", "preserveNullAndEmptyArrays": True}},
        {"$match": {"payment.advance_paid": True, "created_at": {"$gte": six_months_ago}}},
        {"$project": {
            "month": {"$month": "$created_at"},
            "year": {"$year": "$created_at"},
            "amount": {"$cond": [
                {"$eq": ["$payment.completion_paid", True]},
                "$payment.total_amount",
                "$payment.advance_amount"
            ]}
        }},
        {"$group": {
            "_id": {"month": "$month", "year": "$year"},
            "spent": {"$sum": "$amount"}
        }}
    ]
    spending_data = list(db.questions.aggregate(pipeline_spending))
    
    # Format into last 6 months array
    monthly_spending = []
    for i in range(5, -1, -1):
        dt = datetime(now.year, now.month, 1) - relativedelta(months=i)
        month_label = dt.strftime("%b") # e.g. "Dec"
        # Find spent
        spent = sum(item["spent"] for item in spending_data if item["_id"]["month"] == dt.month and item["_id"]["year"] == dt.year)
        monthly_spending.append({"month": month_label, "spent": float(spent or 0)})
        
    return jsonify({
        "orders_by_status": orders_by_status,
        "monthly_spending": monthly_spending
    }), 200


@student_bp.route("/orders", methods=["GET"])
@student_required
def orders():
    uid       = get_jwt_identity()
    db        = get_db()
    student   = db.students.find_one({"user_id": oid(uid)})
    questions = list(db.questions.find({"student_id": student["_id"]}).sort("created_at", -1))
    
    for q in questions:
        # Remove internal/sensitive fields from being exposed
        q.pop("expert_payout", None)
        q.pop("interested_expert_ids", None)
        q.pop("assigned_employee_id", None)
        
        # Robust serialization of all ObjectIds
        to_str_id(q)
        
    return jsonify(questions), 200


@student_bp.route("/orders", methods=["POST"])
@student_required
def create_order():
    uid  = get_jwt_identity()
    data = request.get_json()
    title    = (data.get("title") or "").strip()
    domain_id = data.get("domain_id")
    domain_name = data.get("domain")  # fallback for landing page auto-post
    desc     = data.get("description")
    deadline_str = data.get("deadline")  # "YYYY-MM-DD" or null
    file_ids = data.get("file_ids") or []

    # Parse deadline string to datetime if provided
    deadline = None
    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Invalid deadline format. Use YYYY-MM-DD"}), 400

    if not title:
        return jsonify({"error": "Title is required"}), 400

    db      = get_db()
    try:
        if domain_id:
            domain_doc = db.domains.find_one({"_id": ObjectId(domain_id)})
        elif domain_name:
            import re
            domain_doc = db.domains.find_one({"name": {"$regex": f"^{re.escape(domain_name)}$", "$options": "i"}})
        else:
            domain_doc = None
            
        if not domain_doc:
            raise ValueError()
    except Exception:
        return jsonify({"error": "Invalid or missing domain"}), 400

    student = db.students.find_one({"user_id": oid(uid)})

    result = db.questions.insert_one({
        "student_id":           student["_id"],
        "title":                title,
        "description":          desc,
        "domain_id":            domain_doc["_id"],
        "domain":               domain_doc["name"],
        "deadline":             deadline,
        "status":               OrderStatus.AWAITING_QUOTE,
        "student_price":        None,
        "expert_payout":        None,
        "price_approved":       False,
        "assigned_expert_id":   None,
        "assigned_employee_id": None,
        "interested_expert_ids": [],
        "created_at":           datetime.utcnow()
    })
    qid = result.inserted_id

    # Link uploaded files
    if file_ids:
        db.files.update_many(
            {"_id": {"$in": [oid(f) for f in file_ids]}},
            {"$set": {"question_id": qid}}
        )

    # Automatically create Thread A (Student <-> Admin) so chat is immediate
    print(f"[DEBUG] create_order: Inserting Thread A for question {qid}")
    db.threads.insert_one({
        "question_id": qid,
        "thread_type": "A",
        "student_id":  student["_id"],
        "expert_id":   None,
        "employee_id": None,
        "created_at":  datetime.utcnow()
    })

    # Trigger expert broadcast immediately
    from app.services.diamond_engine import broadcast_question
    broadcast_question(qid)

    from app.tasks.notification_tasks import notify_new_order_task
    print(f"[DEBUG] create_order: Dispatching notify_new_order_task.delay for question {qid}")
    try:
        notify_new_order_task.delay(
            question_id=str(qid),
            title=title,
            domain_name=domain_doc["name"]
        )
        print(f"[DEBUG] create_order: notify_new_order_task.delay dispatched OK")
    except Exception as e:
        print(f"[ERROR] create_order: notify_new_order_task.delay FAILED: {e}")

    # Increment student's total_orders count
    db.students.update_one(
        {"_id": student["_id"]},
        {"$inc": {"total_orders": 1}}
    )

    return jsonify({"question_id": str(qid)}), 201


@student_bp.route("/orders/<question_id>", methods=["PUT"])
@student_required
def edit_order(question_id):
    uid  = get_jwt_identity()
    data = request.get_json()
    db   = get_db()

    student  = db.students.find_one({"user_id": oid(uid)})
    question = db.questions.find_one({"_id": oid(question_id), "student_id": student["_id"]})

    if not question:
        return jsonify({"error": "Question not found"}), 404

    # Optimization: Only allow edits if status is awaiting_quote
    if question.get("status") != OrderStatus.AWAITING_QUOTE:
        return jsonify({"error": "Cannot edit question after price is set or payment is done"}), 400

    title    = data.get("title")
    domain_id = data.get("domain_id")
    desc     = data.get("description")
    deadline_str = data.get("deadline")

    update_payload = {}
    if title:
        update_payload["title"] = title.strip()
    if desc is not None:
        update_payload["description"] = desc.strip()
    if domain_id:
        domain_doc = db.domains.find_one({"_id": oid(domain_id)})
        if domain_doc:
            update_payload["domain_id"] = domain_doc["_id"]
            update_payload["domain"]    = domain_doc["name"]
    if deadline_str:
        try:
            update_payload["deadline"] = datetime.strptime(deadline_str, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Invalid deadline format"}), 400

    if update_payload:
        db.questions.update_one({"_id": oid(question_id)}, {"$set": update_payload})

    return jsonify({"status": "updated"}), 200



@student_bp.route("/orders/<question_id>", methods=["GET"])
@student_required
def order_detail(question_id):
    uid     = get_jwt_identity()
    db      = get_db()
    student = db.students.find_one({"user_id": oid(uid)})
    question = db.questions.find_one({
        "_id":        oid(question_id),
        "student_id": student["_id"]
    })
    if not question:
        return jsonify({"error": "Not found"}), 404

    # Optimization: Only sync payment session if the user just returned from Stripe
    # or if the order is in a state where payment might have happened but not synced.
    payment_success_flag = request.args.get("payment") == "success"
    if payment_success_flag or (question.get("status") in ("reviewing", "completed") and not question.get("price_approved", False)):
         from app.services.payment_service import sync_payment_session
         sync_payment_session(question_id)

    # Re-fetch payment and question to get the latest status
    payment = db.payments.find_one({"question_id": oid(question_id)})
    question = db.questions.find_one({"_id": oid(question_id)})

    # Remove internal/sensitive fields from being exposed
    question.pop("expert_payout", None)
    question.pop("interested_expert_ids", None)
    question.pop("assigned_employee_id", None)

    to_str_id(question)

    if payment:
        question["payment"] = {
            "advance_paid":    payment.get("advance_paid", False),
            "completion_paid": payment.get("completion_paid", False),
            "advance_amount":  payment.get("advance_amount"),
            "completion_amount": payment.get("completion_amount"),
        }
    else:
        question["payment"] = None

    return jsonify(question), 200


@student_bp.route("/orders/<question_id>/files", methods=["POST"])
@student_required
def add_order_files(question_id):
    uid  = get_jwt_identity()
    db   = get_db()
    data = request.json
    file_ids = data.get("file_ids", [])
    
    if not file_ids:
        return jsonify({"error": "No files provided"}), 400
    
    student = db.students.find_one({"user_id": oid(uid)})
    question = db.questions.find_one({
        "_id":        oid(question_id),
        "student_id": student["_id"]
    })
    
    if not question:
        return jsonify({"error": "Order not found"}), 404
    
    # Check status — only allow adding files before payment (awaiting_quote or pending_payment)
    # Actually, the user said "till the payment has not been made"
    if question["status"] not in ("awaiting_quote", "pending_payment"):
        return jsonify({"error": "Cannot add files at this stage"}), 403
    
    # Link files
    db.files.update_many(
        {"_id": {"$in": [oid(fid) for fid in file_ids]}, "student_user_id": oid(uid)},
        {"$set": {"question_id": oid(question_id)}}
    )
    
    return jsonify({"status": "files_added"}), 200


@student_bp.route("/orders/<question_id>/thread", methods=["GET"])
@student_required
def get_thread(question_id):
    uid     = get_jwt_identity()
    db      = get_db()
    student = db.students.find_one({"user_id": oid(uid)})
    thread  = db.threads.find_one({
        "question_id": oid(question_id),
        "thread_type": "A",
        "student_id":  student["_id"]
    })
    if not thread:
        return jsonify({
            "error":  "Chat not available yet",
            "reason": "The admin has not started negotiation on this order yet."
        }), 404
    return jsonify({"thread_id": str(thread["_id"])}), 200


@student_bp.route("/orders/<question_id>/request-refund", methods=["POST"])
@student_required
def request_refund(question_id):
    """
    Student requests a refund after paying advance.
    - Only allowed when advance_paid=True and completion_paid=False.
    - Sets payment status to 'refund_requested'.
    - Posts an automated message to Thread A so the admin sees it immediately.
    """
    uid     = get_jwt_identity()
    db      = get_db()
    student = db.students.find_one({"user_id": oid(uid)})

    question = db.questions.find_one({
        "_id":        oid(question_id),
        "student_id": student["_id"]
    })
    if not question:
        return jsonify({"error": "Order not found"}), 404

    payment = db.payments.find_one({"question_id": oid(question_id)})
    if not payment:
        return jsonify({"error": "No payment record found for this order"}), 400

    if not payment.get("advance_paid"):
        return jsonify({"error": "No advance payment has been made yet"}), 400

    if payment.get("completion_paid"):
        return jsonify({"error": "Order is already completed — refund not applicable"}), 400

    if payment.get("status") == "refund_requested":
        return jsonify({"error": "A refund request is already pending"}), 409

    now = datetime.utcnow()

    # DO NOT mark status as refund_requested here anymore.
    # The student only "asks" (sends a message). 
    # The admin formally initiates it after chatting.


    # Post automated chat message to Thread A so admin sees it
    thread_a = db.threads.find_one({
        "question_id": oid(question_id),
        "thread_type": "A"
    })
    if thread_a:
        auto_msg_body = (
            "⚠️ [REFUND REQUEST] The student has requested a refund for this order. "
            "Please review the situation and initiate a refund if valid."
        )
        from app.extensions import socketio
        from app.utils.helpers import oid as _oid
        msg_result = db.messages.insert_one({
            "thread_id":      thread_a["_id"],
            "sender_user_id": student["user_id"],   # sent as student
            "body":           auto_msg_body,
            "is_system":      True,
            "created_at":     now
        })
        _payload = {
            "_id":            str(msg_result.inserted_id),
            "thread_id":      str(thread_a["_id"]),
            "sender_user_id": str(student["user_id"]),
            "body":           auto_msg_body,
            "is_system":      True,
            "created_at":     now.isoformat()
        }
        socketio.start_background_task(
            lambda: socketio.emit("new_message", _payload, room=f"thread_{thread_a['_id']}")
        )

    # Notify assigned employee
    if question.get("assigned_employee_id"):
        emp = db.employees.find_one({"_id": question["assigned_employee_id"]})
        if emp:
            from app.tasks.notification_tasks import send_notification_async
            send_notification_async.delay(
                user_id=str(emp["user_id"]),
                notif_type="refund_requested",
                title="Refund requested",
                body=f"A student has requested a refund for: {question['title']}",
                link=f"/admin/cockpit.html?id={question_id}"
            )

    return jsonify({"status": "refund_requested"}), 200


@student_bp.route("/feed", methods=["GET"])
@student_required
def global_feed():
    db       = get_db()
    page     = int(request.args.get("page", 1))
    per_page = 20
    skip     = (page - 1) * per_page

    questions = list(
        db.questions.find({"status": "completed"})
        .sort("created_at", -1)
        .skip(skip)
        .limit(per_page)
    )

    result = []
    for q in questions:
        item = {
            "_id":         str(q["_id"]),
            "title":       q["title"],
            "description": q.get("description"),
            "domain":      q["domain"],
            "status":      q["status"],
            "created_at":  str(q["created_at"])
        }
        if q["status"] == "completed":
            # Admin Feedback (Internal/Public Note)
            feedback = db.feedback.find_one({"question_id": q["_id"]})
            if feedback:
                item["public_note"] = feedback.get("public_note")
                item["grade"]       = feedback.get("grade")
            
            # Student Review (Public Review)
            review = db.reviews.find_one({"question_id": q["_id"]})
            if review:
                item["student_review"] = review.get("review_text")
                item["student_rating"] = review.get("rating")
                
        result.append(item)

    return jsonify(result), 200



@student_bp.route("/orders/<question_id>/review", methods=["POST"])
@student_required
def submit_review(question_id):
    identity = get_jwt_identity()
    data     = request.get_json()
    db       = get_db()

    rating      = data.get("rating")
    review_text = (data.get("review_text") or "").strip()

    # Validate rating
    if not rating or not isinstance(rating, int) or rating < 1 or rating > 5:
        return jsonify({"error": "Rating must be an integer between 1 and 5"}), 400

    # Validate review text length
    if len(review_text) > 500:
        return jsonify({"error": "Review must be 500 characters or less"}), 400

    # Verify the order belongs to this student
    student  = db.students.find_one({"user_id": oid(identity)})
    question = db.questions.find_one({
        "_id":        oid(question_id),
        "student_id": student["_id"]
    })
    if not question:
        return jsonify({"error": "Order not found"}), 404

    # Only allow reviews on completed orders
    if question.get("status") != "completed":
        return jsonify({"error": "You can only review a completed order"}), 400

    # Check expert is assigned
    if not question.get("assigned_expert_id"):
        return jsonify({"error": "No expert assigned to this order"}), 400

    # Prevent duplicate reviews
    existing = db.reviews.find_one({"question_id": oid(question_id)})
    if existing:
        return jsonify({"error": "You have already reviewed this order"}), 409

    # Insert review
    db.reviews.insert_one({
        "question_id": oid(question_id),
        "expert_id":   question["assigned_expert_id"],
        "student_id":  student["_id"],
        "rating":      rating,
        "review_text": review_text or None,
        "created_at":  datetime.utcnow(),
        "is_visible":  True
    })

    # Update expert's average_rating and review_count
    expert       = db.experts.find_one({"_id": question["assigned_expert_id"]})
    current_avg  = expert.get("average_rating", 0.0)
    current_count = expert.get("review_count", 0)
    new_count    = current_count + 1
    new_avg      = round(((current_avg * current_count) + rating) / new_count, 2)

    db.experts.update_one(
        {"_id": question["assigned_expert_id"]},
        {"$set": {
            "average_rating": new_avg,
            "review_count":   new_count
        }}
    )

    return jsonify({"status": "review_submitted", "new_average": new_avg}), 201


@student_bp.route("/orders/<question_id>/review", methods=["GET"])
@student_required
def get_review(question_id):
    db     = get_db()
    review = db.reviews.find_one({"question_id": oid(question_id)})
    if not review:
        return jsonify({"reviewed": False}), 200
    return jsonify({
        "reviewed":    True,
        "rating":      review["rating"],
        "review_text": review.get("review_text"),
        "created_at":  str(review["created_at"])
    }), 200
