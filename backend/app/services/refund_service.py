import stripe
from flask import current_app
from datetime import datetime
import logging

from app.extensions import get_db
from app.utils.helpers import oid
from app.utils.currency import money_label

logger = logging.getLogger(__name__)


def _stripe():
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    return stripe


def refund_advance_payment(question_id, admin_id, reason, refund_amount=None, cancel_unpaid_payouts=True, is_part_of_full_refund=False):
    """
    Issues a Stripe refund against the advance payment intent.
    
    Args:
        is_part_of_full_refund: If True, skip updating question status (will be done once for full refund)
    """
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

    currency = payment.get("currency") or payment.get("student_currency") or "inr"

    # Determine the amount to refund in the payment currency.
    # Stripe expects the smallest unit (integer, x100 for INR/USD).
    advance_amount = payment.get("advance_amount", 0)
    if refund_amount is None:
        refund_amount = advance_amount  # default: full refund

    refund_amount = float(refund_amount)
    if refund_amount <= 0 or refund_amount > advance_amount:
        raise Exception(
            f"Refund amount {money_label(refund_amount, currency)} is invalid "
            f"(advance paid: {money_label(advance_amount, currency)})"
        )

    is_partial = refund_amount < advance_amount

    # Build Stripe refund kwargs — only pass amount if partial
    stripe_kwargs = {
        "payment_intent": payment["advance_payment_intent_id"],
        "reason": "requested_by_customer",
    }
    if is_partial:
        stripe_kwargs["amount"] = int(round(refund_amount * 100))

    # BUG#2, #10: Validate Stripe refund status + distinguish recoverable vs fatal errors
    try:
        refund = s.Refund.create(**stripe_kwargs)
    except stripe.error.InvalidRequestError as e:
        logger.error(f"Invalid Stripe refund request for question {question_id}: {str(e)}")
        raise Exception(f"Invalid refund request: {str(e)}")
    except stripe.error.APIConnectionError as e:
        logger.error(f"Stripe connection error for question {question_id}: {str(e)}")
        raise Exception("Temporary payment processor error. Please retry.")
    except stripe.error.AuthenticationError as e:
        logger.error(f"Stripe authentication error for question {question_id}: {str(e)}")
        raise Exception("Payment processor authentication failed.")
    except Exception as e:
        logger.error(f"Unexpected Stripe error for question {question_id}: {str(e)}")
        raise Exception(f"Payment processor error: {str(e)}")

    # BUG#2: Only process if refund succeeded
    if refund.status not in ("succeeded", "pending"):
        raise Exception(f"Refund failed with status: {refund.status}. Please retry or contact support.")

    now = datetime.utcnow()
    student_id = payment.get("student_id")

    # Update payment record: mark as refunded + store Stripe refund details
    db.payments.update_one(
        {"question_id": oid(question_id)},
        {
            "$set": {
                "status":              "refunded",
                "refund_status":       refund.status,  # "succeeded" or "pending"
                "advance_refund_id":   refund.id,
                "refund_completed_at": now,
                "refunded_at":         now,
            },
            "$push": {
                "refunds": {
                    "refund_id":    refund.id,
                    "amount":       refund_amount,
                    "currency":     currency,
                    "payment_type": "advance",
                    "reason":       reason,
                    "status":       refund.status,
                    "initiated_by": oid(admin_id),
                    "created_at":   now
                }
            }
        }
    )

    # For advance-only approved refunds, treat the order as cancelled.
    # (Full refunds still set terminal refunded status at the orchestrator level.)
    if not is_part_of_full_refund:
        db.questions.update_one(
            {"_id": oid(question_id)},
            {"$set": {"status": "cancelled"}}
        )

    # BUG#4: Validate total_spent doesn't go negative
    if student_id and refund_amount:
        student = db.students.find_one({"_id": student_id})
        current_spent = float(student.get("total_spent", 0) or 0)
        new_spent = current_spent - float(refund_amount)
        
        if new_spent < 0:
            logger.warning(f"Refund would make student {student_id} have negative total_spent. Clamping to 0. Previous: {current_spent}, Refund: {refund_amount}")
            new_spent = 0
        
        db.students.update_one(
            {"_id": student_id},
            {
                "$set": {"total_spent": new_spent},
                "$inc": {f"total_spent_by_currency.{currency}": -float(refund_amount)}
            }
        )

    # Optionally cancel pending payout for this question (pre-completion safety path).
    if cancel_unpaid_payouts:
        db.payouts.delete_many({"question_id": oid(question_id), "is_paid": False})

    # Fetch question for notifications
    question = db.questions.find_one({"_id": oid(question_id)})

    # Notify the student
    try:
        if question and student_id:
            student = db.students.find_one({"_id": student_id})
            if student:
                from app.tasks.notification_tasks import send_notification_async
                send_notification_async.delay(
                    user_id=str(student["user_id"]),
                    notif_type="refund_approved",
                    title="Refund Processed",
                    body=f"Your refund of {money_label(refund_amount, currency)} for '{question.get('title', 'your order')}' has been issued.",
                    link=f"/student/order-detail.html?id={question_id}"
                )
    except Exception as e:
        logger.warning(f"Failed to notify student of refund: {str(e)}")

    # Notify the expert
    try:
        if question and question.get("assigned_expert_id"):
            expert = db.experts.find_one({"_id": question["assigned_expert_id"]})
            if expert:
                from app.tasks.notification_tasks import send_notification_async
                send_notification_async.delay(
                    user_id=str(expert["user_id"]),
                    notif_type="refund_expert_advance",
                    title="Refund Issued — Advance Payment",
                    body=(
                        f"A refund was approved for your task: '{question.get('title', 'your task')}'. "
                        + (
                            "Your pending payout for this order has been cancelled."
                            if cancel_unpaid_payouts
                            else "Your payout is not auto-cancelled and will be reviewed by admin."
                        )
                    ),
                    link=f"/expert/task-detail.html?id={question_id}"
                )
    except Exception as e:
        logger.warning(f"Failed to notify expert of refund: {str(e)}")

    return refund


def refund_completion_payment(question_id, admin_id, reason, refund_amount=None, cancel_unpaid_payouts=False, is_part_of_full_refund=False):
    """
    Issues a Stripe refund against the completion payment intent.
    Called by super admin when approving a post-completion refund request.
    
    Args:
        is_part_of_full_refund: If True, skip updating question status (will be done once for full refund)
    """
    db = get_db()
    s = _stripe()

    payment = db.payments.find_one({"question_id": oid(question_id)})

    if not payment:
        raise Exception("Payment not found")

    if not payment.get("completion_payment_intent_id"):
        raise Exception("No completion payment intent found — student may not have paid completion via Stripe yet")

    if payment.get("completion_refund_id"):
        raise Exception("Completion payment already refunded")

    currency = payment.get("currency") or payment.get("student_currency") or "inr"

    # Determine the amount to refund in the payment currency.
    completion_amount = payment.get("completion_amount", 0)
    if refund_amount is None:
        refund_amount = completion_amount  # default: full refund

    refund_amount = float(refund_amount)
    if refund_amount <= 0 or refund_amount > completion_amount:
        raise Exception(
            f"Refund amount {money_label(refund_amount, currency)} is invalid "
            f"(completion paid: {money_label(completion_amount, currency)})"
        )

    is_partial = refund_amount < completion_amount

    stripe_kwargs = {
        "payment_intent": payment["completion_payment_intent_id"],
        "reason": "requested_by_customer",
    }
    if is_partial:
        stripe_kwargs["amount"] = int(round(refund_amount * 100))

    # BUG#2, #10: Validate Stripe refund status + distinguish recoverable vs fatal errors
    try:
        refund = s.Refund.create(**stripe_kwargs)
    except stripe.error.InvalidRequestError as e:
        logger.error(f"Invalid Stripe refund request for question {question_id}: {str(e)}")
        raise Exception(f"Invalid refund request: {str(e)}")
    except stripe.error.APIConnectionError as e:
        logger.error(f"Stripe connection error for question {question_id}: {str(e)}")
        raise Exception("Temporary payment processor error. Please retry.")
    except stripe.error.AuthenticationError as e:
        logger.error(f"Stripe authentication error for question {question_id}: {str(e)}")
        raise Exception("Payment processor authentication failed.")
    except Exception as e:
        logger.error(f"Unexpected Stripe error for question {question_id}: {str(e)}")
        raise Exception(f"Payment processor error: {str(e)}")

    # BUG#2: Only process if refund succeeded or is pending
    if refund.status not in ("succeeded", "pending"):
        raise Exception(f"Refund failed with status: {refund.status}. Please retry or contact support.")

    now = datetime.utcnow()
    student_id = payment.get("student_id")
    question = db.questions.find_one({"_id": oid(question_id)})
    assigned_expert_id = question.get("assigned_expert_id") if question else None

    # Update payment record
    db.payments.update_one(
        {"question_id": oid(question_id)},
        {
            "$set": {
                "status":                "refunded",
                "refund_status":         refund.status,  # "succeeded" or "pending"
                "completion_refund_id":  refund.id,
                "refund_completed_at":   now,
                "refunded_at":           now,
            },
            "$push": {
                "refunds": {
                    "refund_id":    refund.id,
                    "amount":       refund_amount,
                    "currency":     currency,
                    "payment_type": "completion",
                    "reason":       reason,
                    "status":       refund.status,
                    "initiated_by": oid(admin_id),
                    "created_at":   now
                }
            }
        }
    )

    # BUG#5: Only update question status if not part of full refund (will be done once)
    if not is_part_of_full_refund:
        db.questions.update_one(
            {"_id": oid(question_id)},
            {"$set": {"status": "refunded"}}
        )

    # BUG#4: Validate total_spent doesn't go negative
    if student_id and refund_amount:
        student = db.students.find_one({"_id": student_id})
        current_spent = float(student.get("total_spent", 0) or 0)
        new_spent = current_spent - float(refund_amount)
        
        if new_spent < 0:
            logger.warning(f"Refund would make student {student_id} have negative total_spent. Clamping to 0. Previous: {current_spent}, Refund: {refund_amount}")
            new_spent = 0
        
        db.students.update_one(
            {"_id": student_id},
            {
                "$set": {"total_spent": new_spent},
                "$inc": {f"total_spent_by_currency.{currency}": -float(refund_amount)}
            }
        )

    # BUG#6: Reverse expert earnings when refunding completion payment
    if assigned_expert_id and not cancel_unpaid_payouts:
        expert_payout = question.get("expert_payout", 0) if question else 0
        expert_currency = question.get("expert_currency", "inr") if question else "inr"
        if expert_payout > 0:
            expert = db.experts.find_one({"_id": assigned_expert_id})
            current_earnings = float(expert.get("total_earnings", 0) or 0) if expert else 0
            new_earnings = max(0, current_earnings - expert_payout)
            
            db.experts.update_one(
                {"_id": assigned_expert_id},
                {
                    "$set": {"total_earnings": new_earnings},
                    "$inc": {f"total_earnings_by_currency.{expert_currency}": -float(expert_payout)}
                }
            )
            logger.info(f"Reversed expert {assigned_expert_id} earnings for refunded question {question_id}: {expert_payout}")

    # For completion-stage refunds, optionally cancel expert payouts by default.
    if cancel_unpaid_payouts:
        db.payouts.delete_many({"question_id": oid(question_id), "is_paid": False})

    # Notify the student
    try:
        if question and student_id:
            student = db.students.find_one({"_id": student_id})
            if student:
                from app.tasks.notification_tasks import send_notification_async
                send_notification_async.delay(
                    user_id=str(student["user_id"]),
                    notif_type="refund_approved",
                    title="Refund Processed",
                    body=f"Your refund of {money_label(refund_amount, currency)} for '{question.get('title', 'your order')}' has been issued.",
                    link=f"/student/order-detail.html?id={question_id}"
                )
    except Exception as e:
        logger.warning(f"Failed to notify student of refund: {str(e)}")

    # Notify the expert
    try:
        if question and question.get("assigned_expert_id"):
            expert = db.experts.find_one({"_id": question["assigned_expert_id"]})
            if expert:
                from app.tasks.notification_tasks import send_notification_async
                send_notification_async.delay(
                    user_id=str(expert["user_id"]),
                    notif_type="refund_expert_completion",
                    title="Refund Issued — Completion Payment",
                    body=(
                        f"A post-completion refund was approved for your task: '{question.get('title', 'your task')}'. "
                        + (
                            "Your pending payout for this order has been cancelled."
                            if cancel_unpaid_payouts
                            else "Your payout is not auto-cancelled and will be reviewed by admin."
                        )
                    ),
                    link=f"/expert/task-detail.html?id={question_id}"
                )
    except Exception as e:
        logger.warning(f"Failed to notify expert of refund: {str(e)}")

    return refund
