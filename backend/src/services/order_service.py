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

        # Update question status and assigned expert
        questions.update_one(
            {"_id": ObjectId(question_id)},
            {
                "$set": {
                    "status": "NEGOTIATION",
                    "assignedExpert": ObjectId(expert_id)
                }
            }
        )

        return str(result.inserted_id)

    @staticmethod
    def get_order_detail(order_id: str):
        db = current_app.mongo
        orders = db.orders
        questions = db.questions
        users = db.users
        experts = db.experts

        order = orders.find_one({"_id": ObjectId(order_id)})

        if not order:
            raise OrderServiceError("Order not found")

        question = questions.find_one({"_id": order.get("questionId")})
        student = users.find_one({"_id": order.get("studentId")})
        expert = users.find_one({"_id": order.get("expertId")})
        expert_profile = experts.find_one({"user": order.get("expertId")})

        return {
            "order_id": str(order["_id"]),
            "status": order.get("status"),

            "studentPrice": order.get("studentPrice"),
            "expertPayout": order.get("expertPayout"),

            "question": {
                "title": question.get("title") if question else "",
                "description": question.get("description") if question else "",
                "department": question.get("department") if question else ""
            },

            "student": {
                "name": student.get("name") if student else ""
            },

            "expert": {
                "name": expert.get("name") if expert else "",
                "email": expert.get("email") if expert else "",
                "department": expert_profile.get("department") if expert_profile else ""
            }
        }

