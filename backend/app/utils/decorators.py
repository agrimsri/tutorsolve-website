from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt
from app.utils.constants import Role


def role_required(*roles):
    """Decorator that checks JWT is valid and role is in the allowed list."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            role = claims.get("role")
            if not role or role not in roles:
                return jsonify({"error": "Forbidden"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


def student_required(f):
    return role_required(Role.STUDENT)(f)

def expert_required(f):
    return role_required(Role.EXPERT)(f)

def admin_required(f):
    return role_required(Role.EMPLOYEE)(f)

def superadmin_required(f):
    return role_required(Role.SUPER_ADMIN)(f)
