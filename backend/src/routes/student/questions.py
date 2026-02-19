from flask import Blueprint, jsonify, request, current_app
from bson import ObjectId
from datetime import datetime
from src.core.decorators import auth_required
from src.services.question_chat_service import QuestionChatService, QuestionChatServiceError
from src.services.question_service import QuestionService, QuestionServiceError
from src.services.notification_service import NotificationService

student_questions_bp = Blueprint(
    "student_questions",
    __name__,
    url_prefix="/student/questions"
)



@student_questions_bp.route("/mine", methods=["GET"])
@auth_required(["Student"])
def get_my_questions():
    try:
        user = request.user
        questions = QuestionService.get_questions_for_student(user["user_id"])
        return jsonify({
            "questions": questions,
            "count": len(questions)
        })
    except QuestionServiceError as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------------------------
# GET SINGLE QUESTION
# -------------------------------------------------
@student_questions_bp.route("/<question_id>", methods=["GET"])
@auth_required(["Student"])
def get_single_question(question_id):
    try:
        student_id = request.user.get("user_id")

        db = current_app.mongo
        questions = db.questions

        q = questions.find_one({
            "_id": ObjectId(question_id),
            "studentId": ObjectId(student_id)
        })

        if not q:
            return jsonify({"error": "Question not found"}), 404

        return jsonify({
            "question_id": str(q["_id"]),
            "title": q.get("title"),
            "description": q.get("description"),
            "department": q.get("department"),
            "status": q.get("status"),
            "createdAt": q.get("createdAt")
        })

    except QuestionServiceError as e:
        print(f"Error in get_single_question: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


# -------------------------------------------------
# CREATE QUESTION
# -------------------------------------------------
@student_questions_bp.route("/create", methods=["POST"])
@auth_required(["Student"])
def create_question():
    try:
        user = request.user
        payload = request.get_json() or {}
        result = QuestionService.create_question(
            student_id=user["user_id"],
            payload=payload
        )

        NotificationService.notify_experts_new_question(
            department=payload["department"],
            question_title=payload["title"]
        )
        return jsonify(result), 201
    except QuestionServiceError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500


# -------------------------------------------------
# QUESTION-LEVEL CHAT (Negotiation Phase)
# -------------------------------------------------
@student_questions_bp.route("/<question_id>/chat", methods=["GET"])
@auth_required(["Student"])
def get_student_question_chat(question_id):
    try:
        data = QuestionChatService.get_messages(question_id)
        return jsonify({"messages": data})

    except QuestionChatServiceError as e:
        print(f"Error in get_student_question_chat: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@student_questions_bp.route("/<question_id>/chat", methods=["POST"])
@auth_required(["Student"])
def send_student_question_chat(question_id):
    try:
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
        print(f"Error in send_student_question_chat: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
