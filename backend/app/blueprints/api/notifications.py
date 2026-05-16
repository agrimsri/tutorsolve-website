from flask import jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from app.blueprints.api import api_bp
from app.services.notification_service import (
    get_unread_count,
    get_recent_notifications,
    mark_all_read
)


from app.utils.decorators import role_required
from app.utils.constants import Role

@api_bp.route("/notifications", methods=["GET"])
@role_required(Role.STUDENT, Role.EXPERT, Role.EMPLOYEE, Role.SUPER_ADMIN)
def get_notifications():
    identity_id = get_jwt()["sub"]
    return jsonify({
        "unread_count":  get_unread_count(identity_id),
        "notifications": get_recent_notifications(identity_id)
    }), 200


@api_bp.route("/notifications/read", methods=["POST"])
@role_required(Role.STUDENT, Role.EXPERT, Role.EMPLOYEE, Role.SUPER_ADMIN)
def read_notifications():
    identity_id = get_jwt()["sub"]
    mark_all_read(identity_id)
    return jsonify({"status": "ok"}), 200
