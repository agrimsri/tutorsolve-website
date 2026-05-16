import stripe
from flask import current_app
from datetime import datetime

from app.extensions import get_db
from app.utils.helpers import oid


def _stripe():
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    return stripe


def refund_advance_payment(question_id, admin_id, reason, refund_amount=None):
    db = get_db()
    s = _stripe()

    payment = db.payments.find_one({
        "question_id": oid(question_id)
    })

    if not payment:
        raise Exception("Payment not found")

    if not payment.get("advance_payment_intent_id"):
        raise Exception("No payment intent found — student may not have paid via Stripe yet")

    if payment.get("advance_refund_id"):
        raise Exception("Already refunded")

    # Determine the amount to refund.
    # refund_amount is in INR (rupees). Stripe expects paise (integer, ×100).
    advance_amount = payment.get("advance_amount", 0)
    if refund_amount is None:
        refund_amount = advance_amount  # default: full refund

    refund_amount = float(refund_amount)
    if refund_amount <= 0 or refund_amount > advance_amount:
        raise Exception(
            f"Refund amount ₹{refund_amount:.2f} is invalid "
            f"(advance paid: ₹{advance_amount:.2f})"
        )

    is_partial = refund_amount < advance_amount

    # Build Stripe refund kwargs — only pass amount if partial
    stripe_kwargs = {
        "payment_intent": payment["advance_payment_intent_id"],
        "reason": "requested_by_customer",
    }
    if is_partial:
        stripe_kwargs["amount"] = int(round(refund_amount * 100))  # convert to paise

    refund = s.Refund.create(**stripe_kwargs)

    now = datetime.utcnow()
    student_id = payment.get("student_id")

    # Update payment record: mark as refunded + store Stripe refund details
    db.payments.update_one(
        {"question_id": oid(question_id)},
        {
            "$set": {
                "status":              "refunded",
                "refund_status":       "completed",
                "advance_refund_id":   refund.id,
                "refund_completed_at": now,
                "refunded_at":         now,
            },
            "$push": {
                "refunds": {
                    "refund_id":    refund.id,
                    "amount":       refund_amount,
                    "payment_type": "advance",
                    "reason":       reason,
                    "status":       refund.status,
                    "initiated_by": oid(admin_id),
                    "created_at":   now
                }
            }
        }
    )

    # Update question status to refunded
    db.questions.update_one(
        {"_id": oid(question_id)},
        {"$set": {"status": "refunded"}}
    )

    # Reverse the student's total_spent
    if student_id and refund_amount:
        db.students.update_one(
            {"_id": student_id},
            {"$inc": {"total_spent": -float(refund_amount)}}
        )

    # Cancel any pending payout for this question (safety)
    db.payouts.delete_many({"question_id": oid(question_id), "is_paid": False})

    # Notify the student
    try:
        question = db.questions.find_one({"_id": oid(question_id)})
        if question and student_id:
            student = db.students.find_one({"_id": student_id})
            if student:
                from app.tasks.notification_tasks import send_notification_async
                send_notification_async.delay(
                    user_id=str(student["user_id"]),
                    notif_type="refund_approved",
                    title="Refund Processed",
                    body=f"Your refund of \u20b9{refund_amount:.2f} for '{question.get('title', 'your order')}' has been issued.",
                    link=f"/student/order-detail.html?id={question_id}"
                )
    except Exception:
        pass  # Never let notification failure break the refund

    return refund