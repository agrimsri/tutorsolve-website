import time
import logging
from app.tasks.email_tasks import send_email_task

def dispatch_email_task(**kwargs):
    t0 = time.perf_counter()
    send_email_task.delay(**kwargs)
    logging.info(f"Celery dispatch took {time.perf_counter() - t0:.4f}s")


# ── Email trigger functions ───────────────────────────────

def send_order_received_email(student_email, student_name, question_title):
    """Sent to student after they post a question."""
    dispatch_email_task(
        to_email=student_email,
        to_name=student_name,
        subject="We received your question — TutorSolve",
        html_content=f"""
            <p>Hi {student_name},</p>
            <p>We've received your question: <strong>{question_title}</strong></p>
            <p>Our team will review it shortly. You'll hear from us once we have experts interested.</p>
            <p>— The TutorSolve Team</p>
        """
    )


def send_price_quote_email(student_email, student_name, question_title, student_price):
    """Sent to student when admin sets and approves the price."""
    dispatch_email_task(
        to_email=student_email,
        to_name=student_name,
        subject="Your quote is ready — TutorSolve",
        html_content=f"""
            <p>Hi {student_name},</p>
            <p>Your quote for <strong>{question_title}</strong> is ready.</p>
            <p>Total: <strong>${student_price:.2f} USD</strong></p>
            <p>Log in to your dashboard to review and pay.</p>
            <p>— The TutorSolve Team</p>
        """
    )


def send_solution_uploaded_email(student_email, student_name, question_title):
    """Sent to student when admin forwards a solution file."""
    dispatch_email_task(
        to_email=student_email,
        to_name=student_name,
        subject="Your solution is ready — TutorSolve",
        html_content=f"""
            <p>Hi {student_name},</p>
            <p>Your solution for <strong>{question_title}</strong> has been uploaded.</p>
            <p>A preview is available. Pay the completion amount to unlock the full file.</p>
            <p>— The TutorSolve Team</p>
        """
    )


def send_expert_broadcast_email(expert_email, expert_name, domain, question_title, question_id):
    """Sent to experts in a domain when a new question is broadcast."""
    dispatch_email_task(
        to_email=expert_email,
        to_name=expert_name,
        subject=f"New {domain} question available — TutorSolve",
        html_content=f"""
            <p>Hi {expert_name},</p>
            <p>A new question in your domain (<strong>{domain}</strong>) is available:</p>
            <p><strong>{question_title}</strong></p>
            <p>Log in to the job board to express interest.</p>
            <p>— The TutorSolve Team</p>
        """
    )


def send_expert_assigned_email(expert_email, expert_name, question_title, payout):
    """Sent to expert when they are assigned to a task."""
    dispatch_email_task(
        to_email=expert_email,
        to_name=expert_name,
        subject="You've been assigned a task — TutorSolve",
        html_content=f"""
            <p>Hi {expert_name},</p>
            <p>You have been assigned the task: <strong>{question_title}</strong></p>
            <p>Payout: <strong>${payout:.2f} USD</strong> (paid after 20-day hold)</p>
            <p>Log in to your dashboard to begin.</p>
            <p>— The TutorSolve Team</p>
        """
    )


def send_kyc_status_email(expert_email, expert_name, status):
    """Sent to expert when their KYC status changes."""
    if status == "approved":
        subject = "Your application is approved — TutorSolve"
        body    = "Congratulations! Your KYC is approved. You can now access the job board."
    else:
        subject = "Your application was not approved — TutorSolve"
        body    = "Unfortunately your KYC application was not approved. Contact support for details."

    dispatch_email_task(
        to_email=expert_email,
        to_name=expert_name,
        subject=subject,
        html_content=f"<p>Hi {expert_name},</p><p>{body}</p><p>— The TutorSolve Team</p>"
    )


def send_payout_released_email(expert_email, expert_name, amount):
    """Sent to expert when their payout clears the 20-day hold."""
    dispatch_email_task(
        to_email=expert_email,
        to_name=expert_name,
        subject="Your payout has been released — TutorSolve",
        html_content=f"""
            <p>Hi {expert_name},</p>
            <p>Your payout of <strong>${amount:.2f} USD</strong> has cleared the 20-day hold and is being processed.</p>
            <p>— The TutorSolve Team</p>
        """
    )


def send_employee_welcome_email(employee_email, employee_name, raw_password):
    """Sent to newly created employee admins with their login credentials."""
    dispatch_email_task(
        to_email=employee_email,
        to_name=employee_name,
        subject="Welcome to the TutorSolve Admin Team",
        html_content=f"""
            <p>Hi {employee_name},</p>
            <p>An administrative account has been created for you on TutorSolve.</p>
            <p>Your login credentials are:</p>
            <ul>
                <li><strong>Email:</strong> {employee_email}</li>
                <li><strong>Password:</strong> {raw_password}</li>
            </ul>
            <p>— The TutorSolve Team</p>
        """
    )
