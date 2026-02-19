from flask import Blueprint, request, current_app, jsonify
from src.core.decorators import auth_required
from src.services.employee_admin_service import EmployeeAdminService, EmployeeAdminServiceError
from src.services.notification_service import NotificationService
from datetime import datetime, timezone
from bson import ObjectId


admin_employees_bp = Blueprint(
    "admin_employees",
    __name__,
    url_prefix="/admin/employee-admin"
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


@admin_employees_bp.route("/pricing-requests", methods=['GET'])
@auth_required(['Admin'])
def get_pricing_requests():
    try:
        db = current_app.mongo
        pricing_requests = list(db.pricing_requests.find())
        
        # Convert ObjectId to string for JSON serialization
        for request in pricing_requests:
            if '_id' in request:
                request['_id'] = str(request['_id'])
            if 'questionId' in request:
                request['questionId'] = str(request['questionId'])
            if 'createdBy' in request:
                request['createdBy'] = str(request['createdBy'])
        
        return jsonify(pricing_requests)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_employees_bp.route("/approve/<pricing_id>", methods=["POST"])
@auth_required(["Admin"])
def approve_pricing(pricing_id):
    try:
        db = current_app.mongo

        pricing = db.pricing_requests.find_one({
            "_id": ObjectId(pricing_id)
        })

        if not pricing:
            return jsonify({"error": "Pricing request not found"}), 404

        db.pricing_requests.update_one(
            {"_id": ObjectId(pricing_id)},
            {"$set": {"status": "APPROVED"}}
        )

        db.questions.update_one(
            {"_id": pricing["questionId"]},
            {
                "$set": {
                    "studentPrice": pricing["studentPrice"],
                    "expertPayout": pricing["expertPayout"],
                    "status": "PRICING_APPROVED"
                }
            }
        )

        return jsonify({"message": "Pricing approved"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

