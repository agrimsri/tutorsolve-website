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
            "interested_experts": interested_experts,
            "status": q.get("status"),
            "createdAt": q.get("createdAt"),
            "updatedAt": q.get("updatedAt")
        }


    @staticmethod
    def get_questions_by_status(status: str = None):
        db = current_app.mongo
        questions = db.questions
        users = db.users
        departments = db.departments

        query = {}
        if status:
            query["status"] = status.upper()

        cursor = questions.find(query).sort("createdAt", -1)

        results = []

        for q in cursor:
            student = users.find_one({"_id": q.get("studentId")})
            
            department = db.departments.find_one({"slug": q.get("department")})
            department_name = department.get("name") if department else None

            interested_count = len(q.get("interestedExperts", []))
            
            assigned_expert_name = None
            if q.get("assignedExpert"):
                expert_user = users.find_one({"_id": q.get("assignedExpert")})
                assigned_expert_name = expert_user.get("name") if expert_user else None

            results.append({
                "question_id": str(q["_id"]),
                "title": q.get("title"),
                "description": q.get("description"),
                "department": department_name,
                "status": q.get("status"),
                "student_name": student.get("name") if student else "Unknown",
                "interested_count": interested_count,
                "assigned_expert": assigned_expert_name,
                "created_at": q.get("createdAt"),
                "updated_at": q.get("updatedAt")
            })

        return results


    @staticmethod
    def start_review(question_id: str):
        db = current_app.mongo
        questions = db.questions

        result = questions.update_one(
            {"_id": ObjectId(question_id)},
            {
                "$set": {
                    "status": "UNDER_REVIEW",
                    "updatedAt": datetime.now(timezone.utc)
                }
            }
        )

        if result.matched_count == 0:
            raise EmployeeQuestionServiceError("Question not found")

        return True


    @staticmethod
    def start_negotiation(question_id: str):
        db = current_app.mongo
        questions = db.questions

        result = questions.update_one(
            {"_id": ObjectId(question_id)},
            {
                "$set": {
                    "status": "NEGOTIATION",
                    "updatedAt": datetime.now(timezone.utc)
                }
            }
        )

        if result.matched_count == 0:
            raise EmployeeQuestionServiceError("Question not found")

        return True


    @staticmethod
    def get_negotiations(negotiation_id: str = None):
        try:
            db = current_app.mongo
            questions = db.questions
            users = db.users
            experts = db.experts

            if negotiation_id:
                negotiation = questions.find_one({"_id": ObjectId(negotiation_id)})
                if not negotiation:
                    return None
                
                student = users.find_one({"_id": negotiation.get("studentId")})
                interested_experts = []
                for expert_id in negotiation.get("interestedExperts", []):
                    expert_user = users.find_one({"_id": expert_id})
                    expert = experts.find_one({"user": expert_id})
                    if expert_user and expert:
                        interested_experts.append({
                            "expert_id": str(expert_id),
                            "name": expert_user.get("name"),
                            "email": expert_user.get("email"),
                            "department": expert.get("department", "Unknown")
                        })
                
                return {
                    "_id": str(negotiation["_id"]),
                    "question": {
                        "_id": str(negotiation["_id"]),
                        "title": negotiation.get("title", "Unknown Question"),
                        "department": negotiation.get("department", "Unknown"),
                        "description": negotiation.get("description", ""),
                        "status": negotiation.get("status", "Unknown"),
                        "interested_experts": interested_experts,
                        "created_at": negotiation.get("createdAt"),
                        "updated_at": negotiation.get("updatedAt")
                    },
                    "student": {
                        "name": student.get("name") if student else "Unknown Student"
                    }
                }
            
            cursor = questions.find({
                "status": {"$in": ["NEGOTIATION", "PRICING_PENDING_APPROVAL", "PRICING_APPROVED"]}

            }).sort("createdAt", -1)
            negotiations = []
            for q in cursor:
                try:
                    student = users.find_one({"_id": q.get("studentId")})
                    if not q:
                        return []

                    interested_experts = []
                    for expert_id in q.get("interestedExperts", []):
                        expert_user = users.find_one({"_id": expert_id})
                        expert = experts.find_one({"user": expert_id})
                        if expert_user and expert:
                            interested_experts.append({
                                "expert_id": str(expert_id),
                                "name": expert_user.get("name"),
                                "email": expert_user.get("email"),
                                "department": expert.get("department", "Unknown")
                            })

                    negotiations.append({
                        "_id": str(q["_id"]),
                        "question": {
                            "_id": str(q["_id"]),
                            "title": q.get("title") if q else "Unknown Question",
                            "department": q.get("department") if q else "Unknown",
                            "description": q.get("description") if q else "Unknown",
                            "status": q.get("status") if q else "Unknown",
                            "interested_experts": interested_experts,
                            "created_at": q.get("createdAt") if q else "Unknown",
                            "updated_at": q.get("updatedAt") if q else "Unknown"
                        },
                        "student": {
                            "name": student.get("name") if student else "Unknown Student"
                        }
                    })
                except Exception as e:
                    print(f"Error processing order {q.get('_id')}: {str(e)}")
                    continue

            print(f"Found {len(negotiations)} negotiations")
            return negotiations
        except Exception as e:
            print(f"Error in get_negotiations: {str(e)}")
            return []

    