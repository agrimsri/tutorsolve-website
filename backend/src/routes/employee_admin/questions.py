from flask import Blueprint, jsonify, request, current_app
from bson import ObjectId
from datetime import datetime
from src.core.decorators import auth_required
from src.services.employee_admin_service import (
    EmployeeAdminService,
    EmployeeAdminServiceError
)
from src.services.question_chat_service import QuestionChatService, QuestionChatServiceError

employee_questions_bp = Blueprint(
    "employee_questions",
    __name__,
    url_prefix="/employee-admin/questions"
)


@employee_questions_bp.route("/", methods=["GET"])
@auth_required(["EmployeeAdmin"])
def get_questions():
    try:
        status = request.args.get("status")
        data = EmployeeAdminService.get_questions_by_status(status)
        return jsonify({
            "count": len(data),
            "questions": data
        })
    except EmployeeAdminServiceError as e:
        return jsonify({"error": str(e)}), 400


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

# -----------------------------
# START REVIEW
# -----------------------------
@employee_questions_bp.route("/start-review/<question_id>", methods=["POST"])
@auth_required(["EmployeeAdmin"])
def start_review(question_id):
    try:
        EmployeeAdminService.start_review(question_id)
        return jsonify({"message": "Review started"})
    except EmployeeAdminServiceError as e:
        return jsonify({"error": str(e)}), 400

@employee_questions_bp.route("/start-negotiation/<question_id>", methods=["POST"])
@auth_required(["EmployeeAdmin"])
def start_negotiation(question_id):
    try:
        EmployeeAdminService.start_negotiation(question_id)
        return jsonify({"message": "Negotiation started"})
    except EmployeeAdminServiceError as e:
        return jsonify({"error": str(e)}), 400

# -----------------------------
# GET QUESTION CHAT
# -----------------------------
@employee_questions_bp.route("/<question_id>/chat", methods=["GET"])
@auth_required(["EmployeeAdmin"])
def get_question_chat(question_id):
    data = QuestionChatService.get_messages(question_id)
    return jsonify({"messages": data})

# -----------------------------
# SEND QUESTION CHAT
# -----------------------------
@employee_questions_bp.route("/<question_id>/chat", methods=["POST"])
@auth_required(["EmployeeAdmin"])
def send_question_chat(question_id):
    body = request.get_json()

    QuestionChatService.send_message(
        question_id,
        "EmployeeAdmin",
        body.get("message")
    )

    return jsonify({"message": "Sent"})

@employee_questions_bp.route("/negotiations", methods=["GET"])
@auth_required(["EmployeeAdmin"])
def get_all_negotiations():
    try:
        data = EmployeeAdminService.get_negotiations()
        return jsonify({"negotiations": data})
    except EmployeeAdminServiceError as e:
        return jsonify({"error": str(e)}), 400


@employee_questions_bp.route("/negotiations/<negotiation_id>", methods=["GET"])
@auth_required(["EmployeeAdmin"])
def get_negotiation(negotiation_id):
    try:
        data = EmployeeAdminService.get_negotiations(negotiation_id)
        
        # Check if there's a pricing request for this question
        db = current_app.mongo
        pricing_request = db.pricing_requests.find_one({
            "questionId": ObjectId(negotiation_id)
        })
        
        # Convert ObjectId to string if pricing request exists
        if pricing_request:
            pricing_request['_id'] = str(pricing_request['_id'])
            pricing_request['questionId'] = str(pricing_request['questionId'])
            if 'createdBy' in pricing_request:
                pricing_request['createdBy'] = str(pricing_request['createdBy'])
            data['pricing_request'] = pricing_request
        else:
            data['pricing_request'] = None
            
        return jsonify({"negotiation": data})
    except EmployeeAdminServiceError as e:
        return jsonify({"error": str(e)}), 400


@employee_questions_bp.route("/<question_id>/pricing", methods=["POST"])
@auth_required(["EmployeeAdmin"])
def request_pricing(question_id):
    try:
        data = request.get_json()
        student_price = data.get("studentPrice")
        expert_payout = data.get("expertPayout")

        if not student_price or not expert_payout:
            return jsonify({"error": "Invalid pricing"}), 400

        if expert_payout >= student_price:
            return jsonify({"error": "Invalid payout"}), 400

        db = current_app.mongo

        question = db.questions.find_one({
            "_id": ObjectId(question_id)
        })

        if not question:
            return jsonify({"error": "Question not found"}), 404

        pricing_doc = {
            "questionId": ObjectId(question_id),
            "studentPrice": student_price,
            "expertPayout": expert_payout,
            "status": "PENDING_APPROVAL",
            "createdBy": ObjectId(request.user["user_id"]),
            "createdAt": datetime.utcnow()
        }

        db.pricing_requests.insert_one(pricing_doc)

        db.questions.update_one(
            {"_id": ObjectId(question_id)},
            {"$set": {"status": "PRICING_PENDING_APPROVAL"}}
        )

        return jsonify({"message": "Pricing request created"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500