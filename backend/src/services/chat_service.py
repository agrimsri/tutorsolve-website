from flask import current_app
from bson import ObjectId
from datetime import datetime


class ChatServiceError(Exception):
    pass


class ChatService:

    # ---------------------------------------
    # INTERNAL VALIDATION
    # ---------------------------------------

    @staticmethod
    def _validate_order_access(order_id: str, user_id: str, role: str):
        """
        Ensure the user has access to this order.
        """
        db = current_app.mongo
        orders = db.orders

        order = orders.find_one({"_id": ObjectId(order_id)})

        if not order:
            raise ChatServiceError("Order not found")

        # Employee Admin can access all orders
        if role == "EmployeeAdmin":
            return order

        # Student can access only their own order
        if role == "Student":
            if str(order.get("studentId")) != user_id:
                raise ChatServiceError("Access denied")
            return order

        # Expert can access only assigned order
        if role == "Expert":
            if str(order.get("expertId")) != user_id:
                raise ChatServiceError("Access denied")
            return order

        raise ChatServiceError("Invalid role")

    # ---------------------------------------
    # FETCH MESSAGES
    # ---------------------------------------

    @staticmethod
    def get_messages(order_id: str, user_id: str, role: str):
        db = current_app.mongo
        messages = db.order_messages

        order = ChatService._validate_order_access(order_id, user_id, role)

        query = {
            "orderId": ObjectId(order_id)
        }

        # Visibility logic
        if role == "Student":
            query["visibleTo"] = "STUDENT"

        elif role == "Expert":
            query["visibleTo"] = "EXPERT"

        # EmployeeAdmin sees everything (no filter)

        cursor = messages.find(query).sort("createdAt", 1)

        result = []

        for msg in cursor:
            result.append({
                "senderRole": msg.get("senderRole"),
                "message": msg.get("message"),
                "createdAt": msg.get("createdAt")
            })

        return result

    # ---------------------------------------
    # SEND MESSAGE
    # ---------------------------------------

    @staticmethod
    def send_message(order_id: str, user_id: str, role: str, message: str):
        if not message:
            raise ChatServiceError("Message cannot be empty")

        db = current_app.mongo
        messages = db.order_messages

        order = ChatService._validate_order_access(order_id, user_id, role)

        # Determine visibility based on role
        if role == "Student":
            visible_to = "STUDENT"

        elif role == "Expert":
            visible_to = "EXPERT"

        elif role == "EmployeeAdmin":
            # Admin must specify target via route logic
            # Default to STUDENT (for now)
            visible_to = "STUDENT"

        else:
            raise ChatServiceError("Invalid sender role")

        messages.insert_one({
            "orderId": ObjectId(order_id),
            "senderRole": role,
            "message": message,
            "visibleTo": visible_to,
            "createdAt": datetime.utcnow()
        })

        return True
