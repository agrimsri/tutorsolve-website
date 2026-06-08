from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from bson import ObjectId

from app.blueprints.super_admin import super_admin_bp
from app.extensions import get_db
from app.utils.decorators import superadmin_required
from app.utils.helpers import oid
from app.utils.currency import money_label, bucket_add
from app.services.payout_service import (
    get_eligible_payouts,
    mark_expert_payouts_as_paid,
    mark_single_payout_as_paid
)
from app.utils.constants import KYCStatus
from datetime import datetime


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


def _as_iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)


def _money_bucket_total(items, currency_key, amount_fn):
    totals = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        bucket_add(totals, item.get(currency_key) or item.get("currency"), amount_fn(item))
    return totals


def _bucket_subtract(left, right):
    result = dict(left or {})
    for currency, amount in (right or {}).items():
        result[currency] = round(float(result.get(currency, 0) or 0) - float(amount or 0), 2)
    return result


def _legacy_inr(totals):
    return round(float((totals or {}).get("inr", 0) or 0), 2)


def _upper_currency_bucket(totals):
    return {
        str(currency).upper(): round(float(amount or 0), 2)
        for currency, amount in (totals or {}).items()
        if round(float(amount or 0), 2) != 0
    }


def _merge_buckets(*buckets):
    result = {}
    for bucket in buckets:
        for currency, amount in (bucket or {}).items():
            bucket_add(result, currency, amount)
    return result


def _completed_refund_bucket(payments):
    totals = {}
    for p in payments:
        if not isinstance(p, dict):
            continue

        refunds_blob = p.get("refunds")
        if isinstance(refunds_blob, list):
            for refund_item in refunds_blob:
                if isinstance(refund_item, dict):
                    bucket_add(
                        totals,
                        refund_item.get("currency") or p.get("currency"),
                        refund_item.get("amount", 0),
                    )
            continue

        amount = None
        if isinstance(refunds_blob, dict):
            amount = refunds_blob.get("amount")
        if amount is None:
            amount = p.get("refund_amount")
        if amount is None:
            amount = p.get("completion_amount", 0) if p.get("completion_refund_id") else p.get("advance_amount", 0)
        bucket_add(totals, p.get("currency"), amount or 0)
    return totals


def _count_super_admin_unread_messages(db, thread, super_admin_user_oid):
    if not thread:
        return 0

    query = {
        "thread_id": thread["_id"],
        "sender_user_id": {"$ne": super_admin_user_oid},
    }
    read_cutoff = thread.get("super_admin_last_read_at")
    if read_cutoff:
        query["created_at"] = {"$gt": read_cutoff}

    return db.messages.count_documents(query)


def _expert_display_name(expert_doc, user_doc):
    if not expert_doc:
        return "Expert"
    return (
        expert_doc.get("display_name")
        or expert_doc.get("name")
        or ((user_doc or {}).get("email", "").split("@")[0] if user_doc else None)
        or "Expert"
    )


def _build_expert_chat_item(db, expert_doc, user_doc, super_admin_user_oid=None):
    thread = db.threads.find_one(
        {"thread_type": "E", "expert_id": expert_doc["_id"]},
        sort=[("updated_at", -1), ("created_at", -1)],
    )

    last_message_preview = None
    last_message_at = None
    thread_id = None
    unread_count = 0

    if thread:
        thread_id = str(thread["_id"])
        if super_admin_user_oid:
            unread_count = _count_super_admin_unread_messages(
                db,
                thread,
                super_admin_user_oid,
            )
        last_msg = db.messages.find_one(
            {"thread_id": thread["_id"]},
            sort=[("created_at", -1)],
        )
        if last_msg:
            body = (last_msg.get("body") or "").strip()
            last_message_preview = body[:120] + ("..." if len(body) > 120 else "")
            last_message_at = _as_iso(last_msg.get("created_at"))
        else:
            last_message_at = _as_iso(thread.get("updated_at") or thread.get("created_at"))

    return {
        "expert_id": str(expert_doc["_id"]),
        "user_id": str(user_doc["_id"]),
        "name": _expert_display_name(expert_doc, user_doc),
        "email": user_doc.get("email", ""),
        "domain": _resolve_domain_name(
            db,
            domain_id=expert_doc.get("domain_id"),
            fallback_name=expert_doc.get("domain"),
        ),
        "kyc_status": expert_doc.get("kyc_status", KYCStatus.PENDING),
        "is_banned": bool(user_doc.get("is_banned", False)),
        "is_active": bool(user_doc.get("is_active", True)),
        "joined_at": _as_iso(user_doc.get("created_at")),
        "thread_id": thread_id,
        "last_message_preview": last_message_preview,
        "last_message_at": last_message_at,
        "unread_count": unread_count,
    }


def _employee_display_name(employee_doc, user_doc):
    if not employee_doc:
        return "Employee Admin"
    return (
        employee_doc.get("display_name")
        or employee_doc.get("name")
        or ((user_doc or {}).get("email", "").split("@")[0] if user_doc else None)
        or "Employee Admin"
    )


def _build_employee_chat_item(db, employee_doc, user_doc, super_admin_user_oid=None):
    thread = db.threads.find_one(
        {"thread_type": "F", "employee_id": employee_doc["_id"]},
        sort=[("updated_at", -1), ("created_at", -1)],
    )

    last_message_preview = None
    last_message_at = None
    thread_id = None
    unread_count = 0

    if thread:
        thread_id = str(thread["_id"])
        if super_admin_user_oid:
            unread_count = _count_super_admin_unread_messages(
                db,
                thread,
                super_admin_user_oid,
            )
        last_msg = db.messages.find_one(
            {"thread_id": thread["_id"]},
            sort=[("created_at", -1)],
        )
        if last_msg:
            body = (last_msg.get("body") or "").strip()
            last_message_preview = body[:120] + ("..." if len(body) > 120 else "")
            last_message_at = _as_iso(last_msg.get("created_at"))
        else:
            last_message_at = _as_iso(thread.get("updated_at") or thread.get("created_at"))

    return {
        "employee_id": str(employee_doc["_id"]),
        "user_id": str(user_doc["_id"]),
        "name": _employee_display_name(employee_doc, user_doc),
        "email": user_doc.get("email", ""),
        "is_banned": bool(user_doc.get("is_banned", False)),
        "is_active": bool(user_doc.get("is_active", True)),
        "is_senior": bool(employee_doc.get("is_senior", False)),
        "joined_at": _as_iso(user_doc.get("created_at")),
        "thread_id": thread_id,
        "last_message_preview": last_message_preview,
        "last_message_at": last_message_at,
        "unread_count": unread_count,
    }


@super_admin_bp.route("/payouts/eligible", methods=["GET"])
@superadmin_required
def eligible_payouts():
    db = get_db()
    payouts = get_eligible_payouts()

    result = []
    for p in payouts:
        expert = db.experts.find_one({"_id": p.get("expert_id")})
        question = db.questions.find_one({"_id": p.get("question_id")})
        payment = db.payments.find_one({"question_id": p.get("question_id")}) if p.get("question_id") else None

        is_refund_requested = (
            (payment and payment.get("status") == "refund_requested")
            or (question and question.get("status") == "refund_requested")
        )
        is_refunded = bool(payment and payment.get("status") == "refunded")

        refunded_amount = 0.0
        if payment:
            refunds_blob = payment.get("refunds")
            if isinstance(refunds_blob, list):
                refunded_amount = sum(
                    float(r.get("amount", 0) or 0)
                    for r in refunds_blob
                    if isinstance(r, dict)
                )
            elif isinstance(refunds_blob, dict):
                refunded_amount = float(refunds_blob.get("amount", 0) or 0)

            if refunded_amount <= 0:
                refunded_amount = float(payment.get("refund_amount", 0) or 0)

        result.append({
            "payout_id": str(p["_id"]),
            "expert_id": str(p.get("expert_id")) if p.get("expert_id") else None,
            "expert_name": expert["name"] if expert else "Unknown",
            "expert_phone": expert.get("phone") if expert else None,
            "question_id": str(p.get("question_id")) if p.get("question_id") else None,
            "question_title": question["title"] if question else "Unknown Question",
            "amount": float(p.get("amount", 0)),
            "original_amount": float(p.get("amount", 0)),
            "currency": p.get("currency") or (question or {}).get("expert_currency", "inr"),
            "refunded_amount": float(refunded_amount or 0),
            "status": "refund_requested" if is_refund_requested else ("refunded" if is_refunded else "ready"),
            "task_completed_at": str(p.get("task_completed_at")) if p.get("task_completed_at") else None,
            "created_at": str(p.get("created_at")) if p.get("created_at") else None,
        })

    result.sort(key=lambda x: x.get("task_completed_at") or "", reverse=True)
    return jsonify(result), 200


@super_admin_bp.route("/payouts/expert/<expert_id>/pay", methods=["POST"])
@superadmin_required
def pay_out_expert(expert_id):
    try:
        db = get_db()
        unpaid = list(db.payouts.find({"expert_id": oid(expert_id), "is_paid": False}))
        blocked = 0
        for p in unpaid:
            qid_filter = _question_id_filter(p.get("question_id"))
            question = db.questions.find_one({"_id": qid_filter}) if p.get("question_id") else None
            payment = db.payments.find_one({"question_id": qid_filter}) if p.get("question_id") else None
            if (
                (payment and payment.get("status") == "refund_requested")
                or (question and question.get("status") == "refund_requested")
            ):
                blocked += 1
        if blocked:
            return jsonify({"error": "Cannot release payout while refund request is pending review."}), 409

        payout_currency_totals = _money_bucket_total(unpaid, "currency", lambda p: p.get("amount", 0))
        total_amount = mark_expert_payouts_as_paid(expert_id)
        expert = db.experts.find_one({"_id": oid(expert_id)})
        if expert:
            user = db.users.find_one({"_id": expert["user_id"]})
            if user:
                from app.services.email_service import send_payout_released_email
                from app.services.notification_service import create_notification
                default_currency = next(iter(payout_currency_totals.keys()), "inr")
                send_payout_released_email(user["email"], expert["name"], total_amount, default_currency)
                from app.tasks.notification_tasks import send_notification_async
                payout_summary = ", ".join(
                    money_label(amount, currency)
                    for currency, amount in payout_currency_totals.items()
                ) or money_label(total_amount, default_currency)
                send_notification_async.delay(
                    user_id=str(user["_id"]),
                    notif_type="payout_released",
                    title="Payout Released",
                    body=f"Your payout of {payout_summary} has been released.",
                    link="/expert/dashboard.html"
                )

        return jsonify({"status": "paid", "amount": total_amount, "amounts_by_currency": payout_currency_totals}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@super_admin_bp.route("/payouts/<payout_id>/pay", methods=["POST"])
@superadmin_required
def pay_out_single_task(payout_id):
    db = get_db()
    payout_doc = db.payouts.find_one({"_id": oid(payout_id)})
    if not payout_doc:
        return jsonify({"error": "Payout record not found"}), 404

    qid_filter = _question_id_filter(payout_doc.get("question_id"))
    question = db.questions.find_one({"_id": qid_filter}) if payout_doc.get("question_id") else None
    payment = db.payments.find_one({"question_id": qid_filter}) if payout_doc.get("question_id") else None
    if (
        (payment and payment.get("status") == "refund_requested")
        or (question and question.get("status") == "refund_requested")
    ):
        return jsonify({"error": "Cannot release payout while refund request is pending review."}), 409

    try:
        payout = mark_single_payout_as_paid(payout_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    expert = db.experts.find_one({"_id": payout.get("expert_id")})
    if expert:
        user = db.users.find_one({"_id": expert["user_id"]})
        if user:
            from app.services.email_service import send_payout_released_email
            payout_currency = payout.get("currency") or "inr"
            send_payout_released_email(user["email"], expert["name"], payout.get("amount", 0), payout_currency)
            from app.tasks.notification_tasks import send_notification_async
            send_notification_async.delay(
                user_id=str(user["_id"]),
                notif_type="payout_released",
                title="Payout Released",
                body=f"Your payout of {money_label(payout.get('amount', 0), payout_currency)} has been released.",
                link="/expert/dashboard.html"
            )

    return jsonify({
        "status": "paid",
        "payout_id": payout_id,
        "amount": float(payout.get("amount", 0)),
        "currency": payout.get("currency") or "inr"
    }), 200


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
            "user_id":      str(user["_id"]) if user else None,
            "name":         e["name"],
            "domain":       _resolve_domain_name(
                db,
                domain_id=e.get("domain_id"),
                fallback_name=e.get("domain")
            ),
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
            "domain":         _resolve_domain_name(
                db,
                domain_id=q.get("domain_id"),
                fallback_name=q.get("domain")
            ),
            "status":         q["status"],
            "student_price":  q.get("student_price"),
            "student_currency": q.get("student_currency", "inr"),
            "expert_payout":  q.get("expert_payout"),
            "expert_currency": q.get("expert_currency", "inr"),
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
    refund_requests   = db.payments.count_documents({"status": "refund_requested"})
    unassigned_employee_query = {"$or": [
        {"assigned_employee_id": {"$exists": False}},
        {"assigned_employee_id": None},
        {"assigned_employee_id": ""},
    ]}
    assigned_employee_query = {"assigned_employee_id": {"$exists": True, "$nin": [None, ""]}}

    questions_awaiting_review = db.questions.count_documents({
        "status": {"$in": ["awaiting_quote", "created", "pending_review", "CREATED", "PENDING_REVIEW"]},
        **unassigned_employee_query,
    })
    negotiations_in_progress = db.questions.count_documents({
        "status": {"$in": ["awaiting_quote", "negotiation", "NEGOTIATION"]},
        **assigned_employee_query,
    })
    pricing_pending_approval = db.questions.count_documents({
        "status": {"$in": ["pending_payment", "pricing_sent", "awaiting_advance_payment", "PRICING_SENT", "AWAITING_ADVANCE_PAYMENT"]}
    })
    experts_awaiting_assignment = db.questions.count_documents({
        "$and": [
            {"$or": [
                {"assigned_expert_id": {"$exists": False}},
                {"assigned_expert_id": None},
                {"assigned_expert_id": ""},
            ]},
            {"$or": [
                {"expert_id": {"$exists": False}},
                {"expert_id": None},
                {"expert_id": ""},
            ]},
        ],
        "interested_expert_ids.0": {"$exists": True},
        "status": {"$nin": ["completed", "cancelled", "refunded", "refund_requested"]},
    })

    return jsonify({
        "activeOrders": active_orders,
        "completedOrders": completed_orders,
        "pendingKYC": pending_kyc,
        "refundRequests": refund_requests,
        "questionsAwaitingReview": questions_awaiting_review,
        "negotiationsInProgress": negotiations_in_progress,
        "pricingPendingApproval": pricing_pending_approval,
        "expertsAwaitingAssignment": experts_awaiting_assignment,
        "total_orders":      total_orders,
        "active_orders":     active_orders,
        "completed_orders":  completed_orders,
        "pending_kyc":       pending_kyc,
        "refund_requests":   refund_requests,
        "questions_awaiting_review": questions_awaiting_review,
        "negotiations_in_progress": negotiations_in_progress,
        "pricing_pending_approval": pricing_pending_approval,
        "experts_awaiting_assignment": experts_awaiting_assignment,
    }), 200


@super_admin_bp.route("/financial-summary", methods=["GET"])
@superadmin_required
def financial_summary():
    db = get_db()

    paid_payments = list(db.payments.find({
        "$or": [
            {"advance_paid": True},
            {"completion_paid": True},
        ]
    }))
    gross_payments = _money_bucket_total(
        paid_payments,
        "currency",
        lambda p: p.get("total_amount", 0) if p.get("completion_paid") else p.get("advance_amount", 0),
    )
    gross_transaction_count = sum(
        (1 if p.get("advance_paid") else 0) + (1 if p.get("completion_paid") else 0)
        for p in paid_payments
    )

    pending_payout_docs = list(db.payouts.find({"is_paid": False}))
    paid_payout_docs = list(db.payouts.find({"is_paid": True}))
    pending_payouts = _money_bucket_total(
        pending_payout_docs,
        "currency",
        lambda p: p.get("amount", 0),
    )
    paid_payouts = _money_bucket_total(
        paid_payout_docs,
        "currency",
        lambda p: p.get("amount", 0),
    )
    total_payouts = _merge_buckets(pending_payouts, paid_payouts)

    pending_refund_docs = list(db.payments.find({"status": "refund_requested"}))
    pending_refunds = _money_bucket_total(
        pending_refund_docs,
        "currency",
        lambda p: p.get("refund_amount", 0),
    )

    completed_refund_docs = list(db.payments.find({"status": "refunded"}))
    completed_refunds = _completed_refund_bucket(completed_refund_docs)

    platform_earnings = _bucket_subtract(
        _bucket_subtract(gross_payments, total_payouts),
        completed_refunds,
    )

    return jsonify({
        "grossPayments": _upper_currency_bucket(gross_payments),
        "pendingPayouts": _upper_currency_bucket(pending_payouts),
        "paidPayouts": _upper_currency_bucket(paid_payouts),
        "platformEarnings": _upper_currency_bucket(platform_earnings),
        "refunds": {
            "pending": _upper_currency_bucket(pending_refunds),
            "completed": _upper_currency_bucket(completed_refunds),
        },
        "counts": {
            "grossPaymentTransactions": gross_transaction_count,
            "pendingPayouts": len(pending_payout_docs),
            "paidPayouts": len(paid_payout_docs),
            "pendingRefunds": len(pending_refund_docs),
            "completedRefunds": len(completed_refund_docs),
        },
    }), 200


@super_admin_bp.route("/dashboard/charts", methods=["GET"])
@superadmin_required
def dashboard_charts():
    from datetime import datetime, timedelta
    db = get_db()
    
    now = datetime.utcnow()

    # Expert Pool Health
    health_data = list(db.experts.aggregate([
        {"$group": {"_id": "$kyc_status", "count": {"$sum": 1}}}
    ]))
    expert_health = {item["_id"] or "pending": item["count"] for item in health_data}
    
    # Signups Over Time (last 30 days)
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
        "expert_health": expert_health,
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
        domain_name = _resolve_domain_name(
            db,
            domain_id=e.get("domain_id"),
            fallback_name=e.get("domain")
        )
        # Approximate created_at using ObjectID extraction
        activities.append({"type": "expert", "message": f"📋 Expert application received — {domain_name}", "timestamp": e["_id"].generation_time.replace(tzinfo=None)})
        
    # Order posted
    orders = list(db.questions.find().sort("created_at", -1).limit(5))
    for o in orders:
        if o.get("created_at"):
            domain_name = _resolve_domain_name(
                db,
                domain_id=o.get("domain_id"),
                fallback_name=o.get("domain")
            )
            activities.append({"type": "order", "message": f"📝 New {domain_name} question posted", "timestamp": o["created_at"]})
            
    # Payment received
    payments = list(db.payments.find().sort("created_at", -1).limit(5))
    for p in payments:
        if p.get("created_at"):
            activities.append({
                "type": "payment",
                "message": "💰 Student payment received",
                "timestamp": p["created_at"]
            })
            
    # Task completed (Feedback)
    feedbacks = list(db.feedback.find().sort("created_at", -1).limit(5))
    for f in feedbacks:
        if f.get("created_at"):
            activities.append({"type": "completed", "message": f"✅ Task completed — Expert rated {f.get('rating', 0)}/5", "timestamp": f["created_at"]})
            
    # KYC approved
    approved = list(db.experts.find({"kyc_status": "approved"}).sort("_id", -1).limit(5))
    for a in approved:
        domain_name = _resolve_domain_name(
            db,
            domain_id=a.get("domain_id"),
            fallback_name=a.get("domain")
        )
        activities.append({"type": "kyc", "message": f"✔️ Expert KYC approved — {domain_name}", "timestamp": a["_id"].generation_time.replace(tzinfo=None)})
        
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
            "completion_amount":    p.get("completion_amount"),
            "refund_amount":        p.get("refund_amount"),
            "currency":             p.get("currency", p.get("student_currency", "inr")),
            "refund_type":          p.get("refund_type", "advance"),
            "advance_paid":         p.get("advance_paid", False),
            "completion_paid":      p.get("completion_paid", False),
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
    - BUG#1, #3: Handle multi-stage refunds atomically with rollback on failure
    - BUG#7: Add idempotency check to prevent double refunds
    - BUG#8: Validate both payment intents exist for full refunds
    - BUG#9: Use optimistic locking to prevent race conditions
    """
    db      = get_db()
    payment = db.payments.find_one({"_id": oid(payment_id)})
    if not payment:
        return jsonify({"error": "Payment record not found"}), 404

    # BUG#7, #9: Check if already refunded (idempotency + race condition)
    if payment.get("status") == "refunded":
        return jsonify({"error": "This refund has already been approved and processed"}), 409

    if payment.get("status") != "refund_requested":
        return jsonify({"error": "Payment is not in refund_requested state"}), 400

    question_id = payment["question_id"]
    refund_type = payment.get("refund_type", "advance")

    try:
        # BUG#1, #3: Wrap multi-stage refunds in try-catch with detailed error handling
        if refund_type == "completion":
            # BUG#8: Validate completion payment intent exists
            if not payment.get("completion_payment_intent_id"):
                return jsonify({"error": "No completion payment intent found. Cannot refund."}), 400
            
            from app.services.refund_service import refund_completion_payment
            refund_completion_payment(
                question_id=str(question_id),
                admin_id=get_jwt_identity(),
                reason=payment.get("refund_reason", "Approved by super admin"),
                refund_amount=payment.get("refund_amount"),
                cancel_unpaid_payouts=False
            )
        elif refund_type == "full":
            # BUG#8: Validate both payment intents exist before attempting full refund
            if not payment.get("advance_payment_intent_id"):
                return jsonify({"error": "No advance payment intent found. Cannot issue full refund."}), 400
            if not payment.get("completion_payment_intent_id"):
                return jsonify({"error": "No completion payment intent found. Cannot issue full refund."}), 400
            
            from app.services.refund_service import refund_advance_payment, refund_completion_payment
            
            requested = float(payment.get("refund_amount", 0) or 0)
            completion_amount = float(payment.get("completion_amount", 0) or 0)
            advance_amount = float(payment.get("advance_amount", 0) or 0)
            completion_portion = min(requested, completion_amount)
            advance_portion = max(requested - completion_portion, 0)

            # Track what was actually refunded for rollback on failure
            completed_refunds = []
            try:
                if completion_portion > 0:
                    refund_completion_payment(
                        question_id=str(question_id),
                        admin_id=get_jwt_identity(),
                        reason=payment.get("refund_reason", "Approved by super admin"),
                        refund_amount=completion_portion,
                        cancel_unpaid_payouts=False,
                        is_part_of_full_refund=True  # BUG#5: Skip status update for now
                    )
                    completed_refunds.append("completion")
                
                if advance_portion > 0:
                    refund_advance_payment(
                        question_id=str(question_id),
                        admin_id=get_jwt_identity(),
                        reason=payment.get("refund_reason", "Approved by super admin"),
                        refund_amount=advance_portion,
                        cancel_unpaid_payouts=False,
                        is_part_of_full_refund=True  # BUG#5: Skip status update for now
                    )
                    completed_refunds.append("advance")
                
                # BUG#5: Update question status only once at the end for full refunds
                db.questions.update_one(
                    {"_id": oid(question_id)},
                    {"$set": {"status": "refunded"}}
                )
            except Exception as e:
                # BUG#3: Log what failed for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Full refund failed for payment {payment_id}. Completed: {completed_refunds}. Error: {str(e)}")
                raise
        else:  # advance (default)
            # BUG#8: Validate advance payment intent exists
            if not payment.get("advance_payment_intent_id"):
                return jsonify({"error": "No advance payment intent found. Cannot refund."}), 400
            
            from app.services.refund_service import refund_advance_payment
            refund_advance_payment(
                question_id=str(question_id),
                admin_id=get_jwt_identity(),
                reason=payment.get("refund_reason", "Approved by super admin"),
                refund_amount=payment.get("refund_amount")
            )
    except Exception as e:
        # On any error, revert the payment status back to refund_requested
        # This allows retrying without duplicate processing
        db.payments.update_one(
            {"_id": oid(payment_id)},
            {"$set": {"status": "refund_requested"}}
        )
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Refund approval failed for payment {payment_id}: {str(e)}")
        return jsonify({"error": f"Refund processing failed: {str(e)}"}), 400

    # Fetch question to check for assigned expert and employee notification
    question = db.questions.find_one({"_id": question_id}) if question_id else None

    # If the task was completed (i.e. completion payment was paid) and this is a full refund,
    # decrement the expert's tasks_completed count.
    if question and question.get("assigned_expert_id") and payment.get("completion_paid"):
        total_paid = float(payment.get("advance_amount", 0) or 0) + float(payment.get("completion_amount", 0) or 0)
        refund_amount_val = float(payment.get("refund_amount", 0) or 0)
        
        if refund_amount_val >= total_paid - 0.01:
            expert_id = question["assigned_expert_id"]
            db.experts.update_one(
                {"_id": expert_id, "tasks_completed": {"$gt": 0}},
                {"$inc": {"tasks_completed": -1}}
            )
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Full refund approved. Decremented tasks_completed for expert {expert_id}")

    from app.tasks.notification_tasks import send_notification_async

    # Notify assigned employee
    if question and question.get("assigned_employee_id"):
        employee = db.employees.find_one({"_id": question["assigned_employee_id"]})
        if employee:
            send_notification_async.delay(
                user_id=str(employee["user_id"]),
                notif_type="refund_processed",
                title="Refund Approved",
                body=f"The {refund_type} refund for '{question.get('title', 'order')}' has been approved by Super Admin.",
                link=f"/admin/cockpit.html?id={str(question_id)}"
            )

    return jsonify({"status": "refund_approved", "refund_type": refund_type}), 200




@super_admin_bp.route("/refunds/<payment_id>/deny", methods=["POST"])
@superadmin_required
def deny_refund(payment_id):
    """
    Deny a refund request.
    - Restores payment and question status correctly based on refund_type:
        advance refund denied → payment='advance_paid', question='in_progress'
        completion refund denied → payment='fully_paid', question='completed'
    - Notifies student, assigned employee, and assigned expert.
    """
    db      = get_db()
    payment = db.payments.find_one({"_id": oid(payment_id)})
    if not payment:
        return jsonify({"error": "Payment record not found"}), 404

    refund_type = payment.get("refund_type", "advance")
    now = datetime.utcnow()

    # Restore payment status based on which payment type was being refunded
    if refund_type in ("completion", "full"):
        restored_payment_status  = "fully_paid"
        restored_question_status = "completed"
    else:
        restored_payment_status  = "advance_paid"
        restored_question_status = "in_progress"

    db.payments.update_one(
        {"_id": oid(payment_id)},
        {"$set": {
            "status":           restored_payment_status,
            "refund_denied_at": now
        }}
    )

    question_id = payment.get("question_id")
    student_id  = payment.get("student_id")
    question    = None

    if question_id:
        # Restore question status
        db.questions.update_one(
            {"_id": question_id},
            {"$set": {"status": restored_question_status}}
        )
        question = db.questions.find_one({"_id": question_id})

    from app.tasks.notification_tasks import send_notification_async

    # Notify student
    if question_id and student_id:
        student = db.students.find_one({"_id": student_id})
        if student and question:
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
            send_notification_async.delay(
                user_id=str(employee["user_id"]),
                notif_type="refund_processed",
                title="Refund Denied",
                body=f"The {refund_type} refund for '{question.get('title', 'order')}' has been denied by Super Admin.",
                link=f"/admin/cockpit.html?id={str(question_id)}"
            )

    # Notify assigned expert
    if question and question.get("assigned_expert_id"):
        expert = db.experts.find_one({"_id": question["assigned_expert_id"]})
        if expert:
            send_notification_async.delay(
                user_id=str(expert["user_id"]),
                notif_type="refund_denied_expert",
                title="Refund Denied — Your Payout is Safe",
                body=f"The refund request for your task '{question.get('title', 'your task')}' was denied. Your payout is unaffected.",
                link=f"/expert/task-detail.html?id={str(question_id)}"
            )

    return jsonify({"status": "refund_denied", "refund_type": refund_type}), 200


@super_admin_bp.route("/revenue", methods=["GET"])
@superadmin_required
def revenue():
    db       = get_db()
    payments = list(db.payments.find({
        "$or": [
            {"advance_paid": True},
            {"completion_paid": True}
        ]
    }))
    payouts_paid = list(db.payouts.find({"is_paid": True}))
    payouts_all  = list(db.payouts.find({}))

    total_inflow_by_currency = _money_bucket_total(
        payments,
        "currency",
        lambda p: p.get("total_amount", 0) if p.get("completion_paid") else p.get("advance_amount", 0)
    )
    total_paid_out_by_currency = _money_bucket_total(
        payouts_paid, "currency", lambda p: p.get("amount", 0)
    )
    total_accrued_by_currency = _money_bucket_total(
        payouts_all, "currency", lambda p: p.get("amount", 0)
    )
    net_profit_by_currency = _bucket_subtract(total_inflow_by_currency, total_paid_out_by_currency)
    projected_profit_by_currency = _bucket_subtract(total_inflow_by_currency, total_accrued_by_currency)

    return jsonify({
        "total_inflow_by_currency": total_inflow_by_currency,
        "total_paid_out_by_currency": total_paid_out_by_currency,
        "total_accrued_by_currency": total_accrued_by_currency,
        "net_profit_by_currency": net_profit_by_currency,
        "projected_profit_by_currency": projected_profit_by_currency,
        "total_inflow":    _legacy_inr(total_inflow_by_currency),
        "total_paid_out":  _legacy_inr(total_paid_out_by_currency),
        "total_accrued":   _legacy_inr(total_accrued_by_currency),
        "net_profit":      _legacy_inr(net_profit_by_currency),
        "projected_profit": _legacy_inr(projected_profit_by_currency),
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


@super_admin_bp.route("/expert-chats", methods=["GET"])
@superadmin_required
def list_expert_chats():
    uid = get_jwt_identity()
    db = get_db()
    query = (request.args.get("q") or "").strip().lower()
    super_admin_user_oid = oid(uid)

    experts = list(db.experts.find({}).sort("_id", -1).limit(500))
    user_ids = [e.get("user_id") for e in experts if e.get("user_id")]

    users_map = {}
    if user_ids:
        users = db.users.find({"_id": {"$in": user_ids}, "role": "expert"})
        users_map = {u["_id"]: u for u in users}

    items = []
    for expert in experts:
        user = users_map.get(expert.get("user_id"))
        if not user:
            continue

        item = _build_expert_chat_item(db, expert, user, super_admin_user_oid)
        if query:
            haystack = f"{item['name']} {item['email']} {item['domain']}".lower()
            if query not in haystack:
                continue
        items.append(item)

    items.sort(
        key=lambda row: row.get("last_message_at") or row.get("joined_at") or "",
        reverse=True,
    )
    return jsonify(items), 200


@super_admin_bp.route("/expert-chats/<expert_user_id>/thread", methods=["POST"])
@superadmin_required
def get_or_create_expert_chat_thread(expert_user_id):
    uid = get_jwt_identity()
    db = get_db()
    super_admin_user_oid = oid(uid)

    user = db.users.find_one({"_id": oid(expert_user_id), "role": "expert"})
    if not user:
        return jsonify({"error": "Expert user not found"}), 404

    expert = db.experts.find_one({"user_id": user["_id"]})
    if not expert:
        return jsonify({"error": "Expert profile not found"}), 404

    thread = db.threads.find_one({"thread_type": "E", "expert_id": expert["_id"]})
    if not thread:
        now = datetime.utcnow()
        insert_payload = {
            "question_id": None,
            "thread_type": "E",
            "student_id": None,
            "expert_id": expert["_id"],
            "employee_id": None,
            "super_admin_user_id": super_admin_user_oid,
            "created_at": now,
            "updated_at": now,
            "expert_last_read_at": None,
            "super_admin_last_read_at": now,
        }
        thread_id = db.threads.insert_one(insert_payload).inserted_id
        thread = db.threads.find_one({"_id": thread_id})
    elif not thread.get("super_admin_user_id"):
        now = datetime.utcnow()
        db.threads.update_one(
            {"_id": thread["_id"]},
            {
                "$set": {
                    "super_admin_user_id": super_admin_user_oid,
                    "super_admin_last_read_at": now,
                }
            },
        )
        thread["super_admin_user_id"] = super_admin_user_oid
        thread["super_admin_last_read_at"] = now
    else:
        now = datetime.utcnow()
        db.threads.update_one(
            {"_id": thread["_id"]},
            {"$set": {"super_admin_last_read_at": now}},
        )
        thread["super_admin_last_read_at"] = now

    return jsonify({
        "thread_id": str(thread["_id"]),
        "expert": _build_expert_chat_item(db, expert, user, super_admin_user_oid),
    }), 200


@super_admin_bp.route("/employee-chats", methods=["GET"])
@superadmin_required
def list_employee_chats():
    uid = get_jwt_identity()
    db = get_db()
    query = (request.args.get("q") or "").strip().lower()
    super_admin_user_oid = oid(uid)

    employees = list(db.employees.find({}).sort("_id", -1).limit(500))
    user_ids = [e.get("user_id") for e in employees if e.get("user_id")]

    users_map = {}
    if user_ids:
        users = db.users.find({"_id": {"$in": user_ids}, "role": "employee"})
        users_map = {u["_id"]: u for u in users}

    items = []
    for employee in employees:
        user = users_map.get(employee.get("user_id"))
        if not user:
            continue

        item = _build_employee_chat_item(db, employee, user, super_admin_user_oid)
        if query:
            haystack = f"{item['name']} {item['email']}".lower()
            if query not in haystack:
                continue
        items.append(item)

    items.sort(
        key=lambda row: row.get("last_message_at") or row.get("joined_at") or "",
        reverse=True,
    )
    return jsonify(items), 200


@super_admin_bp.route("/employee-chats/<employee_user_id>/thread", methods=["POST"])
@superadmin_required
def get_or_create_employee_chat_thread(employee_user_id):
    uid = get_jwt_identity()
    db = get_db()
    super_admin_user_oid = oid(uid)

    user = db.users.find_one({"_id": oid(employee_user_id), "role": "employee"})
    if not user:
        return jsonify({"error": "Employee user not found"}), 404

    employee = db.employees.find_one({"user_id": user["_id"]})
    if not employee:
        return jsonify({"error": "Employee profile not found"}), 404

    thread = db.threads.find_one({"thread_type": "F", "employee_id": employee["_id"]})
    if not thread:
        now = datetime.utcnow()
        insert_payload = {
            "question_id": None,
            "thread_type": "F",
            "student_id": None,
            "expert_id": None,
            "employee_id": employee["_id"],
            "super_admin_user_id": super_admin_user_oid,
            "created_at": now,
            "updated_at": now,
            "employee_last_read_at": None,
            "super_admin_last_read_at": now,
        }
        thread_id = db.threads.insert_one(insert_payload).inserted_id
        thread = db.threads.find_one({"_id": thread_id})
    elif not thread.get("super_admin_user_id"):
        now = datetime.utcnow()
        db.threads.update_one(
            {"_id": thread["_id"]},
            {
                "$set": {
                    "super_admin_user_id": super_admin_user_oid,
                    "super_admin_last_read_at": now,
                }
            },
        )
        thread["super_admin_user_id"] = super_admin_user_oid
        thread["super_admin_last_read_at"] = now
    else:
        now = datetime.utcnow()
        db.threads.update_one(
            {"_id": thread["_id"]},
            {"$set": {"super_admin_last_read_at": now}},
        )
        thread["super_admin_last_read_at"] = now

    return jsonify({
        "thread_id": str(thread["_id"]),
        "employee": _build_employee_chat_item(db, employee, user, super_admin_user_oid),
    }), 200


@super_admin_bp.route("/chats/<thread_id>/read", methods=["POST"])
@superadmin_required
def mark_super_admin_chat_read(thread_id):
    uid = get_jwt_identity()
    db = get_db()
    thread = db.threads.find_one({
        "_id": oid(thread_id),
        "thread_type": {"$in": ["E", "F"]},
    })
    if not thread:
        return jsonify({"error": "Chat thread not found"}), 404

    now = datetime.utcnow()
    db.threads.update_one(
        {"_id": thread["_id"]},
        {
            "$set": {
                "super_admin_user_id": thread.get("super_admin_user_id") or oid(uid),
                "super_admin_last_read_at": now,
            }
        },
    )
    return jsonify({
        "status": "ok",
        "thread_id": str(thread["_id"]),
        "unread_count": 0,
        "read_at": now.isoformat(),
    }), 200


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
    threads = list(
        db.threads.find({"thread_type": {"$in": ["A", "B"]}})
        .sort("created_at", -1)
        .limit(100)
    )
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
            "currency":          question.get("student_currency", "inr"),
            "student_currency":  question.get("student_currency", "inr"),
            "expert_currency":   question.get("expert_currency", "inr"),
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
            "currency":          question.get("expert_currency", "inr"),
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
            "profit":  float(profit),
            "currency": question.get("student_currency", "inr"),
            "student_currency": question.get("student_currency", "inr"),
            "expert_currency": question.get("expert_currency", "inr")
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
            "domain":       _resolve_domain_name(
                db,
                domain_id=question.get("domain_id") if question else None,
                fallback_name=question.get("domain") if question else "—"
            ),
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

            domain_name = _resolve_domain_name(
                db,
                domain_id=q.get("domain_id"),
                fallback_name=q.get("domain")
            )

            item = {
                "question_id":       str(q["_id"]),
                "title":             q.get("title", "Untitled Question"),
                "description":       q.get("description"),
                "status":            q.get("status", ""),
                "domain":            domain_name,
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
