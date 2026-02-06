from flask import current_app
import bcrypt
from datetime import datetime


class AuthServiceError(Exception):
    pass


class AuthService:
    """
    Auth service adapted to existing client MongoDB schema.
    """

    # -----------------------
    # LOGIN
    # -----------------------
    @staticmethod
    def login(email: str, password: str):
        users = current_app.mongo.users
        experts = current_app.mongo.experts

        user = users.find_one({"email": email})

        if not user:
            raise AuthServiceError("Invalid email or password")

        # Account must be verified
        if not user.get("isVerified", False):
            raise AuthServiceError("Account not verified")

        # Password check (bcrypt)
        if not bcrypt.checkpw(
            password.encode("utf-8"),
            user["password"].encode("utf-8")
        ):
            raise AuthServiceError("Invalid email or password")

        # Expert-specific approval check
        if "Expert" in user.get("role", []):
            expert = experts.find_one({"user": user["_id"]})
            if not expert or not expert.get("approve", False):
                raise AuthServiceError("Expert account not approved yet")

        return {
            "user_id": str(user["_id"]),
            "email": user["email"],
            "role": user["role"],
            "name": user.get("name"),
            "picture": user.get("picture")
        }

    # -----------------------
    # STUDENT SIGNUP
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
            "isVerified": True,   # client schema expects this
            "picture": "",
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        }

        result = users.insert_one(user_doc)

        return str(result.inserted_id)

    # -----------------------
    # EXPERT SIGNUP
    # -----------------------
    @staticmethod
    def signup_expert(name, email, password, department, mobileno):
        users = current_app.mongo.users
        experts = current_app.mongo.experts

        if users.find_one({"email": email}):
            raise AuthServiceError("Email already exists")

        hashed_pw = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        # 1 Create user
        user_doc = {
            "name": name,
            "email": email,
            "password": hashed_pw,
            "role": ["Expert"],
            "isVerified": True,
            "picture": "",
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        }

        user_result = users.insert_one(user_doc)

        # 2 Create expert profile (pending approval)
        experts.insert_one({
            "user": user_result.inserted_id,
            "department": department,
            "mobileno": mobileno,
            "approve": False,
            "document": [],
            "payment": [],
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        })

        return str(user_result.inserted_id)
