from flask import current_app
from src.core.task_queue import get_queue
from src.tasks.email_tasks import (
    send_expert_approved_email_task,
    notify_experts_new_question_task,
    notify_employee_admin_creation
)


class NotificationService:

    @staticmethod
    def send_expert_approved_email(email: str, name: str):
        queue = get_queue()
        queue.enqueue(send_expert_approved_email_task, email, name)

    @staticmethod
    def notify_experts_new_question(department: str, question_title: str):
        experts = current_app.mongo.experts
        users = current_app.mongo.users

        experts = experts.find({
            "department": department,
            "approved": True
        })

        emails = []

        for expert in experts:
            user = users.find_one({"_id": expert["user"]})
            if user:
                emails.append(user["email"])

        if emails:
            queue = get_queue()
            queue.enqueue(
                notify_experts_new_question_task,
                emails,
                department,
                question_title
            )

    @staticmethod
    def notify_employee_admin_new_question(name: str, email: str):
        queue = get_queue()
        queue.enqueue(notify_employee_admin_creation, name, email)