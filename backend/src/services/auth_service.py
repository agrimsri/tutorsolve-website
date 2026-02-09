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
    # LOGIN (UNCHANGED)
    # -----------------------
    @staticmethod
    def login(email: str, password: str):
        users = current_app.mongo.users

        user = users.find_one({"email": email})

        if not user:
            raise AuthServiceError("Invalid email or password")

        if not user.get("isVerified", False):
            raise AuthServiceError("Account not verified")

        if not bcrypt.checkpw(
            password.encode("utf-8"),
            user["password"].encode("utf-8")
        ):
            raise AuthServiceError("Invalid email or password")

        return {
            "user_id": str(user["_id"]),
            "role": user["role"],
            "name": user.get("name"),
            "picture": user.get("picture")
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
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        }

        result = users.insert_one(user_doc)

        # ✅ RETURN SAME SHAPE AS LOGIN
        return {
            "user_id": str(result.inserted_id),
            "role": ["Student"],
            "name": name,
            "picture": ""
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
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        }

        user_result = users.insert_one(user_doc)

        # 2️⃣ Create expert profile (pending approval)
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

        # ✅ RETURN SAME SHAPE AS LOGIN
        return {
            "user_id": str(user_result.inserted_id),
            "role": ["Expert"],
            "name": name,
            "picture": ""
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
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        }

        result = users.insert_one(user_doc)

        return {
            "user_id": str(result.inserted_id),
            "role": ["Admin"],
            "name": name,
            "picture": ""
        }
