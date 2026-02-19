from flask import current_app
from bson import ObjectId
from datetime import datetime


class QuestionChatServiceError(Exception):
    pass


class QuestionChatService:

    @staticmethod
    def get_messages(question_id: str):
        db = current_app.mongo
        messages = db.question_messages

        cursor = messages.find({
            "questionId": ObjectId(question_id)
        }).sort("createdAt", 1)

        return [{
            "senderRole": msg.get("senderRole"),
            "message": msg.get("message"),
            "createdAt": msg.get("createdAt")
        } for msg in cursor]

    @staticmethod
    def send_message(question_id: str, sender_role: str, message: str):
        db = current_app.mongo
        messages = db.question_messages

        messages.insert_one({
            "questionId": ObjectId(question_id),
            "senderRole": sender_role,
            "message": message,
            "createdAt": datetime.utcnow()
        })

        return True
