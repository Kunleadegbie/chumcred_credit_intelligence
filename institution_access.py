
import streamlit as st
from datetime import date, datetime
from db.supabase_client import supabase


def normalize_role(role: str) -> str:
    return (role or "").strip().lower().replace(" ", "_")


def get_display_name(profile: dict, user=None) -> str:
    for key in ["full_name", "name", "display_name"]:
        value = str((profile or {}).get(key) or "").strip()
        if value:
            return value
    email = str((profile or {}).get("email") or getattr(user, "email", "") or "").strip()
    if email:
        return email
    return "Unknown User"


def build_actor_entry(profile: dict, user, stage: str, action: str, note: str = "") -> dict:
    email = str((profile or {}).get("email") or getattr(user, "email", "") or "").strip()
    return {
        "stage": normalize_role(stage).upper(),
        "action": action,
        "user": getattr(user, "id", None),
        "actor_email": email,
        "actor_name": get_display_name(profile, user),
        "timestamp": str(datetime.now()),
        "note": note or "",
    }


def actor_label(history_item: dict) -> str:
    name = str((history_item or {}).get("actor_name") or "").strip()
    email = str((history_item or {}).get("actor_email") or "").strip()
    if name and email and name != email:
        return f"{name} ({email})"
    if email:
        return email
    if name:
        return name
    return str((history_item or {}).get("user") or "Unknown User")


def render_history(history_items):
    history_items = history_items or []
    if not history_items:
        st.info("No approvals yet")
        return
    for item in history_items:
        st.markdown(
            f"**{item.get('stage','UNKNOWN')}** → {item.get('action','')}  \n"
            f"By: {actor_label(item)}  \n"
            f"Note: {item.get('note','')}  \n"
            f"Time: {item.get('timestamp','')}"
        )


def get_stage_actor(history_items, stage_name: str) -> str:
    stage_name = normalize_role(stage_name).upper()
    for item in reversed(history_items or []):
        if str(item.get("stage", "")).upper() == stage_name:
            return actor_label(item)
    return "N/A"


def get_institution_record(institution_name: str):
    institution_name = str(institution_name or "").strip()
    if not institution_name:
        return None
    try:
        resp = supabase.table("institutions").select("*").eq("institution_name", institution_name).limit(1).execute()
        data = resp.data or []
        return data[0] if data else None
    except Exception:
        return None


def institution_block_message(record: dict) -> str:
    institution_name = str((record or {}).get("institution_name") or "your institution")
    reason = str((record or {}).get("lock_reason") or "Subscription inactive or trial expired.")
    trial_end = str((record or {}).get("trial_end_date") or "").strip()
    msg = f"{institution_name} is currently locked. {reason}"
    if trial_end:
        msg += f" Trial end date: {trial_end}."
    return msg


def enforce_institution_access(profile: dict, page_name: str = "this page"):
    role = normalize_role((profile or {}).get("role"))
    if role == "super_admin":
        return
    institution = str((profile or {}).get("institution") or "").strip()
    record = get_institution_record(institution)
    if record and bool(record.get("is_locked")):
        st.error(institution_block_message(record))
        st.stop()


def institution_table_available() -> bool:
    try:
        supabase.table("institutions").select("institution_name").limit(1).execute()
        return True
    except Exception:
        return False
