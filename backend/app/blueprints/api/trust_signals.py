from flask import jsonify
from app.blueprints.api import api_bp
from app.extensions import get_db
from app.utils.constants import KYCStatus, OrderStatus


@api_bp.route("/trust-signals", methods=["GET"])
def trust_signals():
    db = get_db()
    active_experts    = db.experts.count_documents({"kyc_status": KYCStatus.APPROVED})
    questions_solved  = db.questions.count_documents({"status": OrderStatus.COMPLETED})
    recent            = list(db.questions.find({"status": OrderStatus.COMPLETED})
                             .sort("created_at", -1).limit(5))
    ticker = [f"{q['domain']} Question just solved!" for q in recent]
    return jsonify({
        "active_experts":   active_experts,
        "questions_solved": questions_solved,
        "ticker":           ticker
    }), 200
