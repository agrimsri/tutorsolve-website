from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity

from app.blueprints.super_admin import super_admin_bp
from app.extensions import get_db
from app.utils.decorators import superadmin_required
from app.utils.helpers import oid
from app.services.payout_service import get_eligible_payouts, mark_expert_payouts_as_paid
from app.utils.constants import KYCStatus
from datetime import datetime

@super_admin_bp.route("/payouts/eligible", methods=["GET"])
@superadmin_required
def eligible_payouts():
    db = get_db()
    payouts = get_eligible_payouts()
    
    # Aggregate by expert
    expert_totals = {}
    for p in payouts:
        eid = str(p["expert_id"])
        if eid not in expert_totals:
            expert_totals[eid] = {
                "expert_id": eid,
                "amount": 0.0,
                "task_count": 0,
                "last_completed": str(p["task_completed_at"])
            }
        expert_totals[eid]["amount"] += p["amount"]
        expert_totals[eid]["task_count"] += 1
        # Keep the latest task_completed_at for reference
        if str(p["task_completed_at"]) > expert_totals[eid]["last_completed"]:
            expert_totals[eid]["last_completed"] = str(p["task_completed_at"])
            
    result = []
    for eid, data in expert_totals.items():
        expert = db.experts.find_one({"_id": oid(eid)})
        data["expert_name"] = expert["name"] if expert else "Unknown"
        result.append(data)
        
    return jsonify(result), 200


@super_admin_bp.route("/payouts/expert/<expert_id>/pay", methods=["POST"])
@superadmin_required
def pay_out_expert(expert_id):
    try:
        total_amount = mark_expert_payouts_as_paid(expert_id)
        
        db = get_db()
        expert = db.experts.find_one({"_id": oid(expert_id)})
        if expert:
            user = db.users.find_one({"_id": expert["user_id"]})
            if user:
                from app.services.email_service import send_payout_released_email
                from app.services.notification_service import create_notification
                send_payout_released_email(user["email"], expert["name"], total_amount)
                from app.tasks.notification_tasks import send_notification_async
                send_notification_async.delay(
                    user_id=str(user["_id"]),
                    notif_type="payout_released",
                    title="Payout Released",
                    body=f"Your payout of ${total_amount:.2f} has been released.",
                    link="/expert/dashboard.html"
                )

        return jsonify({"status": "paid", "amount": total_amount}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@super_admin_bp.route("/experts/pending", methods=["GET"])
@superadmin_required
def pending_experts():
    db      = get_db()
    experts = list(db.experts.find({"kyc_status": KYCStatus.PENDING}))
    result  = []
    for e in experts:
        user = db.users.find_one({"_id": e["user_id"]})
        from app.services.file_service import get_signed_url
        cv_url = get_signed_url(e["cv_url"]) if e.get("cv_url") else None
        id_proof_url = get_signed_url(e["id_proof_url"]) if e.get("id_proof_url") else None

        result.append({
            "_id":          str(e["_id"]),
            "name":         e["name"],
            "domain":       e["domain"],
            "email":        user["email"] if user else "",
            "cv_url":       cv_url,
            "id_proof_url": id_proof_url,
        })
    return jsonify(result), 200


@super_admin_bp.route("/experts/<expert_id>/approve", methods=["POST"])
@superadmin_required
def approve_expert(expert_id):
    db = get_db()
    db.experts.update_one({"_id": oid(expert_id)}, {"$set": {"kyc_status": KYCStatus.APPROVED}})
    
    # Send Approval Email
    expert = db.experts.find_one({"_id": oid(expert_id)})
    if expert:
        user = db.users.find_one({"_id": expert["user_id"]})
        if user and user.get("email"):
            from app.services.email_service import send_kyc_status_email
            from app.services.notification_service import create_notification
            send_kyc_status_email(user["email"], expert["name"], "approved")
            from app.tasks.notification_tasks import send_notification_async
            send_notification_async.delay(
                user_id=str(user["_id"]),
                notif_type="kyc_approved",
                title="Your application is approved",
                body="Congratulations! Your KYC is approved.",
                link="/expert/job-board.html"
            )

    return jsonify({"status": "approved"}), 200



@super_admin_bp.route("/experts/<expert_id>/reject", methods=["POST"])
@superadmin_required
def reject_expert(expert_id):
    db = get_db()
    db.experts.update_one({"_id": oid(expert_id)}, {"$set": {"kyc_status": KYCStatus.REJECTED}})

    expert = db.experts.find_one({"_id": oid(expert_id)})
    if expert:
        user = db.users.find_one({"_id": expert["user_id"]})
        if user and user.get("email"):
            from app.services.email_service import send_kyc_status_email
            from app.services.notification_service import create_notification
            send_kyc_status_email(user["email"], expert["name"], "rejected")
            from app.tasks.notification_tasks import send_notification_async
            send_notification_async.delay(
                user_id=str(user["_id"]),
                notif_type="kyc_rejected",
                title="Your application was not approved",
                body="Unfortunately your KYC application was not approved.",
                link=""
            )

    return jsonify({"status": "rejected"}), 200


@super_admin_bp.route("/users/<user_id>/ban", methods=["POST"])
@superadmin_required
def ban_user(user_id):
    db = get_db()
    db.users.update_one({"_id": oid(user_id)}, {"$set": {"is_banned": True}})
    return jsonify({"status": "banned"}), 200


@super_admin_bp.route("/orders/<question_id>/approve-price", methods=["POST"])
@superadmin_required
def approve_price(question_id):
    from app.services.diamond_engine import approve_price as _approve
    _approve(question_id)
    return jsonify({"status": "price_approved"}), 200


@super_admin_bp.route("/orders/pending-approvals", methods=["GET"])
@superadmin_required
def pending_approvals():
    """All orders that have a price set but not yet approved. No employee filter."""
    db = get_db()
    questions = list(db.questions.find({
        "student_price": {"$ne": None},
        "price_approved": False
    }).sort("created_at", -1))

    result = []
    for q in questions:
        result.append({
            "_id":            str(q["_id"]),
            "title":          q["title"],
            "domain":         q.get("domain"),
            "status":         q["status"],
            "student_price":  q.get("student_price"),
            "expert_payout":  q.get("expert_payout"),
            "price_approved": q.get("price_approved", False),
            "created_at":     str(q["created_at"]),
        })
    return jsonify(result), 200




@super_admin_bp.route("/stats", methods=["GET"])
@superadmin_required
def stats():
    db = get_db()

    total_orders      = db.questions.count_documents({})
    active_orders     = db.questions.count_documents({"status": {"$in": ["awaiting_quote", "pending_payment", "in_progress", "reviewing"]}})
    completed_orders  = db.questions.count_documents({"status": "completed"})
    pending_kyc       = db.experts.count_documents({"kyc_status": "pending"})
    pending_approvals = db.questions.count_documents({
        "student_price": {"$ne": None},
        "price_approved": False
    })

    # Revenue calculation
    payments     = list(db.payments.find({"advance_paid": True}))
    total_inflow = sum(
        (p.get("total_amount", 0) if p.get("completion_paid")
         else p.get("advance_amount", 0))
        for p in payments
    )

    # Cash Basis (Actual transfers)
    payouts_paid = list(db.payouts.find({"is_paid": True}))
    total_paid   = sum(p.get("amount", 0) for p in payouts_paid)
    
    # Accrual Basis (What we owe + what we paid)
    payouts_all = list(db.payouts.find({}))
    total_accrued = sum(p.get("amount", 0) for p in payouts_all)

    net_profit   = round(total_inflow - total_paid, 2)
    projected_profit = round(total_inflow - total_accrued, 2)

    return jsonify({
        "total_orders":      total_orders,
        "active_orders":     active_orders,
        "completed_orders":  completed_orders,
        "pending_kyc":       pending_kyc,
        "pending_approvals": pending_approvals,
        "total_inflow":      round(total_inflow, 2),
        "total_paid_out":    round(total_paid, 2),
        "total_accrued":     round(total_accrued, 2),
        "net_profit":        net_profit,
        "projected_profit":  projected_profit
    }), 200

@super_admin_bp.route("/dashboard/charts", methods=["GET"])
@superadmin_required
def dashboard_charts():
    from dateutil.relativedelta import relativedelta
    from datetime import datetime, timedelta
    db = get_db()
    
    now = datetime.utcnow()
    
    # 1. Monthly Revenue & Margin Comparison (last 12 months for revenue, last 6 for margin)
    twelve_months_ago = datetime(now.year, now.month, 1) - relativedelta(months=11)
    
    # Payments
    payments_data = list(db.payments.aggregate([
        {"$match": {
            "status": {"$in": ["advance_paid", "fully_paid"]},
            "created_at": {"$gte": twelve_months_ago}
        }},
        {"$project": {
            "month": {"$month": "$created_at"},
            "year": {"$year": "$created_at"},
            "amount": {"$cond": [
                {"$eq": ["$status", "fully_paid"]},
                "$total_amount",
                "$advance_amount"
            ]}
        }},
        {"$group": {
            "_id": {"month": "$month", "year": "$year"},
            "revenue": {"$sum": "$amount"}
        }}
    ]))
    
    # Payouts (All accrued)
    payouts_data = list(db.payouts.aggregate([
        {"$match": {
            # We don't have created_at on payouts reliably in older models, assuming task_completed_at
            "task_completed_at": {"$gte": twelve_months_ago}
        }},
        {"$project": {
            "month": {"$month": "$task_completed_at"},
            "year": {"$year": "$task_completed_at"},
            "amount": 1
        }},
        {"$group": {
            "_id": {"month": "$month", "year": "$year"},
            "payout": {"$sum": "$amount"}
        }}
    ]))
    
    monthly_revenue = []
    margin_comparison = []
    
    for i in range(11, -1, -1):
        dt = datetime(now.year, now.month, 1) - relativedelta(months=i)
        month_label = dt.strftime("%b '%y")
        
        rev = sum(item["revenue"] for item in payments_data if item["_id"]["month"] == dt.month and item["_id"]["year"] == dt.year)
        pay = sum(item["payout"] for item in payouts_data if item["_id"]["month"] == dt.month and item["_id"]["year"] == dt.year)
        
        monthly_revenue.append({
            "month": month_label,
            "revenue": float(rev or 0)
        })
        
        if i < 6:
            margin_comparison.append({
                "month": dt.strftime("%b"),
                "revenue": float(rev or 0),
                "payout": float(pay or 0)
            })
            
    # 2. Expert Pool Health
    health_data = list(db.experts.aggregate([
        {"$group": {"_id": "$kyc_status", "count": {"$sum": 1}}}
    ]))
    expert_health = {item["_id"] or "pending": item["count"] for item in health_data}
    
    # 3. Signups Over Time (last 30 days)
    thirty_days_ago = now - timedelta(days=29)
    users_data = list(db.users.aggregate([
        {"$match": {"created_at": {"$gte": thirty_days_ago}, "role": {"$in": ["student", "expert"]}}},
        {"$project": {
            "role": 1,
            "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}
        }},
        {"$group": {
            "_id": {"date": "$date", "role": "$role"},
            "count": {"$sum": 1}
        }}
    ]))
    
    signups_over_time = []
    for i in range(29, -1, -1):
        dt = now - timedelta(days=i)
        dt_str = dt.strftime("%Y-%m-%d")
        
        student_count = sum(item["count"] for item in users_data if item["_id"]["date"] == dt_str and item["_id"]["role"] == "student")
        expert_count = sum(item["count"] for item in users_data if item["_id"]["date"] == dt_str and item["_id"]["role"] == "expert")
        
        signups_over_time.append({
            "date": dt.strftime("%b %-d"),
            "students": student_count,
            "experts": expert_count
        })
        
    return jsonify({
        "monthly_revenue": monthly_revenue,
        "expert_health": expert_health,
        "margin_comparison": margin_comparison,
        "signups_over_time": signups_over_time
    }), 200

@super_admin_bp.route("/activity", methods=["GET"])
@superadmin_required
def get_activity():
    db = get_db()
    # Mocking activity by pulling latest entries from multiple collections
    activities = []
    
    # New students
    students = list(db.users.find({"role": "student"}).sort("created_at", -1).limit(5))
    for s in students:
        if s.get("created_at"):
            activities.append({"type": "student", "message": "👤 New student joined", "timestamp": s["created_at"]})
            
    # New expert applications
    experts = list(db.experts.find().sort("_id", -1).limit(5))
    for e in experts:
        # Approximate created_at using ObjectID extraction
        activities.append({"type": "expert", "message": f"📋 Expert application received — {e.get('domain', 'Unknown')}", "timestamp": e["_id"].generation_time.replace(tzinfo=None)})
        
    # Order posted
    orders = list(db.questions.find().sort("created_at", -1).limit(5))
    for o in orders:
        if o.get("created_at"):
            activities.append({"type": "order", "message": f"📝 New {o.get('domain', 'Unknown')} question posted", "timestamp": o["created_at"]})
            
    # Payment received
    payments = list(db.payments.find().sort("created_at", -1).limit(5))
    for p in payments:
        if p.get("created_at"):
            activities.append({"type": "payment", "message": f"💰 Payment of ${p.get('total_amount', 0):.2f} received", "timestamp": p["created_at"]})
            
    # Task completed (Feedback)
    feedbacks = list(db.feedback.find().sort("created_at", -1).limit(5))
    for f in feedbacks:
        if f.get("created_at"):
            activities.append({"type": "completed", "message": f"✅ Task completed — Expert rated {f.get('rating', 0)}/5", "timestamp": f["created_at"]})
            
    # KYC approved
    approved = list(db.experts.find({"kyc_status": "approved"}).sort("_id", -1).limit(5))
    for a in approved:
        activities.append({"type": "kyc", "message": f"✔️ Expert KYC approved — {a.get('domain', 'Unknown')}", "timestamp": a["_id"].generation_time.replace(tzinfo=None)})
        
    activities.sort(key=lambda x: x["timestamp"], reverse=True)
    
    for a in activities:
        a["timestamp"] = a["timestamp"].isoformat()
        
    return jsonify(activities[:20]), 200


@super_admin_bp.route("/refunds", methods=["GET"])
@superadmin_required
def list_refunds():
    db = get_db()
    payments = list(db.payments.find({"status": "refund_requested"}))
    result   = []
    for p in payments:
        question = db.questions.find_one({"_id": p["question_id"]})
        student  = db.students.find_one({"_id": p["student_id"]})
        result.append({
            "_id":                  str(p["_id"]),
            "question_id":          str(p["question_id"]),
            "question_title":       question["title"] if question else "—",
            "student_name":         student["name"] if student else "—",
            "total_amount":         p.get("total_amount"),
            "advance_amount":       p.get("advance_amount"),
            "refund_amount":        p.get("refund_amount"),
            "advance_paid":         p.get("advance_paid", False),
            "refund_reason":        p.get("refund_reason", "—"),
            "initiated_by_name":    p.get("refund_initiated_by_name", "Student"),
            "refund_requested_at":  str(p.get("refund_requested_at", p.get("created_at", ""))),
            "created_at":           str(p.get("created_at", "")),
        })
    return jsonify(result), 200


@super_admin_bp.route("/refunds/<payment_id>/approve", methods=["POST"])
@superadmin_required
def approve_refund(payment_id):
    """
    Approve a refund request:
    - Issues the actual Stripe refund via refund_service
    - The service handles: DB status updates, reversing total_spent,
      payout cleanup, and student notification.
    """
    db      = get_db()
    payment = db.payments.find_one({"_id": oid(payment_id)})
    if not payment:
        return jsonify({"error": "Payment record not found"}), 404

    question_id = payment["question_id"]

    from app.services.refund_service import refund_advance_payment
    try:
        refund_advance_payment(
            question_id=str(question_id),
            admin_id=get_jwt_identity(),
            reason=payment.get("refund_reason", "Approved by super admin"),
            refund_amount=payment.get("refund_amount")
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    # Notify assigned employee
    question = db.questions.find_one({"_id": question_id})
    if question and question.get("assigned_employee_id"):
        employee = db.employees.find_one({"_id": question["assigned_employee_id"]})
        if employee:
            from app.tasks.notification_tasks import send_notification_async
            send_notification_async.delay(
                user_id=str(employee["user_id"]),
                notif_type="refund_processed",
                title="Refund Approved",
                body=f"The refund for '{question.get('title', 'order')}' has been approved by Super Admin.",
                link=f"/admin/cockpit.html?id={str(question_id)}"
            )

    return jsonify({"status": "refund_approved"}), 200



@super_admin_bp.route("/refunds/<payment_id>/deny", methods=["POST"])
@superadmin_required
def deny_refund(payment_id):
    """
    Deny a refund request — restore payment to advance_paid status
    and notify the student the refund was not approved.
    """
    db      = get_db()
    payment = db.payments.find_one({"_id": oid(payment_id)})
    if not payment:
        return jsonify({"error": "Payment record not found"}), 404

    # Restore payment status to advance_paid
    db.payments.update_one(
        {"_id": oid(payment_id)},
        {"$set": {
            "status":         "advance_paid",
            "refund_denied_at": datetime.utcnow()
        }}
    )

    # Notify student
    question_id = payment.get("question_id")
    student_id  = payment.get("student_id")
    question    = None
    if question_id and student_id:
        question = db.questions.find_one({"_id": question_id})
        student  = db.students.find_one({"_id": student_id})
        if student and question:
            from app.tasks.notification_tasks import send_notification_async
            send_notification_async.delay(
                user_id=str(student["user_id"]),
                notif_type="refund_denied",
                title="Refund Not Approved",
                body=f"Your refund request for '{question.get('title', 'your order')}' was not approved. The order continues.",
                link=f"/student/order-detail.html?id={str(question_id)}"
            )

    # Notify assigned employee
    if question and question.get("assigned_employee_id"):
        employee = db.employees.find_one({"_id": question["assigned_employee_id"]})
        if employee:
            from app.tasks.notification_tasks import send_notification_async
            send_notification_async.delay(
                user_id=str(employee["user_id"]),
                notif_type="refund_processed",
                title="Refund Denied",
                body=f"The refund for '{question.get('title', 'order')}' has been denied by Super Admin.",
                link=f"/admin/cockpit.html?id={str(question_id)}"
            )

    return jsonify({"status": "refund_denied"}), 200


@super_admin_bp.route("/revenue", methods=["GET"])
@superadmin_required
def revenue():
    db       = get_db()
    payments = list(db.payments.find({"advance_paid": True}))
    payouts_paid = list(db.payouts.find({"is_paid": True}))
    payouts_all  = list(db.payouts.find({}))

    total_inflow   = sum(p.get("total_amount", 0) for p in payments if p.get("completion_paid"))
    total_inflow  += sum(p.get("advance_amount", 0) for p in payments if p.get("advance_paid") and not p.get("completion_paid"))
    
    total_paid_out = sum(p.get("amount", 0) for p in payouts_paid)
    total_accrued  = sum(p.get("amount", 0) for p in payouts_all)

    return jsonify({
        "total_inflow":    round(total_inflow, 2),
        "total_paid_out":  round(total_paid_out, 2),
        "total_accrued":   round(total_accrued, 2),
        "net_profit":      round(total_inflow - total_paid_out, 2),
        "projected_profit": round(total_inflow - total_accrued, 2),
        "total_orders":    db.questions.count_documents({"status": "completed"}),
    }), 200


@super_admin_bp.route("/users", methods=["GET"])
@superadmin_required
def list_users():
    db   = get_db()
    role = request.args.get("role")   # optional filter

    query = {}
    if role:
        query["role"] = role

    users  = list(db.users.find(query).sort("created_at", -1).limit(200))
    result = []
    for u in users:
        result.append({
            "_id":        str(u["_id"]),
            "email":      u["email"],
            "role":       u["role"],
            "is_banned":  u.get("is_banned", False),
            "is_active":  u.get("is_active", True),
            "created_at": str(u.get("created_at", "")),
        })
    return jsonify(result), 200


@super_admin_bp.route("/users/<user_id>/unban", methods=["POST"])
@superadmin_required
def unban_user(user_id):
    db = get_db()
    db.users.update_one({"_id": oid(user_id)}, {"$set": {"is_banned": False}})
    return jsonify({"status": "unbanned"}), 200


@super_admin_bp.route("/employees/create", methods=["POST"])
@superadmin_required
def create_employee():
    from werkzeug.security import generate_password_hash
    from datetime import datetime
    db   = get_db()
    data = request.get_json()

    email     = (data.get("email") or "").strip().lower()
    name      = (data.get("name") or "").strip()
    password  = data.get("password") or ""

    if not all([email, name, password]):
        return jsonify({"error": "Email, name and password are required"}), 400

    if db.users.count_documents({"email": email}, limit=1):
        return jsonify({"error": "Email already exists"}), 409

    result = db.users.insert_one({
        "email":         email,
        "password_hash": generate_password_hash(password),
        "role":          "employee",
        "is_active":     True,
        "is_banned":     False,
        "created_at":    datetime.utcnow()
    })
    db.employees.insert_one({
        "user_id":   result.inserted_id,
        "name":      name,
        "is_senior": False
    })
    
    # Dispatch welcome email with credentials
    from app.services.email_service import send_employee_welcome_email
    send_employee_welcome_email(email, name, password)
    
    return jsonify({"status": "created", "user_id": str(result.inserted_id)}), 201


@super_admin_bp.route("/users/<user_id>", methods=["DELETE"])
@superadmin_required
def delete_user(user_id):
    db   = get_db()
    user = db.users.find_one({"_id": oid(user_id)})
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Remove from role collection
    role_collections = {
        "student":     "students",
        "expert":      "experts",
        "employee":    "employees",
        "super_admin": "super_admins"
    }
    collection = role_collections.get(user["role"])
    if collection:
        db[collection].delete_one({"user_id": oid(user_id)})

    db.users.delete_one({"_id": oid(user_id)})
    return jsonify({"status": "deleted"}), 200


@super_admin_bp.route("/threads", methods=["GET"])
@superadmin_required
def list_threads():
    db      = get_db()
    threads = list(db.threads.find().sort("created_at", -1).limit(100))
    result  = []
    for t in threads:
        question = db.questions.find_one({"_id": t["question_id"]})
        result.append({
            "_id":          str(t["_id"]),
            "question_id":  str(t["question_id"]),
            "question_title": question["title"] if question else "—",
            "thread_type":  t["thread_type"],
            "created_at":   str(t["created_at"]),
        })
    return jsonify(result), 200


@super_admin_bp.route("/demo/pay-advance/<question_id>", methods=["POST"])
@superadmin_required
def demo_pay_advance(question_id):
    """
    DEMO ONLY — Simulates advance payment for testing.
    Remove this endpoint before going to production.
    """
    from datetime import datetime
    db       = get_db()
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Question not found"}), 404

    if not question.get("price_approved"):
        return jsonify({"error": "Price not approved yet"}), 400

    # Upsert payment record
    existing = db.payments.find_one({"question_id": oid(question_id)})
    advance  = (question.get("student_price") or 0) / 2
    completion = (question.get("student_price") or 0) - advance

    if existing:
        db.payments.update_one(
            {"question_id": oid(question_id)},
            {"$set": {
                "advance_paid":    True,
                "advance_paid_at": datetime.utcnow(),
                "status":          "advance_paid"
            }}
        )
    else:
        db.payments.insert_one({
            "question_id":       oid(question_id),
            "student_id":        question["student_id"],
            "advance_amount":    advance,
            "completion_amount": completion,
            "total_amount":      question.get("student_price", 0),
            "advance_paid":      True,
            "advance_paid_at":   datetime.utcnow(),
            "completion_paid":   False,
            "gateway":           "demo",
            "status":            "advance_paid",
            "created_at":        datetime.utcnow()
        })

    db.questions.update_one(
        {"_id": oid(question_id)},
        {"$set": {"status": "in_progress"}}
    )
    return jsonify({"status": "advance_paid_demo", "question_id": question_id}), 200


@super_admin_bp.route("/demo/pay-completion/<question_id>", methods=["POST"])
@superadmin_required
def demo_pay_completion(question_id):
    """
    DEMO ONLY — Simulates completion payment and unlocks files.
    """
    from datetime import datetime
    db = get_db()
    now = datetime.utcnow()
    
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Question not found"}), 404

    db.payments.update_one(
        {"question_id": oid(question_id)},
        {"$set": {
            "completion_paid":    True,
            "completion_paid_at": now,
            "status":             "fully_paid"
        }}
    )

    expert_payout = question.get("expert_payout", 0)
    if question.get("assigned_expert_id") and expert_payout > 0:
        # Create payout record
        db.payouts.insert_one({
            "question_id":       oid(question_id),
            "expert_id":         question["assigned_expert_id"],
            "amount":            float(expert_payout),
            "is_paid":           False,
            "paid_at":           None,
            "task_completed_at": now,
            "created_at":        now
        })
        
    # Update metrics
    student_price = question.get("student_price", 0)
    profit = (student_price or 0) - (expert_payout or 0)
    db.payments.update_one(
        {"question_id": oid(question_id)},
        {"$set": {
            "revenue": float(student_price),
            "profit":  float(profit)
        }}
    )

    db.files.update_many(
        {"question_id": oid(question_id)},
        {"$set": {"is_locked": False}}
    )
    # Clean up preview files from S3 — no longer needed after full payment
    from app.services.diamond_engine import delete_preview_files
    delete_preview_files(question_id)
    db.questions.update_one(
        {"_id": oid(question_id)},
        {"$set": {"status": "completed"}}
    )
    return jsonify({"status": "completion_paid_demo", "question_id": question_id}), 200


@super_admin_bp.route("/reviews", methods=["GET"])
@superadmin_required
def list_reviews():
    db      = get_db()
    reviews = list(db.reviews.find().sort("created_at", -1).limit(100))
    result  = []
    for r in reviews:
        expert   = db.experts.find_one({"_id": r["expert_id"]})
        question = db.questions.find_one({"_id": r["question_id"]})
        result.append({
            "_id":          str(r["_id"]),
            "rating":       r["rating"],
            "review_text":  r.get("review_text"),
            "expert_name":  expert.get("display_name") if expert else "—",
            "domain":       question["domain"] if question else "—",
            "is_visible":   r.get("is_visible", True),
            "created_at":   str(r["created_at"])
        })
    return jsonify(result), 200


@super_admin_bp.route("/reviews/<review_id>/hide", methods=["POST"])
@superadmin_required
def hide_review(review_id):
    db = get_db()
    db.reviews.update_one({"_id": oid(review_id)}, {"$set": {"is_visible": False}})
    return jsonify({"status": "hidden"}), 200


@super_admin_bp.route("/reviews/<review_id>/show", methods=["POST"])
@superadmin_required
def show_review(review_id):
    db = get_db()
    db.reviews.update_one({"_id": oid(review_id)}, {"$set": {"is_visible": True}})
    return jsonify({"status": "visible"}), 200

@super_admin_bp.route("/spy/employee-questions", methods=["GET"])
@superadmin_required
def spy_employee_questions():
    q = request.args.get("q", "").strip()

    if not q:
        return jsonify([]), 200

    db = get_db()

    # Find users matching partial email
    matched_users = list(db.users.find(
        {"role": "employee", "email": {"$regex": q, "$options": "i"}}
    ))
    user_ids = [u["_id"] for u in matched_users]
    
    # Find employees matching partial name OR matching user_ids
    employees = list(db.employees.find({
        "$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"user_id": {"$in": user_ids}}
        ]
    }))

    if not employees:
        return jsonify([]), 200

    result = []
    for employee in employees:
        questions = list(db.questions.find(
            {"assigned_employee_id": employee["_id"]}
        ).sort("created_at", -1))

        for q in questions:
            student_thread = db.threads.find_one({"question_id": q["_id"], "thread_type": "A"})
            expert_thread  = db.threads.find_one({"question_id": q["_id"], "thread_type": "B"})

            item = {
                "question_id":       str(q["_id"]),
                "title":             q.get("title", "Untitled Question"),
                "description":       q.get("description"),
                "status":            q.get("status", ""),
                "domain":            q.get("domain", ""),
                "created_at":        str(q["created_at"]),
                "employee_name":     employee.get("name", ""),
                "student_thread_id": str(student_thread["_id"]) if student_thread else None,
                "expert_thread_id":  str(expert_thread["_id"]) if expert_thread else None,
            }

            if q["status"] == "completed":
                review = db.reviews.find_one({"question_id": q["_id"]})
                if review:
                    item["student_review"] = review.get("review_text")
                    item["student_rating"] = review.get("rating")

            result.append(item)

    return jsonify(result), 200

@super_admin_bp.route("/spy/search-employees", methods=["GET"])
@superadmin_required
def search_employees_spy():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([]), 200

    db = get_db()
    
    # Find matching users (by email) or employees (by name)
    # First get matching employees by name
    matched_employees = list(db.employees.find(
        {"name": {"$regex": query, "$options": "i"}}
    ).limit(10))
    
    # Get matching users by email that are employees
    matched_users = list(db.users.find(
        {"role": "employee", "email": {"$regex": query, "$options": "i"}}
    ).limit(10))
    
    user_ids_from_users = [u["_id"] for u in matched_users]
    additional_employees = list(db.employees.find(
        {"user_id": {"$in": user_ids_from_users}}
    ))
    
    # Combine and deduplicate by employee _id
    seen_ids = set()
    combined = []
    
    for emp in matched_employees + additional_employees:
        emp_id_str = str(emp["_id"])
        if emp_id_str not in seen_ids:
            seen_ids.add(emp_id_str)
            
            # Fetch user to get email
            user = db.users.find_one({"_id": emp["user_id"]})
            email = user["email"] if user else ""
            
            combined.append({
                "id": emp_id_str,
                "name": emp.get("name", "Unknown"),
                "email": email
            })

    return jsonify(combined[:10]), 200

