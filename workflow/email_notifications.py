import os
import smtplib
from email.mime.text import MIMEText

from db.supabase_client import supabase

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "True").lower() == "true"
FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL")
FROM_NAME = os.getenv("SMTP_FROM_NAME", "Chumcred CLIE")


def send_email(to_email, subject, body):
    if not to_email:
        return False

    if not all([SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, FROM_EMAIL]):
        print("Email config missing. Check SMTP environment variables.")
        return False

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
        return True

    except Exception as e:
        print("Email error:", e)
        return False


def send_initiator_outcome(payload, decision):
    try:
        to_email = payload.get("initiated_by_email")
        client_name = payload.get("client_name", "Client")

        if not to_email:
            return False

        subject = f"Loan Application Update - {client_name}"
        body = f"""
Dear Applicant,

Your loan application for {client_name} has been {decision}.

Please log in to CLIE for full details.

Regards,
Chumcred CLIE
"""
        return send_email(to_email, subject, body)

    except Exception as e:
        print("Outcome email error:", e)
        return False


def send_next_stage_notification(institution, stage, payload, actor_name):
    try:
        stage_value = str(stage or "").strip().lower()

        if stage_value == "initiator":
            next_role = "analyst"
        elif stage_value == "analyst":
            next_role = "manager"
        elif stage_value == "manager":
            next_role = "final_approver"
        else:
            return False

        resp = (
            supabase.table("user_profiles")
            .select("email, role, institution")
            .eq("institution", institution)
            .execute()
        )

        rows = resp.data or []
        next_email = None

        for row in rows:
            role_value = str(row.get("role") or "").strip().lower().replace(" ", "_")
            if role_value == next_role:
                next_email = row.get("email")
                break

        if not next_email:
            print(f"No next approver found for institution={institution}, role={next_role}")
            return False

        client_name = payload.get("client_name", "Client")

        subject = f"Loan Application Awaiting Your Review - {client_name}"
        body = f"""
Dear User,

A loan application for {client_name} has been processed by {actor_name}
and is now awaiting your review at the {next_role.upper()} stage.

Please log in to CLIE to take action.

Regards,
Chumcred CLIE
"""

        return send_email(next_email, subject, body)

    except Exception as e:
        print("Notification error:", e)
        return False
