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
# LANDING / LOGIN FLOW (FINAL)
# ===============================
if "user" not in st.session_state:

    if not st.session_state.get("go_to_login", False):

        st.markdown("""
        <style>
        [data-testid="stSidebar"] {display: none;}
        </style>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="text-align:center; padding:60px 20px;">
            <h1 style="color:#1f3c88; font-size:40px;">
                Chumcred AI Credit Intelligence Platform
            </h1>
            <p style="font-size:18px; color:#555;">
                Smart Credit Decisions Powered by AI
            </p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("### 🤖 AI Credit Assessment")
            st.write("Automate borrower risk evaluation")

        with col2:
            st.markdown("### 📄 Smart Credit Memo")
            st.write("Generate structured bank-grade memos")

        with col3:
            st.markdown("### 🔄 Approval Workflow")
            st.write("Multi-level credit approval system")

        st.markdown("---")

        if st.button("🔐 Go to Login", use_container_width=True):
            st.session_state.go_to_login = True
            st.rerun()

        st.stop()

    # LOGIN PAGE
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