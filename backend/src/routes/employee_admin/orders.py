from flask import Blueprint, jsonify, request, current_app
from src.core.decorators import auth_required
from src.services.order_service import (
    OrderService,
    OrderServiceError
)
from src.services.chat_service import ChatService
from bson import ObjectId

employee_orders_bp = Blueprint(
    "employee_orders",
    __name__,
    url_prefix="/employee-admin/orders"
)


@employee_orders_bp.route("/create-from-interest", methods=["POST"])
@auth_required(["EmployeeAdmin"])
def create_order_from_interest():
    data = request.get_json()

    question_id = data.get("questionId")
    expert_id = data.get("expertId")

    if not question_id or not expert_id:
        return jsonify({"error": "Missing fields"}), 400

    try:
        order_id = OrderService.create_order_from_interest(
            question_id,
            expert_id
        )

        return jsonify({
            "message": "Order created",
            "order_id": order_id
        })

    except OrderServiceError as e:
        return jsonify({"error": str(e)}), 400

@employee_orders_bp.route("/detail/<order_id>", methods=["GET"])
@auth_required(["EmployeeAdmin"])
def get_order_detail(order_id):
    try:
        data = OrderService.get_order_detail(order_id)
        return jsonify(data)
    except OrderServiceError as e:
        return jsonify({"error": str(e)}), 400

@employee_orders_bp.route("/negotiations", methods=["GET"])
@auth_required(["EmployeeAdmin"])
def get_negotiations():
    try:
        db = current_app.mongo
        orders = db.orders
        questions = db.questions
        users = db.users
        experts = db.experts

        # Check if collections exist
        if orders is None or questions is None or users is None or experts is None:
            return jsonify({"error": "Database collections not available"}), 500

        # Get orders with status "NEGOTIATION"
        cursor = orders.find({"status": "NEGOTIATION"}).sort("createdAt", -1)
        
        negotiations = []
        for order in cursor:
            try:
                question_id = order.get("questionId")
                student_id = order.get("studentId")
                expert_id = order.get("expertId")
                
                print(f"Processing order {order.get('_id')}: question={question_id}, student={student_id}, expert={expert_id}")
                
                # Find related documents with better error handling
                question = questions.find_one({"_id": question_id}) if question_id else None
                student = users.find_one({"_id": student_id}) if student_id else None
                expert = users.find_one({"_id": expert_id}) if expert_id else None
                expert_profile = experts.find_one({"user": expert_id}) if expert_id else None

                if not question:
                    print(f"Warning: Question {question_id} not found for order {order.get('_id')}")
                if not student:
                    print(f"Warning: Student {student_id} not found for order {order.get('_id')}")
                if not expert:
                    print(f"Warning: Expert {expert_id} not found for order {order.get('_id')}")

                negotiations.append({
                    "order_id": str(order["_id"]),
                    "status": order.get("status"),
                    "createdAt": order.get("createdAt"),
                    "studentPrice": order.get("studentPrice"),
                    "expertPayout": order.get("expertPayout"),
                    "question": {
                        "title": question.get("title") if question else "Unknown Question",
                        "department": question.get("department") if question else "Unknown"
                    },
                    "student": {
                        "name": student.get("name") if student else "Unknown Student"
                    },
                    "expert": {
                        "name": expert.get("name") if expert else "Unknown Expert",
                        "email": expert.get("email") if expert else "Unknown",
                        "department": expert_profile.get("department") if expert_profile else "Unknown"
                    }
                })
            except Exception as e:
                print(f"Error processing order {order.get('_id')}: {str(e)}")
                continue

        print(f"Found {len(negotiations)} negotiations")
        return jsonify({"orders": negotiations})
    except Exception as e:
        print(f"Error in get_negotiations: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@employee_orders_bp.route("/<order_id>/chat", methods=["GET"])
@auth_required(["EmployeeAdmin"])
def get_employee_admin_chat(order_id):
    try:
        # Get current user ID from request context set by auth decorator
        current_user_id = request.user.get("user_id")
        
        if not current_user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Get messages for this order (EmployeeAdmin sees all messages)
        messages = ChatService.get_messages(order_id, current_user_id, "EmployeeAdmin")
        
        return jsonify({"messages": messages})
    except Exception as e:
        print(f"Error in get_employee_admin_chat: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@employee_orders_bp.route("/<order_id>/chat", methods=["POST"])
@auth_required(["EmployeeAdmin"])
def send_employee_admin_chat(order_id):
    try:
        body = request.get_json()
        message = body.get("message")
        
        if not message:
            return jsonify({"error": "Message cannot be empty"}), 400

        # Get current user ID from request context set by auth decorator
        current_user_id = request.user.get("user_id")
        
        if not current_user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Send message as EmployeeAdmin
        ChatService.send_message(order_id, current_user_id, "EmployeeAdmin", message)
        
        return jsonify({"message": "Message sent successfully"})
    except Exception as e:
        print(f"Error in send_employee_admin_chat: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500