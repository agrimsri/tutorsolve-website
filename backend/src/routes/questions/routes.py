
from flask import Blueprint, request, jsonify
from src.services.question_service import QuestionService, QuestionServiceError
from src.core.decorators import auth_required

questions_bp = Blueprint("questions", __name__, url_prefix="/questions")



@questions_bp.route("", methods=["POST"])
@auth_required(["Student"])
def create_question():
    try:
        user = request.user
        payload = request.get_json() or {}
        result = QuestionService.create_question(
            student_id=user["user_id"],
            payload=payload
        )
        return jsonify(result), 201
    except QuestionServiceError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500



@questions_bp.route("/mine", methods=["GET"])
@auth_required(["Student"])
def get_my_questions():
    try:
        user = request.user
        questions = QuestionService.get_questions_for_student(user["user_id"])
        return jsonify({
            "questions": questions,
            "count": len(questions)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
