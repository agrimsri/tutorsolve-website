from flask import current_app
from bson import ObjectId
from datetime import datetime
from src.models.question_status import QuestionStatus
from src.services.department_service import DepartmentService



class QuestionServiceError(Exception):
    pass


class QuestionService:

    @staticmethod
    def create_question(student_id: str, payload: dict):
        questions = current_app.mongo.questions

        required_fields = ["department", "title", "description"]

        for field in required_fields:
            if field not in payload or not payload[field]:
                raise QuestionServiceError(f"Missing field: {field}")
        
        department_slug = payload["department"]
        if not DepartmentService.is_valid_department(department_slug):
            raise QuestionServiceError("Invalid department")

        question_doc = {
            # Existing client fields
            "studentId": ObjectId(student_id),
            "department": department_slug,
            "title": payload["title"],
            "description": payload["description"],
            "willingtopay": payload.get("willingtopay"),
            "duedate": payload.get("duedate"),
            "attachments": payload.get("attachments", []),
            "slug": payload.get("slug"),

            # Module 3 workflow fields
            "status": QuestionStatus.CREATED,
            "adminReview": None,
            "assignment": None,
            "order": None,

            # Timestamps
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        }

        result = questions.insert_one(question_doc)

        return {
            "question_id": str(result.inserted_id),
            "status": QuestionStatus.CREATED
        }

    @staticmethod
    def get_questions_by_status(status: str):
        questions = current_app.mongo.questions

        cursor = questions.find({"status": status}).sort("createdAt", -1)

        result = []
        for q in cursor:
            result.append({
                "id": str(q["_id"]),
                "title": q.get("title"),
                "department": q.get("department"),
                "status": q.get("status"),
                "createdAt": q.get("createdAt")
            })

        return result

    @staticmethod
    def get_questions_for_student(student_id: str):
        questions = current_app.mongo.questions

        cursor = questions.find(
            {"studentId": ObjectId(student_id)}
        ).sort("createdAt", -1)

        result = []
        for q in cursor:
            result.append({
                "id": str(q["_id"]),
                "title": q.get("title"),
                "department": q.get("department"),
                "status": q.get("status"),
                "createdAt": q.get("createdAt")
            })

        return result

