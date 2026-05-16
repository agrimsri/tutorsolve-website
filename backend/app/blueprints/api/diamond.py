from flask import jsonify
from app.blueprints.api import api_bp
from app.services.diamond_engine import broadcast_question
from app.utils.decorators import admin_required

@api_bp.route("/diamond/broadcast/<question_id>", methods=["POST"])
@admin_required
def broadcast(question_id):
    broadcast_question(question_id)
    return jsonify({"status": "broadcasted"}), 200
