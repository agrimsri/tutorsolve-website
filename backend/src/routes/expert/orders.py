from flask import Blueprint, jsonify, request, current_app
from src.core.decorators import auth_required
from src.services.chat_service import ChatService, ChatServiceError
from bson import ObjectId

expert_orders_bp = Blueprint(
    "expert_orders",
    __name__,
    url_prefix="/expert/orders"
)


@expert_orders_bp.route("/", methods=["GET"])
@auth_required(["Expert"])
def get_expert_orders():
    try:
        db = current_app.mongo
        orders = db.orders
        questions = db.questions
        users = db.users
        experts = db.experts

        # Get current user ID from request context set by auth decorator
        current_user_id = request.user.get("user_id")
        
        if not current_user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Get orders for this expert
        cursor = orders.find({"expertId": ObjectId(current_user_id)}).sort("createdAt", -1)
        
        expert_orders = []
        for order in cursor:
            try:
                question = questions.find_one({"_id": order.get("questionId")})
                student = users.find_one({"_id": order.get("studentId")})
                expert_profile = experts.find_one({"user": ObjectId(current_user_id)})

                expert_orders.append({
                    "order_id": str(order["_id"]),
                    "status": order.get("status"),
                    "createdAt": order.get("createdAt"),
                    "studentPrice": order.get("studentPrice"),
                    "expertPayout": order.get("expertPayout"),
                    "question": {
                        "title": question.get("title") if question else "Unknown Question",
                        "department": question.get("department") if question else "Unknown",
                        "description": question.get("description") if question else ""
                    },
                    "student": {
                        "name": student.get("name") if student else None,
                        "email": student.get("email") if student else None
                    }
                })
            except Exception as e:
                print(f"Error processing order {order.get('_id')}: {str(e)}")
                continue

        return jsonify({"orders": expert_orders})
    except Exception as e:
        print(f"Error in get_expert_orders: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@expert_orders_bp.route("/<order_id>/chat", methods=["GET"])
@auth_required(["Expert"])
def get_expert_chat(order_id):
    try:
        # Get current user ID from request context set by auth decorator
        current_user_id = request.user.get("user_id")
        
        if not current_user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Get messages for this order
        messages = ChatService.get_messages(order_id, current_user_id, "Expert")
        
        return jsonify({"messages": messages})
    except ChatServiceError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"Error in get_expert_chat: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@expert_orders_bp.route("/<order_id>/chat", methods=["POST"])
@auth_required(["Expert"])
def send_expert_chat(order_id):
    try:
        body = request.get_json()
        message = body.get("message")
        
        if not message:
            return jsonify({"error": "Message cannot be empty"}), 400

        # Get current user ID from request context set by auth decorator
        current_user_id = request.user.get("user_id")
        
        if not current_user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Send message
        ChatService.send_message(order_id, current_user_id, "Expert", message)
        
        return jsonify({"message": "Message sent successfully"})
    except ChatServiceError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"Error in send_expert_chat: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
