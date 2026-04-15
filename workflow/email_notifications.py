import smtplib
from email.mime.text import MIMEText
import os

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "True") == "True"
FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL")
FROM_NAME = os.getenv("SMTP_FROM_NAME", "Chumcred CLIE")


def send_email(to_email, subject, body):
    try:
        msg = MIMEText(body, "plain")
        msg["Subject"] = subject
        msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg["To"] = to_email

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        if SMTP_USE_TLS:
            server.starttls()

        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(FROM_EMAIL, [to_email], msg.as_string())
        server.quit()

    except Exception as e:
        print("Email error:", e)


def send_next_stage_notification(to_email, stage, client_name):
    subject = f"Loan Application Awaiting Your Review - {client_name}"
    body = f"""
Dear User,

A loan application for {client_name} is awaiting your action at the {stage} stage.

Please log in to CLIE to review and take action.

Regards,
Chumcred CLIE
"""
    send_email(to_email, subject, body)


def send_initiator_outcome(to_email, client_name, decision):
    subject = f"Loan Application Update - {client_name}"
    body = f"""
Dear Applicant,

Your loan application for {client_name} has been {decision}.

Please log in to CLIE for full details.

Regards,
Chumcred CLIE
"""
    send_email(to_email, subject, body)