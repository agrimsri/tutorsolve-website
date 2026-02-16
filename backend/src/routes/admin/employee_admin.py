from flask import Blueprint, request
from src.core.decorators import auth_required
from src.services.employee_admin_service import EmployeeAdminService, EmployeeAdminServiceError
from src.services.notification_service import NotificationService
from datetime import datetime, timezone


admin_employees_bp = Blueprint(
    "admin_employees",
    __name__,
    url_prefix="/admin/employees-admin"
)



@admin_employees_bp.route("/create", methods=["POST"])
@auth_required(["Admin"])
def create_employee():
    data = request.json
    try:
        EmployeeAdminService.create_employee_admin(
            data["email"],
            data["password"],
            data["name"],
            data["mobileno"]
        )
        NotificationService.notify_employee_admin_new_question(data["name"], data["email"])
        return {"success": True}, 201
    except EmployeeAdminServiceError as e:
        return {"success": False, "error": str(e)}, 400



    