import time
import logging
from app.tasks.email_tasks import send_email_task
from app.utils.currency import money_label

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


def send_price_quote_email(student_email, student_name, question_title, student_price, currency=None):
    """Sent to student when admin sets and approves the price."""
    dispatch_email_task(
        to_email=student_email,
        to_name=student_name,
        subject="Your quote is ready — TutorSolve",
        html_content=f"""
            <p>Hi {student_name},</p>
            <p>Your quote for <strong>{question_title}</strong> is ready.</p>
            <p>Total: <strong>{money_label(student_price, currency)} {((currency or 'inr').upper())}</strong></p>
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
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, Helvetica, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px;">

    <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
            <td align="center">

                <table width="600" cellpadding="0" cellspacing="0"
                       style="background-color: #ffffff; border-radius: 8px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">

                    <tr>
                        <td>

                            <h2 style="color: #1f2937; margin-top: 0;">
                                New Question Available
                            </h2>

                            <p style="font-size: 16px; color: #374151;">
                                Hi <strong>{expert_name}</strong>,
                            </p>

                            <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                                A new question matching your expertise in
                                <strong>{domain}</strong> has been posted on TutorSolve.
                            </p>

                            <div style="
                                background-color: #f9fafb;
                                border-left: 4px solid #2563eb;
                                padding: 15px;
                                margin: 20px 0;
                            ">
                                <strong style="font-size: 17px; color: #111827;">
                                    {question_title}
                                </strong>
                            </div>

                            <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                                Visit your dashboard to review the question and
                                express your interest.
                            </p>

                            <p style="text-align: center; margin: 30px 0;">
                                <a href="https://www.tutorsolve.com"
                                   style="
                                   background-color: #2563eb;
                                   color: white;
                                   text-decoration: none;
                                   padding: 12px 24px;
                                   border-radius: 6px;
                                   font-weight: bold;
                                   display: inline-block;
                                   ">
                                    View Job Board
                                </a>
                            </p>

                            <hr style="border: none; border-top: 1px solid #e5e7eb;">

                            <p style="font-size: 14px; color: #6b7280;">
                                Thank you,<br>
                                <strong>The TutorSolve Team</strong>
                            </p>

                        </td>
                    </tr>

                </table>

            </td>
        </tr>
    </table>

</body>
</html>
"""
    )


def send_expert_assigned_email(expert_email, expert_name, question_title, payout):
    """Sent to expert when they are assigned to a task."""
    dispatch_email_task(
        to_email=expert_email,
        to_name=expert_name,
        subject="You've been assigned a task — TutorSolve",
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, Helvetica, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px;">

    <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
            <td align="center">

                <table width="600" cellpadding="0" cellspacing="0"
                       style="background-color: #ffffff; border-radius: 8px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">

                    <tr>
                        <td>

                            <h2 style="color: #1f2937; margin-top: 0;">
                                Task Assignment Notification
                            </h2>

                            <p style="font-size: 16px; color: #374151;">
                                Hi <strong>{expert_name}</strong>,
                            </p>

                            <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                                Congratulations! A task has been assigned to you.
                            </p>

                            <div style="
                                background-color: #f9fafb;
                                border-left: 4px solid #2563eb;
                                padding: 15px;
                                margin: 20px 0;
                            ">
                                <strong style="font-size: 17px; color: #111827;">
                                    {question_title}
                                </strong>
                            </div>

                            <div style="
                                background-color: #eff6ff;
                                border: 1px solid #bfdbfe;
                                border-radius: 6px;
                                padding: 15px;
                                margin: 20px 0;
                            ">
                                <p style="margin: 0; font-size: 16px; color: #1e40af;">
                                    <strong>Payout:</strong> ${payout:.2f} USD
                                </p>
                                <p style="margin: 8px 0 0 0; font-size: 14px; color: #6b7280;">
                                    Payment will be released after the standard 20-day hold period.
                                </p>
                            </div>

                            <p style="font-size: 16px; color: #374151; line-height: 1.6;">
                                Please log in to your TutorSolve dashboard to review the requirements and begin working on the task.
                            </p>

                            <p style="text-align: center; margin: 30px 0;">
                                <a href="https://www.tutorsolve.com"
                                   style="
                                   background-color: #2563eb;
                                   color: white;
                                   text-decoration: none;
                                   padding: 12px 24px;
                                   border-radius: 6px;
                                   font-weight: bold;
                                   display: inline-block;
                                   ">
                                    Open Dashboard
                                </a>
                            </p>

                            <hr style="border: none; border-top: 1px solid #e5e7eb;">

                            <p style="font-size: 14px; color: #6b7280;">
                                Thank you,<br>
                                <strong>The TutorSolve Team</strong>
                            </p>

                        </td>
                    </tr>

                </table>

            </td>
        </tr>
    </table>

</body>
</html>
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


def send_payout_released_email(expert_email, expert_name, amount, currency=None):
    """Sent to expert when their payout clears the 20-day hold."""
    dispatch_email_task(
        to_email=expert_email,
        to_name=expert_name,
        subject="Your payout has been released — TutorSolve",
        html_content=f"""
            <p>Hi {expert_name},</p>
            <p>Your payout of <strong>{money_label(amount, currency)} {((currency or 'inr').upper())}</strong> has cleared the 20-day hold and is being processed.</p>
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


def send_password_changed_email(user_email, user_name, role):
    """Sent after a successful password change for any authenticated role."""
    role_label = (role or "user").replace("_", " ").title()
    dispatch_email_task(
        to_email=user_email,
        to_name=user_name or "User",
        subject="Your password was changed — TutorSolve",
        html_content=f"""
            <p>Hi {user_name or "there"},</p>
            <p>Your TutorSolve account password was just changed.</p>
            <p><strong>Role:</strong> {role_label}</p>
            <p>If this wasn't you, please contact support immediately.</p>
            <p>— The TutorSolve Team</p>
        """
    )


def send_password_reset_email(user_email, user_name, reset_link, minutes_valid=15):
    """Sent when a user requests a password reset link."""
    dispatch_email_task(
        to_email=user_email,
        to_name=user_name or "User",
        subject="Reset your password — TutorSolve",
        html_content=f"""
            <p>Hi {user_name or "there"},</p>
            <p>We received a request to reset your TutorSolve password.</p>
            <p>This link is valid for <strong>{int(minutes_valid)}</strong> minutes:</p>
            <p><a href="{reset_link}">Reset My Password</a></p>
            <p>If you didn't request this, you can safely ignore this email.</p>
            <p>— The TutorSolve Team</p>
        """
    )
