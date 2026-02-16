from flask import Blueprint, jsonify
from src.services.department_service import DepartmentService

departments_bp = Blueprint(
    "departments",
    __name__,
    url_prefix="/departments"
)


@departments_bp.route("", methods=["GET"])
def list_departments():
    departments = DepartmentService.get_all_departments()
    return jsonify({
        "count": len(departments),
        "departments": departments
    })