import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app
import os


class Mailer:

    @staticmethod
    def send_email(to_email: str, subject: str, body: str):
        try:
            smtp_server = os.getenv("MAIL_SMTP")
            smtp_port = int(os.getenv("MAIL_PORT", 587))
            username = os.getenv("MAIL_USERNAME")
            password = os.getenv("MAIL_PASSWORD")
            mail_from = os.getenv("MAIL_FROM")

            msg = MIMEMultipart()
            msg["From"] = mail_from
            msg["To"] = to_email
            msg["Subject"] = subject

            msg.attach(MIMEText(body, "html"))

            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(username, password)
            server.sendmail(mail_from, to_email, msg.as_string())
            server.quit()

            return True

        except Exception as e:
            if current_app.config.get("DEBUG"):
                print("Email send failed:", str(e))
            return False
