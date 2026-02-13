from flask import Blueprint, request, jsonify
from src.services.auth_service import AuthService, AuthServiceError

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/signup/student", methods=["POST"])
def signup_student():
    data = request.json
    try:
        result = AuthService.signup_student(
            name=data["name"],
            email=data["email"],
            password=data["password"]
        )
        return jsonify(result), 201
    except AuthServiceError as e:
        return jsonify({"error": str(e)}), 400


@auth_bp.route("/signup/expert", methods=["POST"])
def signup_expert():
    data = request.json
    try:
        result = AuthService.signup_expert(
            name=data["name"],
            email=data["email"],
            password=data["password"],
            department=data["department"],
            mobileno=data["mobileno"]
        )
        return jsonify(result), 201
    except AuthServiceError as e:
        return jsonify({"error": str(e)}), 400


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    try:
        result = AuthService.login(
            email=data["email"],
            password=data["password"]
        )
        return jsonify(result)
    except AuthServiceError as e:
        return jsonify({"error": str(e)}), 401

@auth_bp.route("/signup/admin", methods=["POST"])
def admin_signup():
    data = request.json
    try:
        result = AuthService.admin_signup(
            name=data["name"],
            email=data["email"],
            password=data["password"]
        )
        return jsonify(result), 201
    except AuthServiceError as e:
        return jsonify({"error": str(e)}), 400