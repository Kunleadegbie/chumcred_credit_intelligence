
import streamlit as st
import pandas as pd
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
email = profile.get("email") or ""
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
if not inst_table_ok:
    st.warning("The institutions table is not available yet. Run the SQL migration file first to enable institution creation and lock/unlock.")
    st.code(open('institutions_phase5.sql').read() if __import__('os').path.exists('institutions_phase5.sql') else 'Run the provided SQL migration file.', language='sql')


def load_institutions():
    if not inst_table_ok:
        return []
    try:
        return supabase.table("institutions").select("*").order("institution_name").execute().data or []
    except Exception:
        return []


def load_users():
    query = supabase.table("user_profiles").select("*").order("institution").order("email")
    if role == "institution_admin":
        query = query.eq("institution", institution)
    return query.execute().data or []


def load_applications_for(inst_name=None):
    q = supabase.table("loan_applications").select("*")
    if inst_name:
        q = q.eq("institution", inst_name)
    elif role == "institution_admin":
        q = q.eq("institution", institution)
    return q.order("created_at", desc=True).execute().data or []

users = load_users()
institutions = load_institutions()
known_institutions = sorted({str(u.get('institution') or '').strip() for u in users if str(u.get('institution') or '').strip()})
if institutions:
    for r in institutions:
        nm = str(r.get('institution_name') or '').strip()
        if nm and nm not in known_institutions:
            known_institutions.append(nm)
known_institutions = sorted(set(known_institutions))

if role == 'super_admin':
    tab1, tab2, tab3 = st.tabs(["Institution Registry", "Pending Users", "Users by Institution"])
else:
    tab1, tab2, tab3 = st.tabs(["My Institution", "Pending Users", "Users by Institution"])

with tab1:
    if role == 'super_admin':
        st.subheader("🏦 Create Institution")
        if not inst_table_ok:
            st.info("Create the institutions table first using the SQL migration file.")
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
                    }
                    try:
                        supabase.table("institutions").insert(payload).execute()
                        st.success(f"Created institution: {institution_name.strip()}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Create failed: {e}")

        st.markdown("---")
        st.subheader("🔐 Lock / Unlock Institutions")
        if not institutions:
            st.info("No institutions found yet.")
        else:
            for inst in institutions:
                with st.expander(f"{inst.get('institution_name')} | Status: {'Locked' if inst.get('is_locked') else 'Open'}"):
                    st.write(f"**Institution Code:** {inst.get('institution_code') or 'N/A'}")
                    st.write(f"**Plan Status:** {inst.get('plan_status') or 'N/A'}")
                    st.write(f"**Trial Start:** {inst.get('trial_start_date') or 'N/A'}")
                    st.write(f"**Trial End:** {inst.get('trial_end_date') or 'N/A'}")
                    st.write(f"**Logo Path:** {inst.get('logo_path') or 'N/A'}")
                    lock_reason = st.text_area("Lock Reason", value=inst.get('lock_reason') or '', key=f"lock_reason_{inst.get('id')}")
                    new_trial_end = st.text_input("Extend / Update Trial End Date (YYYY-MM-DD)", value=inst.get('trial_end_date') or '', key=f"trial_edit_{inst.get('id')}")
                    c1, c2, c3 = st.columns(3)
                    if c1.button("Lock Institution", key=f"lock_{inst.get('id')}"):
                        try:
                            supabase.table("institutions").update({"is_locked": True, "lock_reason": lock_reason or "Subscription inactive", "plan_status": "suspended", "updated_at": "now()"}).eq("id", inst.get('id')).execute()
                            st.success("Institution locked")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lock failed: {e}")
                    if c2.button("Unlock Institution", key=f"unlock_{inst.get('id')}"):
                        try:
                            payload = {"is_locked": False, "lock_reason": "", "plan_status": "active", "updated_at": "now()"}
                            if str(new_trial_end).strip():
                                payload["trial_end_date"] = str(new_trial_end).strip()
                            supabase.table("institutions").update(payload).eq("id", inst.get('id')).execute()
                            st.success("Institution unlocked")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Unlock failed: {e}")
                    if c3.button("Update Metadata", key=f"update_inst_{inst.get('id')}"):
                        try:
                            payload = {"lock_reason": lock_reason, "updated_at": "now()"}
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
            st.write(f"**Institution:** {record.get('institution_name')}" )
            st.write(f"**Plan Status:** {record.get('plan_status') or 'N/A'}")
            st.write(f"**Trial End:** {record.get('trial_end_date') or 'N/A'}")
            st.write(f"**Locked:** {'Yes' if record.get('is_locked') else 'No'}")
            st.write(f"**Logo Path:** {record.get('logo_path') or 'N/A'}")
        else:
            st.info("Institution record not found yet. Super Admin should create it first.")

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
                    if known_institutions:
                        default_inst = (u.get('institution') or known_institutions[0]) if known_institutions else ''
                        try:
                            idx = known_institutions.index(default_inst)
                        except Exception:
                            idx = 0
                        new_institution = st.selectbox("Institution", known_institutions, index=idx, key=f"pending_inst_{u['id']}")
                    else:
                        new_institution = st.text_input("Institution", value=u.get('institution') or '', key=f"pending_inst_{u['id']}")
                else:
                    new_institution = institution
                    st.text_input("Institution", value=new_institution, key=f"pending_inst_{u['id']}", disabled=True)
            if st.button("✅ Approve User", key=f"approve_{u['id']}"):
                try:
                    supabase.table("user_profiles").update({"role": new_role, "institution": new_institution}).eq("id", u['id']).execute()
                    st.success(f"{u.get('email')} assigned as {new_role}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")

with tab3:
    st.subheader("👥 Users Grouped by Institution")
    if not users:
        st.warning("No users found")
    else:
        user_df = pd.DataFrame(users)
        if 'institution' not in user_df.columns:
            user_df['institution'] = 'Unassigned'
        user_df['institution'] = user_df['institution'].fillna('Unassigned').replace('', 'Unassigned')
        for inst_name in sorted(user_df['institution'].unique().tolist()):
            group_df = user_df[user_df['institution'] == inst_name].copy()
            app_count = len(load_applications_for(None if role == 'super_admin' else institution) if role == 'institution_admin' and inst_name == institution else load_applications_for(inst_name if role == 'super_admin' else institution))
            with st.expander(f"{inst_name} | Users: {len(group_df)} | Applications: {app_count}"):
                for _, row in group_df.sort_values('email').iterrows():
                    user_role = normalize_role(row.get('role') or 'pending') or 'pending'
                    st.write(f"📧 **{row.get('email')}** | 🎭 **{user_role}**")
                    if role == 'super_admin' or inst_name == institution:
                        c1, c2 = st.columns(2)
                        role_options = ["initiator", "analyst", "manager", "final_approver", "institution_admin"]
                        if role == 'super_admin':
                            role_options += ["super_admin"]
                        default_role = user_role if user_role in role_options else 'initiator'
                        with c1:
                            edit_role = st.selectbox("Edit Role", role_options, index=role_options.index(default_role), key=f"edit_role_{row['id']}")
                        with c2:
                            if role == 'super_admin':
                                if known_institutions:
                                    current_inst = row.get('institution') or known_institutions[0]
                                    idx = known_institutions.index(current_inst) if current_inst in known_institutions else 0
                                    edit_inst = st.selectbox("Edit Institution", known_institutions, index=idx, key=f"edit_inst_{row['id']}")
                                else:
                                    edit_inst = st.text_input("Edit Institution", value=row.get('institution') or '', key=f"edit_inst_{row['id']}")
                            else:
                                edit_inst = institution
                                st.text_input("Edit Institution", value=edit_inst, key=f"edit_inst_{row['id']}", disabled=True)
                        if st.button("💾 Update User", key=f"update_user_{row['id']}"):
                            try:
                                supabase.table("user_profiles").update({"role": edit_role, "institution": edit_inst}).eq("id", row['id']).execute()
                                st.success(f"Updated {row.get('email')}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Update failed: {e}")
