from flask import current_app
from bson import ObjectId
from src.core.decorators import auth_required

class ExpertServiceError(Exception):
    pass


class ExpertService:

    @staticmethod
    def get_pending_experts():
        experts = current_app.mongo.experts
        users = current_app.mongo.users

        cursor = experts.find({"approved": False})

        result = []

        for expert in cursor:
            user = users.find_one({"_id": expert["user"]})

            if not user:
                continue

            result.append({
                    "expert_id": str(expert["_id"]),
                    "user_id": str(user["_id"]),
                    "name": user.get("name"),
                    "email": user.get("email"),
                    "department": expert.get("department")
            })

        return result

    @staticmethod
    def approve_expert(expert_id: str):
        experts = current_app.mongo.experts

        result = experts.update_one(
            {"_id": ObjectId(expert_id)},
            {"$set": {"approved": True}}
        )

        if result.matched_count == 0:
            raise ExpertServiceError("Expert not found")

        return True
