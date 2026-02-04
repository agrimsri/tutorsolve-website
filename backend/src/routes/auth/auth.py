from flask import Blueprint, request, jsonify
from src.services.auth_service import AuthService, AuthServiceError

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/signup/student", methods=["POST"])
def signup_student():
    data = request.json

    try:
        user = AuthService.signup_student(
            email=data["email"],
            password=data["password"],
            country=data["country"],
            degree=data.get("degree")
        )
        return jsonify({"message": "Student registered", "user_id": str(user.id)}), 201

    except AuthServiceError as e:
        return jsonify({"error": str(e)}), 400


@auth_bp.route("/signup/expert", methods=["POST"])
def signup_expert():
    data = request.json

    try:
        user = AuthService.signup_expert(
            email=data["email"],
            password=data["password"],
            domain=data["domain"]
        )
        return jsonify({"message": "Expert registered, pending approval"}), 201

    except AuthServiceError as e:
        return jsonify({"error": str(e)}), 400


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json

    try:
        user = AuthService.login(
            email=data["email"],
            password=data["password"]
        )
        return jsonify({
            "message": "Login successful",
            "role": user.role.value
        })

    except AuthServiceError as e:
        return jsonify({"error": str(e)}), 401