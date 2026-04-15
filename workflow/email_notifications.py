import os
import smtplib
from email.message import EmailMessage
from db.supabase_client import supabase

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME or "no-reply@clie.chumcred.com")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "CLIE Notifications")


def _send_email(to_email: str, subject: str, body: str):
    if not to_email or not SMTP_HOST or not SMTP_USERNAME or not SMTP_PASSWORD:
        return False, "SMTP not configured"

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg["To"] = to_email
        msg.set_content(body)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)


def get_users_by_roles(institution: str, roles):
    role_values = [(r or "").strip().lower() for r in roles]
    try:
        rows = (
            supabase.table("user_profiles")
            .select("*")
            .eq("institution", institution)
            .execute()
            .data
            or []
        )
    except Exception:
        return []
    return [r for r in rows if str(r.get("role") or "").strip().lower() in role_values and r.get("email")]


def get_next_approver_emails(institution: str, stage: str):
    stage_map = {
        "initiator": ["analyst", "credit_analyst"],
        "analyst": ["manager"],
        "manager": ["final_approver"],
    }
    roles = stage_map.get((stage or "").strip().lower(), [])
    return [r.get("email") for r in get_users_by_roles(institution, roles)]


def send_next_stage_notification(institution: str, stage_from: str, app_record: dict, actor_name: str):
    recipients = get_next_approver_emails(institution, stage_from)
    if not recipients:
        return []

    subject = f"Loan application awaiting your review: {app_record.get('client_name', 'Borrower')}"
    body = (
        f"A loan application is awaiting your review.\n\n"
        f"Client: {app_record.get('client_name', 'N/A')}\n"
        f"Amount: ₦{float(app_record.get('loan_amount', 0) or 0):,.0f}\n"
        f"Tenor: {app_record.get('tenor', 'N/A')} months\n"
        f"Institution: {institution}\n"
        f"Submitted/advanced by: {actor_name}\n\n"
        f"Please log in to CLIE to review the application."
    )
    results = []
    for email in recipients:
        ok, err = _send_email(email, subject, body)
        results.append((email, ok, err))
    return results


def send_initiator_outcome_notification(app_record: dict, outcome_label: str, actor_name: str):
    recipient = app_record.get("initiated_by_email")
    if not recipient:
        return False, "Initiator email not available"

    subject = f"Loan application update: {app_record.get('client_name', 'Borrower')} - {outcome_label}"
    body = (
        f"Your loan application has been updated.\n\n"
        f"Client: {app_record.get('client_name', 'N/A')}\n"
        f"Amount: ₦{float(app_record.get('loan_amount', 0) or 0):,.0f}\n"
        f"Tenor: {app_record.get('tenor', 'N/A')} months\n"
        f"Status: {outcome_label}\n"
        f"Updated by: {actor_name}\n\n"
        f"Please log in to CLIE for full details."
    )
    return _send_email(recipient, subject, body)
