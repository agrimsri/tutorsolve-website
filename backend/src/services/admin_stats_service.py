from flask import current_app
from bson import ObjectId


class AdminStatsServiceError(Exception):
    pass


class AdminStatsService:

    @staticmethod
    def get_dashboard_stats():
        db = current_app.mongo
        users = db.users
        experts = db.experts
        questions = db.questions
        orders = db.orders

        # Count total users by role
        total_users = users.count_documents({})
        total_experts = experts.count_documents({})
        total_students = users.count_documents({"role": ["Student"]})
        total_admins = users.count_documents({"role": {"$in": [["Admin"], ["Admin", "EmployeeAdmin"]]}})
        
        # Count questions by status
        total_questions = questions.count_documents({})
        pending_questions = questions.count_documents({"status": "CREATED"})
        assigned_questions = questions.count_documents({"status": "ASSIGNED"})
        negotiation_questions = questions.count_documents({"status": "NEGOTIATION"})
        
        # Count orders by status
        total_orders = orders.count_documents({})
        active_orders = orders.count_documents({"status": {"$in": ["NEGOTIATION", "PRICING_APPROVED", "ADVANCE_PAID"]}})
        completed_orders = orders.count_documents({"status": "COMPLETED"})
        
        # Expert approval stats
        pending_experts = experts.count_documents({"approved": False})
        approved_experts = experts.count_documents({"approved": True})
        
        # Recent activity (last 7 days)
        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        recent_questions = questions.count_documents({"createdAt": {"$gte": week_ago}})
        recent_orders = orders.count_documents({"createdAt": {"$gte": week_ago}})
        recent_registrations = users.count_documents({"createdAt": {"$gte": week_ago}})

        return {
            "users": {
                "total": total_users,
                "students": total_students,
                "experts": total_experts,
                "admins": total_admins,
                "recent_registrations": recent_registrations
            },
            "questions": {
                "total": total_questions,
                "pending": pending_questions,
                "assigned": assigned_questions,
                "in_negotiation": negotiation_questions,
                "recent": recent_questions
            },
            "orders": {
                "total": total_orders,
                "active": active_orders,
                "completed": completed_orders,
                "recent": recent_orders
            },
            "experts": {
                "pending_approval": pending_experts,
                "approved": approved_experts,
                "approval_rate": round((approved_experts / total_experts * 100) if total_experts > 0 else 0, 1)
            }
        }

    @staticmethod
    def get_all_experts():
        db = current_app.mongo
        experts = db.experts
        users = db.users

        cursor = experts.find({})
        
        result = []

        for expert in cursor:
            user = users.find_one({"_id": expert["user"]})

            if not user:
                continue

            result.append({
                "expert_id": str(expert["_id"]),
                "user_id": str(user["_id"]),
                "name": user.get("name"),
                "email": user.get("email"),
                "department": expert.get("department"),
                "approved": expert.get("approved", False),
                "created_at": expert.get("createdAt"),
                "mobile": user.get("mobileno")
            })

        return result

    @staticmethod
    def get_all_students():
        db = current_app.mongo
        users = db.users
        
        cursor = users.find({"role": ["Student"]})
        
        result = []

        for student in cursor:
            result.append({
                "student_id": str(student["_id"]),
                "name": student.get("name"),
                "email": student.get("email"),
                "mobile": student.get("mobileno"),
                "created_at": student.get("createdAt"),
                "status": "Active" if student.get("isActive", True) else "Inactive"
            })

        return result

    @staticmethod
    def get_all_employee_admins():
        db = current_app.mongo
        users = db.users
        
        cursor = users.find({"role": "EmployeeAdmin"})
        
        result = []

        for employee_admin in cursor:
            
            result.append({
                "employee_admin_id": str(employee_admin["_id"]),
                "name": employee_admin.get("name"),
                "email": employee_admin.get("email"),
                "mobile": employee_admin.get("mobileno"),
                "created_at": employee_admin.get("createdAt"),
                "role": "Employee Admin",
                "status": "Active" if employee_admin.get("isActive", True) else "Inactive"
            })

        return result
