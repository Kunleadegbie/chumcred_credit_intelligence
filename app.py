import streamlit as st
import pandas as pd

from db.supabase_client import supabase
from auth.login import login_page
from auth.signup import signup_page

from workflow.sidebar_menu import render_sidebar

# ===============================
# PAGE CONFIG (FIRST ALWAYS)
# ===============================
st.set_page_config(page_title="Chumcred AI", layout="wide")

st.markdown("""
<style>
[data-testid="stSidebarNav"] {display: none;}
</style>
""", unsafe_allow_html=True)

st.image("assets/logo.png", width=120)

# ===============================
# INIT STATE
# ===============================
if "go_to_login" not in st.session_state:
    st.session_state.go_to_login = False

# ===============================
# LANDING / LOGIN FLOW (FINAL CLEAN)
# ===============================
if "user" not in st.session_state:

    if not st.session_state.get("go_to_login", False):
        st.switch_page("Landing.py")

    # LOGIN PAGE
    st.markdown("""
    <style>
    [data-testid="stSidebar"] {display: none;}
    </style>
    """, unsafe_allow_html=True)

    st.title("🔐 Login to Chumcred AI")

    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        login_page()

    with tab2:
        signup_page()

    st.stop()
    # ===============================
    # LOGIN PAGE
    # ===============================
    st.title("🔐 Login to Chumcred AI")

    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        login_page()

    with tab2:
        signup_page()

    st.stop()

# ===============================
# GET USER
# ===============================
user = st.session_state.user

# ===============================
# FETCH PROFILE
# ===============================
resp = supabase.table("user_profiles") \
    .select("*") \
    .eq("id", user.id) \
    .execute()

profile = resp.data[0] if resp.data else {}

# ===============================
# EXTRACT ROLE
# ===============================
role = (profile.get("role") or "").strip().lower()
institution = profile.get("institution", "")
email = profile.get("email", "")

# ===============================
# SIDEBAR (ONLY ONE SYSTEM)
# ===============================
render_sidebar(role)

# ===============================
# LOGOUT (STABLE POSITION)
# ===============================
st.sidebar.markdown("---")

if st.sidebar.button("🚪 Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.session_state.go_to_login = False
    st.rerun()

# ===============================
# BLOCK PENDING USERS
# ===============================
if role == "pending":
    st.warning("Your account is awaiting role assignment.")
    st.stop()

# ===============================
# GLOBAL STYLE
# ===============================
st.markdown("""
<style>
.main {background-color: #f8f9fa;}
h1, h2, h3 {color: #1f3c88;}
.stButton>button {
    background-color: #1f3c88;
    color: white;
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

# ===============================
# DASHBOARD TITLE
# ===============================
def get_dashboard_title(role: str) -> str:

    if role == "loan_officer":
        return "📝 Loan Initiation Dashboard"

    elif role in ["analyst", "credit_analyst"]:
        return "🔎 Credit Analyst Dashboard"

    elif role == "manager":
        return "📊 Credit Manager Dashboard"

    elif role == "final_approver":
        return "✅ Final Approval Desk"

    elif role in ["institution_admin", "super_admin"]:
        return "⚙️ Admin Control Panel"

    else:
        return "📌 Credit Workflow Dashboard"

# ===============================
# MAIN DASHBOARD HEADER
# ===============================
st.title(get_dashboard_title(role))
st.caption(f"Institution: {institution} | User: {email} | Role: {role}")