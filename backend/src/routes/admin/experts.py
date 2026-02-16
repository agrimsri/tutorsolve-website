from flask import Blueprint, jsonify, current_app
from bson import ObjectId
from src.core.decorators import auth_required
from src.services.expert_service import ExpertService, ExpertServiceError
from src.services.notification_service import NotificationService


admin_experts_bp = Blueprint(
    "admin_experts",
    __name__,
    url_prefix="/admin/experts"
)


@admin_experts_bp.route("/pending", methods=["GET"])
@auth_required(["Admin"])
def list_pending_experts():
    experts = ExpertService.get_pending_experts()

    return jsonify({
        "count": len(experts),
        "experts": experts
    })


@admin_experts_bp.route("/approve/<expert_id>", methods=["POST"])
@auth_required(["Admin"])
def approve_expert(expert_id):
    try:
        ExpertService.approve_expert(expert_id)

        experts = current_app.mongo.experts
        users = current_app.mongo.users

        expert = experts.find_one({"_id": ObjectId(expert_id)})
        user = users.find_one({"_id": expert["user"]})

        NotificationService.send_expert_approved_email(
            email=user["email"],
            name=user.get("name", "Expert")
        )


        return jsonify({"message": "Expert approved successfully"})
    except ExpertServiceError as e:
        return jsonify({"error": str(e)}), 400
