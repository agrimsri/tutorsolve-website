from flask import Blueprint, jsonify, request, current_app
from bson import ObjectId
from datetime import datetime
from src.core.decorators import auth_required
from src.services.question_chat_service import QuestionChatService, QuestionChatServiceError

student_chat_bp = Blueprint(
    "student_chat",
    __name__,
    url_prefix="/student/questions"
)


# ==================================================
# GET QUESTION CHAT (Student ↔ EmployeeAdmin)
# ==================================================
@student_chat_bp.route("/<question_id>/chat", methods=["GET"])
@auth_required(["Student"])
def get_question_chat(question_id):
    try:
        # Validate question exists and student owns it
        db = current_app.mongo
        question = db.questions.find_one({
            "_id": ObjectId(question_id)
        })

        if not question:
            return jsonify({"error": "Question not found"}), 404

        user_id = request.user.get("user_id")
        if str(question.get("studentId")) != user_id:
            return jsonify({"error": "Access denied"}), 403

        # Fetch chat messages using service
        data = QuestionChatService.get_messages(question_id)
        return jsonify({"messages": data})

    except QuestionChatServiceError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================================================
# SEND QUESTION CHAT MESSAGE
# ==================================================
@student_chat_bp.route("/<question_id>/chat", methods=["POST"])
@auth_required(["Student"])
def send_question_chat(question_id):
    try:
        # Validate question exists and student owns it
        db = current_app.mongo
        question = db.questions.find_one({
            "_id": ObjectId(question_id)
        })

        if not question:
            return jsonify({"error": "Question not found"}), 404

        user_id = request.user.get("user_id")
        if str(question.get("studentId")) != user_id:
            return jsonify({"error": "Access denied"}), 403

        # Send message using service
        body = request.get_json()
        message = body.get("message")

        if not message:
            return jsonify({"error": "Message cannot be empty"}), 400

        QuestionChatService.send_message(
            question_id,
            "Student",
            message
        )

        return jsonify({"message": "Sent"})

    except QuestionChatServiceError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
