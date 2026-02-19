from flask import Blueprint, jsonify, current_app
from bson import ObjectId
from src.core.decorators import auth_required
from src.services.admin_stats_service import AdminStatsService


admin_students_bp = Blueprint(
    "admin_students",
    __name__,
    url_prefix="/admin/students"
)


@admin_students_bp.route("/all", methods=["GET"])
@auth_required(["Admin"])
def get_all_students():
    try:
        students = AdminStatsService.get_all_students()
        
        return jsonify({
            "count": len(students),
            "students": students
        })
    except Exception as e:
        return jsonify({"error": "Failed to fetch students"}), 500


@admin_students_bp.route("/employee-admins/all", methods=["GET"])
@auth_required(["Admin"])
def get_all_employee_admins():
    try:
        employee_admins = AdminStatsService.get_all_employee_admins()
        
        return jsonify({
            "count": len(employee_admins),
            "employee_admins": employee_admins
        })
    except Exception as e:
        return jsonify({"error": "Failed to fetch employee admins"}), 500
