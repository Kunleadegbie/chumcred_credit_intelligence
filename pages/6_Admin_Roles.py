import streamlit as st
from db.supabase_client import supabase
from workflow.sidebar_menu import render_sidebar

# ===============================
# PAGE CONFIG
# ===============================
st.set_page_config(page_title="Admin - Role Assignment", layout="wide")

# ===============================
# AUTH CHECK
# ===============================
if "user" not in st.session_state:
    st.switch_page("app.py")

user = st.session_state.user

# ===============================
# FETCH PROFILE
# ===============================
resp = supabase.table("user_profiles") \
    .select("*") \
    .eq("id", user.id) \
    .execute()

profile = resp.data[0] if resp.data else {}

role = (profile.get("role") or "").strip().lower().replace(" ", "_")
institution = profile.get("institution") or ""
email = profile.get("email") or ""

# ===============================
# SIDEBAR
# ===============================
render_sidebar(role)

# ===============================
# ACCESS CONTROL
# ===============================
if role not in ["super_admin", "institution_admin"]:
    st.error("Access denied")
    st.stop()

# ===============================
# PAGE HEADER
# ===============================
st.title("👤 Admin: Role Assignment")
st.caption(f"Institution: {institution or 'All Institutions'} | User: {email} | Role: {role}")
st.markdown("---")

# ===============================
# LOAD USERS BY ACCESS SCOPE
# ===============================
try:
    if role == "super_admin":
        resp = supabase.table("user_profiles").select("*").order("email").execute()
    else:
        resp = supabase.table("user_profiles").select("*").eq("institution", institution).order("email").execute()
    users = resp.data or []
except Exception as e:
    st.error(f"Failed to load users: {e}")
    st.stop()

pending_users = [u for u in users if (u.get("role") or "pending") in [None, "", "pending"]]
all_roles = ["initiator", "analyst", "manager", "final_approver", "institution_admin"]
if role == "super_admin":
    all_roles.append("super_admin")

# ===============================
# PENDING USERS
# ===============================
st.subheader("🟡 Pending Users")

if not pending_users:
    st.success("No pending users")
else:
    for u in pending_users:
        st.markdown("---")
        st.write(f"📧 **{u.get('email')}**")

        col1, col2 = st.columns(2)
        with col1:
            new_role = st.selectbox(
                "Assign Role",
                all_roles,
                key=f"pending_role_{u['id']}"
            )

        with col2:
            if role == "super_admin":
                new_institution = st.text_input(
                    "Institution",
                    value=u.get("institution") or "",
                    key=f"pending_inst_{u['id']}"
                )
            else:
                new_institution = institution
                st.text_input(
                    "Institution",
                    value=new_institution,
                    key=f"pending_inst_readonly_{u['id']}",
                    disabled=True
                )

        if st.button("✅ Approve User", key=f"approve_{u['id']}"):
            payload = {
                "role": new_role,
                "institution": new_institution
            }
            supabase.table("user_profiles") \
                .update(payload) \
                .eq("id", u["id"]) \
                .execute()

            st.success(f"{u.get('email')} has been updated successfully")
            st.rerun()

# ===============================
# ALL USERS VIEW
# ===============================
st.markdown("---")
st.subheader("👥 All Registered Users")

if not users:
    st.warning("No users found")
else:
    for u in users:
        with st.container():
            st.markdown("---")
            st.write(
                f"📧 **{u.get('email')}** | "
                f"🏢 **{u.get('institution') or 'N/A'}** | "
                f"🎭 **{u.get('role') or 'pending'}**"
            )

            if role == "super_admin" or (u.get("institution") or "") == institution:
                col1, col2 = st.columns(2)
                current_role = (u.get("role") or "pending").strip().lower().replace(" ", "_")
                default_role = current_role if current_role in all_roles else "initiator"
                default_index = all_roles.index(default_role) if default_role in all_roles else 0

                with col1:
                    edit_role = st.selectbox(
                        "Edit Role",
                        all_roles,
                        index=default_index,
                        key=f"edit_role_{u['id']}"
                    )

                with col2:
                    if role == "super_admin":
                        edit_institution = st.text_input(
                            "Edit Institution",
                            value=u.get("institution") or "",
                            key=f"edit_inst_{u['id']}"
                        )
                    else:
                        edit_institution = institution
                        st.text_input(
                            "Edit Institution",
                            value=edit_institution,
                            key=f"edit_inst_readonly_{u['id']}",
                            disabled=True
                        )

                if st.button("💾 Update User", key=f"update_user_{u['id']}"):
                    payload = {
                        "role": edit_role,
                        "institution": edit_institution
                    }
                    supabase.table("user_profiles") \
                        .update(payload) \
                        .eq("id", u["id"]) \
                        .execute()
                    st.success(f"Updated {u.get('email')}")
                    st.rerun()
