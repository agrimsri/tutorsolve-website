from flask import current_app
from bson import ObjectId
from src.core.decorators import auth_required
import bcrypt
from datetime import datetime, timezone

class EmployeeAdminServiceError(Exception):
    pass


class EmployeeAdminService:

    @staticmethod
    def create_employee_admin(email: str, password: str, name: str, mobileno: str = None):

        users = current_app.mongo.users

        employee_admin = users.find_one({"email": email})
        if employee_admin:
            raise EmployeeAdminServiceError("Employee admin already exists")

        hashed_pw = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")
        
        user_doc = {
            "email": email,
            "password": hashed_pw,
            "name": name,
            "mobileno": mobileno,
            "role": ["EmployeeAdmin"],
            "isVerified": True,
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc)
        }
        
        users.insert_one(user_doc)
        
        return str(user_doc["_id"])


    @staticmethod
    def get_interested_questions():
        db = current_app.mongo
        questions = db.questions
        users = db.users
        experts = db.experts

        cursor = questions.find({
            "interestedExperts": {
                "$exists": True,
                "$not": {"$size": 0}
            },
            "assignedExpert": None,
            "status": "CREATED"
        }).sort("createdAt", -1)

        results = []

        for q in cursor:
            student = users.find_one({"_id": q.get("studentId")})

            department = db.departments.find_one({"slug": q.get("department")})
            department_name = department.get("name") if department else None

            interested_experts = []

            for expert_id in q.get("interestedExperts", []):
                expert_user = users.find_one({"_id": expert_id})
                expert = experts.find_one({"user": expert_id})

                if expert_user and expert:
                    interested_experts.append({
                        "expert_id": str(expert_id),
                        "name": expert_user.get("name"),
                        "email": expert_user.get("email"),
                        "department": department_name
                    })

            results.append({
                "question_id": str(q["_id"]),
                "title": q.get("title"),
                "description": q.get("description"),
                "department": department_name,
                "student_name": student.get("name") if student else "Unknown",
                "interested_count": len(interested_experts),
                # "interested_experts": interested_experts
            })

        return results

    
    @staticmethod
    def get_question_detail(question_id: str):
        db = current_app.mongo
        questions = db.questions
        users = db.users
        experts = db.experts

        q = questions.find_one({"_id": ObjectId(question_id)})

        if not q:
            raise EmployeeAdminServiceError("Question not found")

        student = users.find_one({"_id": q.get("studentId")})

        interested_experts = []

        for expert_id in q.get("interestedExperts", []):
            expert_user = users.find_one({"_id": expert_id})
            expert = experts.find_one({"user": expert_id})

            if expert_user and expert:
                interested_experts.append({
                    "expert_id": str(expert_id),
                    "name": expert_user.get("name"),
                    "email": expert_user.get("email"),
                    "department": expert.get("department")
                })

        return {
            "question_id": str(q["_id"]),
            "title": q.get("title"),
            "description": q.get("description"),
            "department": q.get("department"),
            "student_name": student.get("name") if student else "Unknown",
            "interested_experts": interested_experts
        }



