import stripe
import hmac
import hashlib
from flask import request, jsonify, current_app
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from datetime import datetime

from app.blueprints.api import api_bp
from app.extensions import get_db
from app.utils.helpers import oid
from app.utils.decorators import student_required, admin_required
from app.services.payment_service import (
    create_advance_session,
    create_completion_session,
    ensure_payment_record,
    get_split_amounts
)


# ── Admin initiates payment setup ────────────────────────────────────────────

@api_bp.route("/payments/setup/<question_id>", methods=["POST"])
@api_bp.route("/payments/split-link/<question_id>", methods=["POST"])
@admin_required
def setup_payment(question_id):
    """
    Called by admin after price is approved.
    Creates the payments record with split amounts.
    Returns the advance and completion amounts so the cockpit can display them.
    """
    db       = get_db()
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return jsonify({"error": "Not found"}), 404
    if not question.get("price_approved"):
        return jsonify({"error": "Price must be approved before setting up payment"}), 400

    # Verification: Must be the assigned employee
    verify_jwt_in_request()
    uid = get_jwt()["sub"]
    employee = db.employees.find_one({"user_id": oid(uid)})
    if not employee or str(question.get("assigned_employee_id")) != str(employee["_id"]):
        return jsonify({"error": "Access denied. You are not assigned to this order."}), 403

    student = db.students.find_one({"_id": question["student_id"]})
    ensure_payment_record(question_id, question["student_price"], question["student_id"])

    advance, completion = get_split_amounts(question["student_price"])
    return jsonify({
        "advance":    advance,
        "completion": completion,
        "total":      question["student_price"],
        "gateway":    "stripe"
    }), 200


# ── Student creates Checkout Session ─────────────────────────────────────────

@api_bp.route("/payments/checkout/<question_id>", methods=["POST"])
@student_required
def create_checkout(question_id):
    """
    Student calls this to get a Stripe Checkout Session URL.
    payment_type in body: "advance" | "completion"
    Redirects the student to Stripe's hosted checkout page.
    """
    print(f"DEBUG: Checkout requested for question_id: {question_id}")
    try:
        user_id_str = get_jwt()["sub"]  # identity is just the user_id string
        db          = get_db()
        print(f"DEBUG: User ID from JWT: {user_id_str}")

        student  = db.students.find_one({"user_id": oid(user_id_str)})
        user     = db.users.find_one({"_id": oid(user_id_str)})
        print(f"DEBUG: Student found: {student is not None}")
        
        question = db.questions.find_one({
            "_id":        oid(question_id),
            "student_id": student["_id"]
        })
        if not question:
            return jsonify({"error": "Order not found"}), 404

        data         = request.get_json()
        payment_type = data.get("payment_type")   # "advance" or "completion"

        if payment_type not in ("advance", "completion"):
            return jsonify({"error": "Invalid payment_type"}), 400

        payment = db.payments.find_one({"question_id": oid(question_id)})
        if not payment:
            return jsonify({"error": "Payment record not set up yet. Contact admin."}), 400

        # Guard: don't let student pay advance twice
        if payment_type == "advance" and payment.get("advance_paid"):
            return jsonify({"error": "Advance already paid"}), 400

        # Guard: don't let student pay completion before advance
        if payment_type == "completion" and not payment.get("advance_paid"):
            return jsonify({"error": "Advance payment required first"}), 400

        # Guard: don't let student pay completion twice
        if payment_type == "completion" and payment.get("completion_paid"):
            return jsonify({"error": "Completion already paid"}), 400

        student_email = user.get("email", "")

        if payment_type == "advance":
            session_url, session_id = create_advance_session(
                question_id, question["student_price"],
                question["title"], student_email
            )
            db.payments.update_one(
                {"question_id": oid(question_id)},
                {"$set": {"advance_session_id": session_id}}
            )
        else:
            session_url, session_id = create_completion_session(
                question_id, question["student_price"],
                question["title"], student_email
            )
            db.payments.update_one(
                {"question_id": oid(question_id)},
                {"$set": {"completion_session_id": session_id}}
            )

        return jsonify({"checkout_url": session_url}), 200

    except Exception as e:
        print(f"DEBUG: Checkout failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


# ── Stripe Webhook ────────────────────────────────────────────────────────────

@api_bp.route("/payments/webhook/stripe", methods=["POST"])
def stripe_webhook():
    """
    Stripe sends events here after payment succeeds.
    Must be registered in Stripe Dashboard → Webhooks.
    No JWT auth — Stripe signs the request with STRIPE_WEBHOOK_SECRET.
    """
    payload    = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    secret     = current_app.config["STRIPE_WEBHOOK_SECRET"]

    db = get_db()

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
        # Prevent duplicate webhook processing
        event_id = event["id"]

        already_processed = db.processed_webhooks.find_one({
            "event_id": event_id
        })

        if already_processed:
            return jsonify({"status": "already_processed"}), 200

    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400
    except Exception:
        return jsonify({"error": "Webhook parse error"}), 400

    if event["type"] == "checkout.session.completed":
        _handle_checkout_completed(event["data"]["object"])

    # Record every processed event — not just checkout.session.completed
    db.processed_webhooks.insert_one({
        "event_id":     event_id,
        "event_type":   event["type"],
        "processed_at": datetime.utcnow()
    })

    # Always return 200 to Stripe — even for unhandled event types
    return jsonify({"status": "ok"}), 200


@api_bp.route("/payments/refund/<question_id>", methods=["POST"])
@admin_required
def refund_payment(question_id):

    db = get_db()

    verify_jwt_in_request()
    admin_user_id = get_jwt()["sub"]

    data = request.get_json() or {}
    reason = data.get("reason", "No reason provided")

    from app.services.refund_service import refund_advance_payment

    try:
        refund = refund_advance_payment(
            question_id,
            admin_user_id,
            reason
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "message": "Refund successful",
        "refund_id": refund.id
    }), 200


@api_bp.route("/payments/verify", methods=["GET"])
@student_required
def verify_payment():
    """
    Called by the frontend after Stripe redirect.
    Checks Stripe's session status and reconciles DB if webhook was missed.
    """
    session_id = request.args.get("session_id")
    question_id = request.args.get("id")  # Using 'id' to match order-detail URL param

    if not session_id or not question_id:
        return jsonify({"error": "Missing session_id or id"}), 400

    try:
        db = get_db()
        # 1. Ask Stripe directly
        from app.services.payment_service import _stripe
        s = _stripe()
        stripe_session = s.checkout.Session.retrieve(
            session_id,
            expand=["payment_intent"]
        )
        
        payment_status = getattr(stripe_session, "payment_status", "unpaid")
        if payment_status != "paid":
            return jsonify({"status": "pending", "stripe_status": payment_status})

        # 2. Reconcile DB if needed
        # _handle_checkout_completed is idempotent and returns the payment type
        payment_type = _handle_checkout_completed(stripe_session, triggered_by="verify_endpoint")

        return jsonify({"status": "paid", "payment_type": payment_type})

    except Exception as e:
        print(f"DEBUG: Verification failed: {str(e)}")
        return jsonify({"error": str(e)}), 500


def _handle_checkout_completed(session, triggered_by="webhook"):
    """Process a completed Stripe Checkout Session. Idempotent."""
    # Robustly get session_id
    session_id = getattr(session, "id", None)
    if not session_id:
        try:
            session_id = session.get("id")
        except Exception:
            pass

    if not session_id:
        return

    db = get_db()
    now = datetime.utcnow()

    # 1. Find the payment record by session_id
    payment = db.payments.find_one({
        "$or": [
            {"advance_session_id": session_id},
            {"completion_session_id": session_id}
        ]
    })

    if not payment:
        # Fallback: Check metadata if session is not yet linked in DB
        metadata = getattr(session, "metadata", {})
        if not metadata:
            try: metadata = session.get("metadata", {})
            except: metadata = {}
        
        qid_str = metadata.get("question_id")
        payment_type = metadata.get("payment_type") # "advance" or "completion"
        
        if qid_str:
            payment = db.payments.find_one({"question_id": oid(qid_str)})
            question_id = oid(qid_str)
        
        if not payment:
            return None
    else:
        question_id = payment["question_id"]
        payment_type = "advance" if payment.get("advance_session_id") == session_id else "completion"

    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        return

    # Robustly get amount_total
    amount_paid_cents = getattr(session, "amount_total", 0)
    if not amount_paid_cents:
        try:
            amount_paid_cents = session.get("amount_total", 0)
        except Exception:
            pass
    amount_paid = amount_paid_cents / 100

    # Extract Stripe PaymentIntent ID safely.
    # When called from verify_payment (expand=["payment_intent"]), the field is a
    # full PaymentIntent object. When called from webhook/sync, it is a plain string.
    # Always store only the string ID so MongoDB can serialize it.
    _pi_raw = getattr(session, "payment_intent", None)
    if _pi_raw is None:
        try:
            _pi_raw = session.get("payment_intent")
        except Exception:
            _pi_raw = None
    if isinstance(_pi_raw, str):
        payment_intent_id = _pi_raw
    elif _pi_raw is not None:
        # Expanded PaymentIntent object — extract its ID
        payment_intent_id = getattr(_pi_raw, "id", None) or _pi_raw.get("id")
    else:
        payment_intent_id = None

    if payment_type == "advance":
        # Idempotency check — already paid, but backfill intent_id if it was missed
        if payment.get("advance_paid"):
            if payment_intent_id and not payment.get("advance_payment_intent_id"):
                db.payments.update_one(
                    {"question_id": oid(question_id)},
                    {"$set": {"advance_payment_intent_id": payment_intent_id}}
                )
            return "advance"

        db.payments.update_one(
            {"question_id": oid(question_id)},
            {"$set": {
                "advance_paid":       True,
                "advance_paid_at":    now,
                "advance_session_id": session_id,
                "status":             "advance_paid",
                "advance_payment_intent_id": payment_intent_id,
                "triggered_by":       triggered_by  # Audit trail
            }}
        )
        # Check if status transitions to in_progress or similar
        db.questions.update_one(
            {"_id": oid(question_id)},
            {"$set": {"status": "in_progress"}}
        )
        # Increment student's total_spent
        db.students.update_one(
            {"_id": question["student_id"]},
            {"$inc": {"total_spent": amount_paid}}
        )

        # Notify student
        _notify_payment_confirmed(question_id, "advance")
        return "advance"

    elif payment_type == "completion":
        # Idempotency check — already paid, but backfill intent_id if it was missed
        if payment.get("completion_paid"):
            if payment_intent_id and not payment.get("completion_payment_intent_id"):
                db.payments.update_one(
                    {"question_id": oid(question_id)},
                    {"$set": {"completion_payment_intent_id": payment_intent_id}}
                )
            return "completion"

        db.payments.update_one(
            {"question_id": oid(question_id)},
            {"$set": {
                "completion_paid":       True,
                "completion_paid_at":    now,
                "completion_session_id": session_id,
                "status":                "fully_paid",
                "completion_payment_intent_id": payment_intent_id,
                "triggered_by":       triggered_by  # Audit trail
            }}
        )
        # Unlock all solution files for this question
        from app.services.diamond_engine import unlock_all_solutions, delete_preview_files
        unlock_all_solutions(str(question_id))
        # Clean up preview files from S3 — no longer needed after full payment
        delete_preview_files(str(question_id))
        db.questions.update_one(
            {"_id": oid(question_id)},
            {"$set": {"status": "completed"}}
        )

        # Increment student's total_spent
        db.students.update_one(
            {"_id": question["student_id"]},
            {"$inc": {"total_spent": amount_paid}}
        )

        # Increment expert's total_earnings and tasks_completed
        assigned_expert_id = question.get("assigned_expert_id")
        expert_payout = question.get("expert_payout", 0)
        if assigned_expert_id and expert_payout > 0:
            db.experts.update_one(
                {"_id": assigned_expert_id},
                {"$inc": {
                    "total_earnings": float(expert_payout),
                    "tasks_completed": 1
                }}
            )
            # Create a payout record for the expert
            db.payouts.insert_one({
                "question_id":       oid(question_id),
                "expert_id":         assigned_expert_id,
                "amount":            float(expert_payout),
                "is_paid":           False,
                "paid_at":           None,
                "task_completed_at": now,
                "created_at":        now
            })

        # Update final revenue and profit in payment record
        student_price = question.get("student_price", 0)
        profit = (student_price or 0) - (expert_payout or 0)
        db.payments.update_one(
            {"question_id": oid(question_id)},
            {"$set": {
                "revenue": float(student_price),
                "profit":  float(profit)
            }}
        )

        # Notify student
        _notify_payment_confirmed(question_id, "completion")
        return "completion"


def _notify_payment_confirmed(question_id, payment_type):
    """
    Fire notification + email after a successful payment.
    Runs synchronously inside the webhook handler — keep it fast.
    """
    try:
        from app.services.notification_service import create_notification
        from app.services.email_service import send_order_received_email

        db       = get_db()
        question = db.questions.find_one({"_id": oid(question_id)})
        if not question:
            return

        student = db.students.find_one({"_id": question["student_id"]})
        user    = db.users.find_one({"_id": student["user_id"]})
        if not user:
            return

        user_id_str = str(user["_id"])

        if payment_type == "advance":
            from app.tasks.notification_tasks import send_notification_async
            send_notification_async.delay(
                user_id=user_id_str,
                notif_type="payment_confirmed",
                title="Advance payment confirmed",
                body=f"Work has begun on: {question['title']}",
                link=f"/student/order-detail.html?id={question_id}"
            )
            # ALSO NOTIFY ADMIN
            if question.get("assigned_employee_id"):
                emp = db.employees.find_one({"_id": question["assigned_employee_id"]})
                if emp:
                    from app.tasks.notification_tasks import send_notification_async
                    send_notification_async.delay(
                        user_id=str(emp["user_id"]),
                        notif_type="admin_payment_received",
                        title="Payment received",
                        body=f"Student paid advance for: {question['title']}",
                        link=f"/admin/cockpit.html?id={question_id}"
                    )
        else:
            from app.tasks.notification_tasks import send_notification_async
            send_notification_async.delay(
                user_id=user_id_str,
                notif_type="order_completed",
                title="Solution unlocked",
                body=f"Your full solution is now available: {question['title']}",
                link=f"/student/order-detail.html?id={question_id}"
            )
            # ALSO NOTIFY ADMIN
            if question.get("assigned_employee_id"):
                emp = db.employees.find_one({"_id": question["assigned_employee_id"]})
                if emp:
                    from app.tasks.notification_tasks import send_notification_async
                    send_notification_async.delay(
                        user_id=str(emp["user_id"]),
                        notif_type="admin_payment_received",
                        title="Full payment received",
                        body=f"Student paid completion for: {question['title']}",
                        link=f"/admin/cockpit.html?id={question_id}"
                    )
    except Exception:
        pass   # Never let notification failure break the webhook response


# ── Payment status endpoint ───────────────────────────────────────────────────

@api_bp.route("/payments/status/<question_id>", methods=["GET"])
@student_required
def payment_status(question_id):
    """
    Student polls this to check payment state.
    Used to refresh the UI after returning from Stripe Checkout.
    """
    user_id_str = get_jwt()["sub"]
    db          = get_db()

    student  = db.students.find_one({"user_id": oid(user_id_str)})
    question = db.questions.find_one({
        "_id":        oid(question_id),
        "student_id": student["_id"]
    })
    if not question:
        return jsonify({"error": "Not found"}), 404

    # Sync with Stripe manually in case webhook was missed (local dev)
    from app.services.payment_service import sync_payment_session
    sync_payment_session(question_id)

    payment = db.payments.find_one({"question_id": oid(question_id)})
    if not payment:
        return jsonify({
            "advance_paid":    False,
            "completion_paid": False,
            "advance_amount":  None,
            "completion_amount": None,
            "status":          "not_setup"
        }), 200

    advance, completion = get_split_amounts(question["student_price"])

    return jsonify({
        "advance_paid":      payment.get("advance_paid",    False),
        "completion_paid":   payment.get("completion_paid", False),
        "advance_amount":    payment.get("advance_amount",  advance),
        "completion_amount": payment.get("completion_amount", completion),
        "total_amount":      payment.get("total_amount",    question["student_price"]),
        "status":            payment.get("status",          "pending"),
        "gateway":           "stripe"
    }), 200
