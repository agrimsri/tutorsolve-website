from src.core.mailer import Mailer


def send_expert_approved_email_task(email: str, name: str):
    subject = "Your TutorSolve Account Has Been Approved 🎉"

    body = f"""
    <h2>Congratulations {name}!</h2>
    <p>Your expert account has been approved.</p>
    """

    Mailer.send_email(email, subject, body)


def notify_experts_new_question_task(emails: list, department: str, question_title: str):
    subject = f"New Question in {department}"

    body = f"""
    <h3>New Question Posted</h3>
    <p><strong>{question_title}</strong></p>
    """

    for email in emails:
        Mailer.send_email(email, subject, body)


def notify_employee_admin_creation(name: str, email: str):
    subject = f"Admin employee access to tutorsolve"
    
    body = f"""
    <h2>Hello {name},</h2>
    <p>Congratulations! You have been granted admin employee access to TutorSolve.</p>
    <p>Please log in to your account to get started.</p>
    """
    
    Mailer.send_email(email, subject, body)

    

