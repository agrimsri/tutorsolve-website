import stripe
from flask import current_app
from datetime import datetime
from app.extensions import get_db
from app.utils.helpers import oid


def _stripe():
    """Return configured Stripe client."""
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    # stripe.api_version = "2026-04-01"
    return stripe


def get_split_amounts(student_price):
    """
    Split student_price 50/50 into advance and completion.
    Returns amounts in USD dollars (floats), not cents.
    Always rounds up the advance so completion is never larger.
    """
    advance    = round(student_price / 2, 2)
    completion = round(student_price - advance, 2)
    return advance, completion


def create_advance_session(question_id, student_price, question_title, student_email):
    """
    Creates a Stripe Checkout Session for the advance payment.
    Returns the session URL to redirect the student to.
    """
    s = _stripe()
    advance, _ = get_split_amounts(student_price)
    frontend   = current_app.config["FRONTEND_URL"]

    session = s.checkout.Session.create(
        payment_method_types=["card"],
        # automatic_payment_methods={"enabled": True},
        mode="payment",
        customer_email=student_email,
        billing_address_collection="required",
        line_items=[{
            "price_data": {
                "currency":     "inr",
                "unit_amount":  int(advance * 100),   # Stripe expects cents
                "product_data": {
                    "name":        f"Advance Payment — {question_title}",
                    "description": "50% advance to begin work on your question."
                }
            },
            "quantity": 1
        }],
        metadata={
            "question_id":  str(question_id),
            "payment_type": "advance"
        },
        success_url=f"{frontend}/student/order-detail.html?id={question_id}&payment=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{frontend}/student/order-detail.html?id={question_id}&payment=cancelled",
    )
    return session.url, session.id


def create_completion_session(question_id, student_price, question_title, student_email):
    """
    Creates a Stripe Checkout Session for the completion payment.
    Returns the session URL to redirect the student to.
    """
    s = _stripe()
    _, completion = get_split_amounts(student_price)
    frontend      = current_app.config["FRONTEND_URL"]

    session = s.checkout.Session.create(
        payment_method_types=["card"],
        # automatic_payment_methods={"enabled": True},
        mode="payment",
        customer_email=student_email,
        billing_address_collection="required",
        line_items=[{
            "price_data": {
                "currency":     "inr",
                "unit_amount":  int(completion * 100),
                "product_data": {
                    "name":        f"Completion Payment — {question_title}",
                    "description": "Final payment to unlock your full solution file."
                }
            },
            "quantity": 1
        }],
        metadata={
            "question_id":  str(question_id),
            "payment_type": "completion"
        },
        success_url=f"{frontend}/student/order-detail.html?id={question_id}&payment=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{frontend}/student/order-detail.html?id={question_id}&payment=cancelled",
    )
    return session.url, session.id


def ensure_payment_record(question_id_str, student_price, student_id_oid):
    """
    Creates or updates the payments document.
    Safe to call multiple times.
    If it exists, it updates the amounts, but ONLY if neither advance nor completion is paid.
    """
    db = get_db()
    advance, completion = get_split_amounts(student_price)

    # Fetch expert_payout from question
    question = db.questions.find_one({"_id": oid(question_id_str)})
    expert_payout = question.get("expert_payout", 0) if question else 0
    expected_profit = (student_price or 0) - (expert_payout or 0)

    existing = db.payments.find_one({"question_id": oid(question_id_str)})
    if not existing:
        db.payments.insert_one({
            "question_id":        oid(question_id_str),
            "student_id":         student_id_oid,
            "advance_amount":     advance,
            "completion_amount":  completion,
            "total_amount":       student_price,
            "expert_payout":      expert_payout,
            "revenue":            student_price,
            "expected_profit":    expected_profit,
            "advance_paid":       False,
            "completion_paid":    False,
            "advance_paid_at":    None,
            "completion_paid_at": None,
            "advance_session_id": None,
            "completion_session_id": None,
            "gateway":            "stripe",
            "status":             "pending",
            "payout_released":    False,
            "payout_released_at": None,
            "created_at":         datetime.utcnow()
        })
    else:
        # Only update if no payment has been processed
        if not existing.get("advance_paid") and not existing.get("completion_paid"):
            db.payments.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "advance_amount":    advance,
                    "completion_amount": completion,
                    "total_amount":      student_price,
                    "expert_payout":      expert_payout,
                    "revenue":            student_price,
                    "expected_profit":    expected_profit
                }}
            )


def sync_payment_session(question_id_str):
    """
    Manually checks Stripe to see if the session is paid if the webhook was missed.
    Also backfills advance_payment_intent_id / completion_payment_intent_id if they
    were not stored during the original payment (e.g. due to a pre-fix BSON bug).
    Mainly useful for local development without stripe listen.
    """
    db = get_db()
    payment = db.payments.find_one({"question_id": oid(question_id_str)})
    if not payment:
        return

    s = _stripe()

    # Check advance — run if not yet paid OR if intent_id is missing
    advance_needs_sync = (
        payment.get("advance_session_id") and (
            not payment.get("advance_paid") or
            not payment.get("advance_payment_intent_id")
        )
    )
    if advance_needs_sync:
        try:
            session = s.checkout.Session.retrieve(payment["advance_session_id"])
            if session.payment_status == "paid":
                from app.blueprints.api.payments import _handle_checkout_completed
                _handle_checkout_completed(session)
        except Exception as e:
            print("Sync advance error:", e)

    # Check completion — run if not yet paid OR if intent_id is missing
    completion_needs_sync = (
        payment.get("completion_session_id") and (
            not payment.get("completion_paid") or
            not payment.get("completion_payment_intent_id")
        )
    )
    if completion_needs_sync:
        try:
            session = s.checkout.Session.retrieve(payment["completion_session_id"])
            if session.payment_status == "paid":
                from app.blueprints.api.payments import _handle_checkout_completed
                _handle_checkout_completed(session)
        except Exception as e:
            print("Sync completion error:", e)
