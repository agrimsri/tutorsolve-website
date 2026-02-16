from flask import current_app
import bcrypt
from datetime import datetime, timezone
from src.core.jwt_utils import generate_token
from src.services.department_service import DepartmentService


class AuthServiceError(Exception):
    pass


class AuthService:
    """
    Auth service adapted to existing client MongoDB schema.
    """

    # -----------------------
    # LOGIN (UNCHANGED)
    # -----------------------
    @staticmethod
    def login(email: str, password: str):
        users = current_app.mongo.users
        experts = current_app.mongo.experts

        # 1️⃣ Find user
        user = users.find_one({"email": email})

        if not user:
            raise AuthServiceError("Invalid email or password")

        # 2️⃣ Check verification
        if not user.get("isVerified", False):
            raise AuthServiceError("Account not verified")

        # 3️⃣ Verify password
        if not bcrypt.checkpw(
            password.encode("utf-8"),
            user["password"].encode("utf-8")
        ):
            raise AuthServiceError("Invalid email or password")

        # 4️⃣ Generate JWT (identity only)
        token = generate_token(
            user_id=str(user["_id"]),
            role=user["role"]
        )

        # 5️⃣ If Expert → fetch approval status
        approved = None
        expert = None

        if "Expert" in user.get("role", []):
            expert = experts.find_one({"user": user["_id"]})
            approved = expert.get("approved", False) if expert else False

        # 6️⃣ Return structured response
        return {
            "token": token,
            "user_id": str(user["_id"]),
            "role": user["role"],
            "name": user.get("name"),
            "picture": user.get("picture"),
            "approved": approved,  # None for non-experts
            "department": expert.get("department") if expert else None
        }

    # -----------------------
    # STUDENT SIGNUP (FIXED)
    # -----------------------
    @staticmethod
    def signup_student(name, email, password):
        users = current_app.mongo.users

        if users.find_one({"email": email}):
            raise AuthServiceError("Email already exists")

        hashed_pw = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        user_doc = {
            "name": name,
            "email": email,
            "password": hashed_pw,
            "role": ["Student"],
            "isVerified": True,
            "picture": "",
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc)
        }

        result = users.insert_one(user_doc)

        token = generate_token(str(result.inserted_id), ["Student"])

        return {
            "user_id": str(result.inserted_id),
            "role": ["Student"],
            "name": name,
            "picture": "",
            "token": token
        }

    # -----------------------
    # EXPERT SIGNUP (FIXED)
    # -----------------------
    @staticmethod
    def signup_expert(name, email, password, department, mobileno):
        users = current_app.mongo.users
        experts = current_app.mongo.experts

        if users.find_one({"email": email}):
            raise AuthServiceError("Email already exists")

        # Validate department slug
        if not DepartmentService.is_valid_department(department):
            raise AuthServiceError("Invalid department")

        hashed_pw = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        # 1️⃣ Create user
        user_doc = {
            "name": name,
            "email": email,
            "password": hashed_pw,
            "role": ["Expert"],
            "isVerified": True,
            "picture": "",
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc)
        }

        user_result = users.insert_one(user_doc)

        # 2️⃣ Create expert profile (pending approval)
        experts.insert_one({
            "user": user_result.inserted_id,
            "department": department,  # department is slug
            "mobileno": mobileno,
            "approved": False,
            "document": [],
            "payment": [],
        })

        token = generate_token(str(user_result.inserted_id), ["Expert"])

        # ✅ RETURN SAME SHAPE AS LOGIN
        return {
            "user_id": str(user_result.inserted_id),
            "role": ["Expert"],
            "name": name,
            "picture": "",
            "token": token,
            "approved": False
        }


    @staticmethod
    def admin_signup(name, email, password):
        users = current_app.mongo.users

        if users.find_one({"email": email}):
            raise AuthServiceError("Email already exists")

        hashed_pw = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        user_doc = {
            "name": name,
            "email": email,
            "password": hashed_pw,
            "role": ["Admin"],
            "isVerified": True,
            "picture": "",
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc)
        }

        result = users.insert_one(user_doc)

        token = generate_token(str(result.inserted_id), ["Admin"])

        return {
            "user_id": str(result.inserted_id),
            "role": ["Admin"],
            "name": name,
            "picture": "",
            "token": token
        }
