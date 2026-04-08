
import streamlit as st
import pandas as pd
from datetime import datetime
from db.supabase_client import supabase
from workflow.sidebar_menu import render_sidebar
from institution_access import normalize_role, get_display_name, enforce_institution_access, institution_table_available, get_institution_record

st.set_page_config(page_title="Admin - Institutions & Roles", layout="wide")

if "user" not in st.session_state:
    st.switch_page("app.py")

user = st.session_state.user
resp = supabase.table("user_profiles").select("*").eq("id", user.id).execute()
profile = resp.data[0] if resp.data else {}

role = normalize_role(profile.get("role"))
institution = profile.get("institution") or ""
email = profile.get("email") or getattr(user, "email", "") or ""
display_name = get_display_name(profile, user)

render_sidebar(role)
enforce_institution_access(profile, "admin page")

if role not in ["super_admin", "institution_admin"]:
    st.error("Access denied")
    st.stop()

st.title("🏢 Admin: Institutions, Trial Control & Role Assignment")
st.caption(f"Institution: {institution or 'All Institutions'} | User: {display_name} | Email: {email} | Role: {role}")
st.markdown("---")

inst_table_ok = institution_table_available()


def load_users():
    query = supabase.table("user_profiles").select("*").order("institution").order("email")
    if role == "institution_admin":
        query = query.eq("institution", institution)
    return query.execute().data or []


def load_application_rows():
    query = supabase.table("loan_applications").select("institution")
    if role == "institution_admin":
        query = query.eq("institution", institution)
    try:
        return query.execute().data or []
    except Exception:
        return []


def load_institutions_from_table():
    if not inst_table_ok:
        return []
    try:
        q = supabase.table("institutions").select("*").order("institution_name")
        if role == "institution_admin":
            q = q.eq("institution_name", institution)
        return q.execute().data or []
    except Exception:
        return []


def derived_institution_names(users, application_rows):
    names = set()
    for row in users or []:
        nm = str(row.get("institution") or "").strip()
        if nm:
            names.add(nm)
    for row in application_rows or []:
        nm = str(row.get("institution") or "").strip()
        if nm:
            names.add(nm)
    if role == "institution_admin" and institution:
        names.add(institution)
    return sorted(names)


def sync_missing_institutions(names, existing_records):
    existing_names = {str(r.get("institution_name") or "").strip() for r in existing_records}
    missing = [n for n in names if n not in existing_names]
    created = 0
    for name in missing:
        payload = {
            "institution_name": name,
            "plan_status": "trial",
            "trial_start_date": str(datetime.now().date()),
            "trial_end_date": str(datetime.now().date()),
            "is_locked": False,
            "lock_reason": "",
            "created_by": email,
            "updated_at": str(datetime.now()),
        }
        try:
            supabase.table("institutions").insert(payload).execute()
            created += 1
        except Exception:
            pass
    return created


users = load_users()
application_rows = load_application_rows()
institution_records = load_institutions_from_table()
known_names = derived_institution_names(users, application_rows)
record_map = {str(r.get("institution_name") or "").strip(): r for r in institution_records}
all_names = sorted(set(known_names) | set(record_map.keys()))

if role == "super_admin":
    tab1, tab2, tab3 = st.tabs(["Institution Registry", "Pending Users", "Users by Institution"])
else:
    tab1, tab2, tab3 = st.tabs(["My Institution", "Pending Users", "Users by Institution"])

with tab1:
    if role == "super_admin":
        st.subheader("🏦 Create Institution")
        if not inst_table_ok:
            st.warning("The institutions table is not available yet. Run the SQL migration first.")
        else:
            c1, c2 = st.columns(2)
            institution_name = c1.text_input("Institution Name", key="new_inst_name")
            institution_code = c2.text_input("Institution Code", key="new_inst_code")
            c3, c4 = st.columns(2)
            trial_start = c3.date_input("Trial Start Date", key="trial_start")
            trial_end = c4.date_input("Trial End Date", key="trial_end")
            c5, c6 = st.columns(2)
            logo_path = c5.text_input("Logo Path (optional)", key="logo_path")
            plan_status = c6.selectbox("Plan Status", ["trial", "active", "suspended"], key="plan_status")
            if st.button("Create Institution", key="create_institution"):
                if not institution_name.strip():
                    st.error("Institution name is required.")
                else:
                    payload = {
                        "institution_name": institution_name.strip(),
                        "institution_code": institution_code.strip() or None,
                        "trial_start_date": str(trial_start),
                        "trial_end_date": str(trial_end),
                        "plan_status": plan_status,
                        "is_locked": False,
                        "lock_reason": "",
                        "logo_path": logo_path.strip() or None,
                        "created_by": email,
                        "updated_at": str(datetime.now()),
                    }
                    try:
                        supabase.table("institutions").insert(payload).execute()
                        st.success(f"Created institution: {institution_name.strip()}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Create failed: {e}")

        st.markdown("---")
        st.subheader("🔐 Lock / Unlock Institutions")

        if inst_table_ok and all_names:
            missing = [n for n in all_names if n not in record_map]
            if missing:
                st.info("Some institutions exist in user/application data but not yet in the institutions registry.")
                if st.button("Sync Missing Institutions to Registry", key="sync_missing_institutions"):
                    created = sync_missing_institutions(missing, institution_records)
                    st.success(f"Synced {created} institution(s).")
                    st.rerun()

        if not all_names:
            st.info("No institutions found yet.")
        else:
            for name in all_names:
                inst = record_map.get(name, {
                    "institution_name": name,
                    "institution_code": None,
                    "plan_status": "trial",
                    "trial_start_date": None,
                    "trial_end_date": None,
                    "is_locked": False,
                    "lock_reason": "",
                    "logo_path": None,
                    "id": None,
                })
                tag = "Registry record" if inst.get("id") else "Derived from users/applications"
                with st.expander(f"{name} | Status: {'Locked' if inst.get('is_locked') else 'Open'} | {tag}"):
                    st.write(f"**Institution Code:** {inst.get('institution_code') or 'N/A'}")
                    st.write(f"**Plan Status:** {inst.get('plan_status') or 'N/A'}")
                    st.write(f"**Trial Start:** {inst.get('trial_start_date') or 'N/A'}")
                    st.write(f"**Trial End:** {inst.get('trial_end_date') or 'N/A'}")
                    st.write(f"**Logo Path:** {inst.get('logo_path') or 'N/A'}")
                    if not inst.get("id"):
                        if st.button("Create Registry Record", key=f"create_registry_{name}"):
                            created = sync_missing_institutions([name], institution_records)
                            if created:
                                st.success("Registry record created.")
                                st.rerun()
                            else:
                                st.error("Could not create registry record.")
                    else:
                        lock_reason = st.text_area("Lock Reason", value=inst.get('lock_reason') or '', key=f"lock_reason_{inst.get('id')}")
                        new_trial_end = st.text_input("Extend / Update Trial End Date (YYYY-MM-DD)", value=inst.get('trial_end_date') or '', key=f"trial_edit_{inst.get('id')}")
                        c1, c2, c3 = st.columns(3)
                        if c1.button("Lock Institution", key=f"lock_{inst.get('id')}"):
                            try:
                                supabase.table("institutions").update({
                                    "is_locked": True,
                                    "lock_reason": lock_reason or "Subscription inactive",
                                    "plan_status": "suspended",
                                    "updated_at": str(datetime.now()),
                                }).eq("id", inst.get('id')).execute()
                                st.success("Institution locked")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Lock failed: {e}")
                        if c2.button("Unlock Institution", key=f"unlock_{inst.get('id')}"):
                            try:
                                payload = {
                                    "is_locked": False,
                                    "lock_reason": "",
                                    "plan_status": "active",
                                    "updated_at": str(datetime.now()),
                                }
                                if str(new_trial_end).strip():
                                    payload["trial_end_date"] = str(new_trial_end).strip()
                                supabase.table("institutions").update(payload).eq("id", inst.get('id')).execute()
                                st.success("Institution unlocked")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Unlock failed: {e}")
                        if c3.button("Update Metadata", key=f"update_inst_{inst.get('id')}"):
                            try:
                                payload = {"lock_reason": lock_reason, "updated_at": str(datetime.now())}
                                if str(new_trial_end).strip():
                                    payload["trial_end_date"] = str(new_trial_end).strip()
                                supabase.table("institutions").update(payload).eq("id", inst.get('id')).execute()
                                st.success("Institution updated")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Update failed: {e}")
    else:
        st.subheader("🏦 My Institution")
        record = get_institution_record(institution) or {}
        if record:
            st.write(f"**Institution:** {record.get('institution_name')}")
            st.write(f"**Plan Status:** {record.get('plan_status') or 'N/A'}")
            st.write(f"**Trial End:** {record.get('trial_end_date') or 'N/A'}")
            st.write(f"**Locked:** {'Yes' if record.get('is_locked') else 'No'}")
            st.write(f"**Logo Path:** {record.get('logo_path') or 'N/A'}")
        else:
            st.info("Institution record not found yet. Super Admin should create or sync it first.")

with tab2:
    st.subheader("🟡 Pending Users")
    pending_users = [u for u in users if normalize_role(u.get('role') or 'pending') in ['', 'pending']]
    if not pending_users:
        st.success("No pending users")
    else:
        role_options = ["initiator", "analyst", "manager", "final_approver"]
        if role == "super_admin":
            role_options += ["institution_admin", "super_admin"]
        else:
            role_options += ["institution_admin"]

        for u in pending_users:
            st.markdown("---")
            st.write(f"📧 **{u.get('email')}**")
            c1, c2 = st.columns(2)
            with c1:
                new_role = st.selectbox("Assign Role", role_options, key=f"pending_role_{u['id']}")
            with c2:
                if role == 'super_admin':
                    if all_names:
                        current_inst = str(u.get('institution') or '').strip()
                        try:
                            idx = all_names.index(current_inst) if current_inst in all_names else 0
                        except Exception:
                            idx = 0
                        new_institution = st.selectbox("Institution", all_names, index=idx, key=f"pending_inst_{u['id']}")
                    else:
                        new_institution = st.text_input("Institution", value=u.get('institution') or '', key=f"pending_inst_{u['id']}")
                else:
                    new_institution = institution
                    st.text_input("Institution", value=new_institution, disabled=True, key=f"pending_inst_{u['id']}")

            if st.button("Approve & Assign Role", key=f"approve_{u['id']}"):
                try:
                    supabase.table("user_profiles").update({
                        "role": new_role,
                        "institution": new_institution,
                    }).eq("id", u["id"]).execute()
                    st.success(f"{u.get('email')} assigned as {new_role}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")

with tab3:
    st.subheader("👥 Users by Institution")
    if not users:
        st.warning("No users found")
    else:
        grouped = {}
        for u in users:
            nm = str(u.get("institution") or "Unassigned").strip() or "Unassigned"
            grouped.setdefault(nm, []).append(u)

        for inst_name in sorted(grouped.keys()):
            with st.expander(f"{inst_name} ({len(grouped[inst_name])} users)", expanded=(role == "institution_admin")):
                frame = pd.DataFrame([
                    {
                        "email": u.get("email"),
                        "display_name": get_display_name(u),
                        "role": normalize_role(u.get("role") or "pending"),
                        "institution": u.get("institution") or "",
                    }
                    for u in grouped[inst_name]
                ])
                st.dataframe(frame, use_container_width=True)

                apps = load_applications_for(inst_name)
                st.write(f"**Applications in {inst_name}:** {len(apps)}")
                if apps:
                    app_frame = pd.DataFrame([
                        {
                            "client_name": a.get("client_name"),
                            "loan_amount": a.get("loan_amount"),
                            "workflow_status": a.get("workflow_status"),
                            "score": a.get("score"),
                        }
                        for a in apps
                    ])
                    st.dataframe(app_frame, use_container_width=True)
