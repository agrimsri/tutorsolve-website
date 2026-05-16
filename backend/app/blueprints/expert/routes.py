from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity

from app.blueprints.expert import expert_bp
from app.extensions import get_db
from app.utils.decorators import expert_required
from app.utils.helpers import oid, to_str_id
from app.utils.constants import KYCStatus


@expert_bp.route("/dashboard", methods=["GET"])
@expert_required
def dashboard():
    uid    = get_jwt_identity()
    db     = get_db()
    expert = db.experts.find_one({"user_id": oid(uid)})
    if not expert:
        return jsonify({"error": "Profile not found"}), 404
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
    domain_name = (expert.get("domain") or "").strip()
    
    query = {
        "status": "awaiting_quote",
        "interested_expert_ids": {"$ne": expert["_id"]}
    }
    
    # Robust matching: Try by ID if available, otherwise by name (case-insensitive, trimmed)
    import re
    if domain_id:
        # Use $or to catch both ID match and Name match (in case ID is missing on question)
        escaped_name = re.escape(domain_name)
        query["$or"] = [
            {"domain_id": domain_id},
            {"domain": {"$regex": f"^{escaped_name}$", "$options": "i"}}
        ]
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
            "domain":      q["domain"],
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
            "domain":       q["domain"],
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
            "domain":       q["domain"],
            "deadline":     str(q["deadline"]) if q.get("deadline") else None,
            "status":       q["status"],
            "expert_payout": q.get("expert_payout"),
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

    return jsonify({
        "_id":          str(question["_id"]),
        "title":        question["title"],
        "description":  question.get("description"),
        "domain":       question["domain"],
        "deadline":     str(question["deadline"]) if question.get("deadline") else None,
        "status":       question["status"],
        "expert_payout": question.get("expert_payout"),
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
