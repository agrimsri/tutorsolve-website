from functools import wraps
from flask import request, jsonify, current_app
from src.models.user import UserRole
import jwt
from src.core.jwt_utils import decode_token

def auth_required(roles=None):
    """
    roles: optional list of allowed roles
    Example:
        @auth_required()
        @auth_required(["Admin"])
        @auth_required(["Student", "Admin"])
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):

            auth_header = request.headers.get("Authorization")

            if not auth_header:
                return jsonify({"error": "Authorization header missing"}), 401

            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Invalid Authorization format"}), 401

            token = auth_header.split(" ")[1]

            try:
                decoded = decode_token(token)

                # Attach user to request context
                request.user = {
                    "user_id": decoded["user_id"],
                    "role": decoded["role"]
                }

                # Optional role enforcement
                if roles:
                    user_roles = decoded.get("role", [])
                    if not any(role in user_roles for role in roles):
                        return jsonify({"error": "Access denied"}), 403

            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired"}), 401

            except jwt.InvalidTokenError as e:
                if current_app.config.get("DEBUG"):
                    print("JWT decode error:", str(e))
                return jsonify({"error": "Invalid token"}), 401

            except Exception as e:
                if current_app.config.get("DEBUG"):
                    print("Auth middleware error:", str(e))
                return jsonify({"error": "Authentication failed"}), 401

            return fn(*args, **kwargs)

        return wrapper
    return decorator


def role_required(required_role: UserRole):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user_id = request.headers.get("X-User-ID")

            if not user_id:
                return jsonify({"error": "Authentication required"}), 401

            # Get user from MongoDB
            users = current_app.mongo.users
            user = users.find_one({"_id": user_id})

            if not user or required_role.value not in user.get("role", []):
                return jsonify({"error": "Forbidden"}), 403

            return fn(*args, **kwargs)

        return wrapper
    return decorator
