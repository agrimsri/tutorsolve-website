from flask import Blueprint, jsonify, request
from src.core.decorators import auth_required
from src.services.expert_question_service import (
    ExpertQuestionService,
    ExpertQuestionServiceError
)

expert_questions_bp = Blueprint(
    "expert_questions",
    __name__,
    url_prefix="/expert/questions"
)


@expert_questions_bp.route("/available", methods=["GET"])
@auth_required(["Expert"])
def available_questions():
    try:
        questions = ExpertQuestionService.get_available_questions(
            request.user["user_id"]
        )
        return jsonify({
            "count": len(questions),
            "questions": questions
        })
    except ExpertQuestionServiceError as e:
        return jsonify({"error": str(e)}), 400


@expert_questions_bp.route("/interest/<question_id>", methods=["POST"])
@auth_required(["Expert"])
def express_interest(question_id):
    try:
        ExpertQuestionService.express_interest(
            request.user["user_id"],
            question_id
        )
        return jsonify({"message": "Interest recorded"})
    except ExpertQuestionServiceError as e:
        return jsonify({"error": str(e)}), 400
