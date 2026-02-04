from functools import wraps
from flask import request, jsonify
from src.models.user import User, UserRole


def role_required(required_role: UserRole):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user_id = request.headers.get("X-User-ID")

            if not user_id:
                return jsonify({"error": "Authentication required"}), 401

            user = User.query.get(user_id)

            if not user or user.role != required_role:
                return jsonify({"error": "Forbidden"}), 403

            return fn(*args, **kwargs)

        return wrapper
    return decorator
