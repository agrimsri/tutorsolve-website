from flask import Blueprint, request, jsonify
from src.services.question_service import QuestionService
from src.models.question_status import QuestionStatus
from src.core.decorators import role_required
from src.models.user import UserRole

admin_questions_bp = Blueprint(
    "admin_questions",
    __name__,
    url_prefix="/admin/questions"
)


@admin_questions_bp.route("", methods=["GET"])
@role_required(UserRole.ADMIN)
def list_questions():
    """List all questions with optional status filter"""
    try:
        status = request.args.get("status")
        
        if status:
            questions = QuestionService.get_questions_by_status(status)
        else:
            questions = QuestionService.get_all_questions()
        
        return jsonify({
            "questions": questions,
            "count": len(questions)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
