from flask import current_app
from bson import ObjectId
from datetime import datetime


class OrderServiceError(Exception):
    pass


class OrderService:

    @staticmethod
    def create_order_from_interest(question_id: str, expert_id: str):
        db = current_app.mongo
        questions = db.questions
        orders = db.orders

        q = questions.find_one({"_id": ObjectId(question_id)})

        if not q:
            raise OrderServiceError("Question not found")

        if q.get("assignedExpert"):
            raise OrderServiceError("Question already assigned")

        order_doc = {
            "questionId": ObjectId(question_id),
            "studentId": q.get("studentId"),
            "expertId": ObjectId(expert_id),

            "studentPrice": None,
            "expertPayout": None,

            "pricingApproved": False,
            "advancePaid": False,

            "status": "NEGOTIATION",

            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        }

        result = orders.insert_one(order_doc)

        # Update question status
        questions.update_one(
            {"_id": ObjectId(question_id)},
            {
                "$set": {
                    "status": "NEGOTIATION"
                }
            }
        )

        return str(result.inserted_id)
