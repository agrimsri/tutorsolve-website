from flask import Blueprint, jsonify
from src.core.decorators import auth_required
from src.services.employee_admin_service import (
    EmployeeAdminService,
    EmployeeAdminServiceError
)

employee_questions_bp = Blueprint(
    "employee_questions",
    __name__,
    url_prefix="/employee-admin/questions"
)


@employee_questions_bp.route("/interested", methods=["GET"])
@auth_required(["EmployeeAdmin"])
def get_interested_questions():
    try:
        data = EmployeeAdminService.get_interested_questions()
        return jsonify({
            "count": len(data),
            "questions": data
        })
    except EmployeeAdminServiceError as e:
        return jsonify({"error": str(e)}), 400

@employee_questions_bp.route("/detail/<question_id>", methods=["GET"])
@auth_required(["EmployeeAdmin"])
def get_question_detail(question_id):
    try:
        data = EmployeeAdminService.get_question_detail(question_id)
        return jsonify(data)
    except EmployeeAdminServiceError as e:
        return jsonify({"error": str(e)}), 400
