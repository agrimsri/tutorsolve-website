from flask import current_app
from bson import ObjectId


class ExpertQuestionServiceError(Exception):
    pass


class ExpertQuestionService:

    @staticmethod
    def get_available_questions(expert_user_id: str):
        experts = current_app.mongo.experts

        expert = experts.find_one({"user": ObjectId(expert_user_id)})

        if not expert:
            raise ExpertQuestionServiceError("Expert profile not found")

        department = expert.get("department")

        questions = current_app.mongo.questions

        cursor = questions.find({
            "department": department,
            "status": {"$in": ["CREATED", "UNDER_REVIEW", "NEGOTIATION"]},
            "assignedExpert": None,
        }).sort("createdAt", -1)

        result = []

        for q in cursor:
            interested_experts = q.get("interestedExperts", [])
            has_applied = ObjectId(expert_user_id) in interested_experts

            result.append({
                "question_id": str(q["_id"]),
                "title": q.get("title"),
                "description": q.get("description"),
                "department": q.get("department"),
                "createdAt": q.get("createdAt"),
                "has_applied": has_applied
            })

        return result

    @staticmethod
    def express_interest(expert_user_id: str, question_id: str):
        questions = current_app.mongo.questions

        result = questions.update_one(
            {
                "_id": ObjectId(question_id),
                "status": {"$in": ["CREATED", "UNDER_REVIEW", "NEGOTIATION"]},
                "assignedExpert": None
            },
            {
                "$addToSet": {
                    "interestedExperts": ObjectId(expert_user_id)
                }
            }
        )

        if result.matched_count == 0:
            raise ExpertQuestionServiceError("Question not available")

        return True
