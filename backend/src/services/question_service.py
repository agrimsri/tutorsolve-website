from flask import current_app
from bson import ObjectId
from datetime import datetime
from src.core.question_status import QuestionStatus


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

        question_doc = {
            # Existing client fields
            "user": ObjectId(student_id),
            "department": payload["department"],
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
