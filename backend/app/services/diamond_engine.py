"""
Diamond Logic — Core Transaction Engine (Module 3)
Phase A: Broadcast & Interest Signal
Phase B: Parallel Negotiation
Phase C: Payment & Assignment
Phase D: Delivery & Lock Logic
"""
from app.extensions import get_db
from app.services.email_blast import send_domain_blast
from app.utils.constants import OrderStatus
from app.utils.helpers import oid
from datetime import datetime


def broadcast_question(question_id):
    db = get_db()
    question = db.questions.find_one({"_id": oid(question_id)})
    if not question:
        raise ValueError("Question not found")
    db.questions.update_one(
        {"_id": oid(question_id)},
        {"$set": {"status": OrderStatus.AWAITING_QUOTE}}
    )
    send_domain_blast(question)


def set_price_quote(question_id, student_price, expert_payout):
    db = get_db()
    db.questions.update_one(
        {"_id": oid(question_id)},
        {"$set": {
            "student_price": student_price,
            "expert_payout": expert_payout,
        }}
    )


def approve_price(question_id):
    db = get_db()
    db.questions.update_one(
        {"_id": oid(question_id)},
        {"$set": {
            "price_approved": True,
            "status": OrderStatus.PENDING_PAYMENT
        }}
    )


def assign_expert(question_id, expert_id):
    db = get_db()
    db.questions.update_one(
        {"_id": oid(question_id)},
        {"$set": {
            "assigned_expert_id": oid(expert_id),
            "status": OrderStatus.IN_PROGRESS
        }}
    )


def unlock_all_solutions(question_id):
    db = get_db()
    db.files.update_many(
        {"question_id": oid(question_id), "category": "solution"},
        {"$set": {"is_locked": False}}
    )


def delete_preview_files(question_id):
    """
    Remove preview S3 objects and clear preview_s3_key for all solution files
    of a question. Called after full payment when students get access to the
    real files and previews are no longer needed.
    """
    from flask import current_app
    db = get_db()
    solution_files = list(db.files.find({
        "question_id": oid(question_id),
        "category": "solution",
        "preview_s3_key": {"$ne": None}
    }))

    if not solution_files:
        return

    from app.services.file_service import delete_from_s3
    for f in solution_files:
        preview_key = f.get("preview_s3_key")
        if preview_key:
            delete_from_s3(preview_key)

    # Clear preview_s3_key from all solution files for this question
    db.files.update_many(
        {"question_id": oid(question_id), "category": "solution"},
        {"$set": {"preview_s3_key": None}}
    )
    try:
        current_app.logger.info(
            f"[Preview Cleanup] Deleted {len(solution_files)} preview(s) for question {question_id}"
        )
    except Exception:
        pass
