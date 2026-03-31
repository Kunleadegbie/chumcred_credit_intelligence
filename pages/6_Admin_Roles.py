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

role = (profile.get("role") or "").strip().lower()

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
st.caption("Assign roles and institutions to users")

st.markdown("---")

# ===============================
# LOAD ALL USERS
# ===============================
resp = supabase.table("user_profiles").select("*").execute()
users = resp.data or []

# ===============================
# FILTER PENDING USERS
# ===============================
st.subheader("🟡 Pending Users")

pending_users = [u for u in users if u.get("role") in [None, "pending"]]

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
                ["loan_officer", "analyst", "manager", "final_approver"],
                key=f"role_{u['id']}"
            )

        with col2:
            new_institution = st.text_input(
                "Institution",
                value=u.get("institution") or "",
                key=f"inst_{u['id']}"
            )

        if st.button("Approve & Assign Role", key=f"approve_{u['id']}"):

            supabase.table("user_profiles") \
                .update({
                    "role": new_role,
                    "institution": new_institution
                }) \
                .eq("id", u["id"]) \
                .execute()

            st.success(f"{u['email']} assigned as {new_role}")
            st.rerun()

# ===============================
# ROLE ASSIGNMENT SECTION
# ===============================
for u in pending_users:

    with st.container():
        st.markdown("---")

        st.markdown(f"**📧 Email:** {u.get('email')}")

        col1, col2 = st.columns(2)

        with col1:
            new_role = st.selectbox(
                "Assign Role",
                ["loan_officer", "analyst", "manager", "final_approver"],
                key=f"role_{u['id']}"
            )

        with col2:
            new_institution = st.text_input(
                "Institution",
                value=u.get("institution") or "",
                key=f"inst_{u['id']}"
            )

        if st.button("✅ Approve User", key=f"approve_{u['id']}"):

            supabase.table("user_profiles") \
                .update({
                    "role": new_role,
                    "institution": new_institution
                }) \
                .eq("id", u["id"]) \
                .execute()

            st.success(f"{u.get('email')} has been updated successfully")
            st.rerun()

# ===============================
# ALL USERS VIEW (CONTROL PANEL)
# ===============================
st.markdown("---")
st.subheader("👥 All Registered Users")

if not users:
    st.warning("No users found")
else:
    for u in users:
        st.write(
            f"📧 {u.get('email')} | "
            f"🏢 {u.get('institution') or 'N/A'} | "
            f"🎭 {u.get('role')}"
        )