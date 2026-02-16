from flask import Blueprint, jsonify, request
from src.core.decorators import auth_required
from bson import ObjectId
from flask import current_app

me_bp = Blueprint("me", __name__, url_prefix="/me")


@me_bp.route("", methods=["GET"])
@auth_required()
def get_current_user():
    users = current_app.mongo.users
    experts = current_app.mongo.experts

    user = users.find_one({"_id": ObjectId(request.user["user_id"])})

    if not user:
        return jsonify({"error": "User not found"}), 404

    approved = None

    if "Expert" in user.get("role", []):
        expert = experts.find_one({"user": user["_id"]})
        approved = expert.get("approved", expert.get("approve", False)) if expert else False

    department = None
    if "Expert" not in user.get("role", []):
        departments = current_app.mongo.departments
        department = departments.find_one({"slug": user.get("department")})
    return jsonify({
        "user_id": str(user["_id"]),
        "role": user["role"],
        "name": user.get("name"),
        "picture": user.get("picture"),
        "approved": approved,
        "department": department.get("name") if department else None
    })
