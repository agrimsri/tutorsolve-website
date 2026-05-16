from app.extensions import get_db
from datetime import datetime, timedelta
from app.utils.helpers import oid


def get_eligible_payouts():
    db = get_db()
    unpaid = list(db.payouts.find({"is_paid": False}))
    # Removed 20-day hold for testing/immediate payouts
    # cutoff = datetime.utcnow() - timedelta(days=20)
    return [p for p in unpaid if p.get("task_completed_at")]


def mark_expert_payouts_as_paid(expert_id):
    db = get_db()
    unpaid = list(db.payouts.find({"expert_id": oid(expert_id), "is_paid": False}))
    if not unpaid:
        raise ValueError("No unpaid payouts found for this expert")
        
    total_amount = sum(p["amount"] for p in unpaid)
    
    db.payouts.update_many(
        {"expert_id": oid(expert_id), "is_paid": False},
        {"$set": {"is_paid": True, "paid_at": datetime.utcnow()}}
    )
    return total_amount
