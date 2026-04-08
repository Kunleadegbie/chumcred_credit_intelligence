
import streamlit as st
from institution_access import normalize_role

def render_sidebar(role: str) -> None:
    role = normalize_role(role)

    st.markdown("""
    <style>
    [data-testid="stSidebarNav"] {display: none;}
    </style>
    """, unsafe_allow_html=True)

    st.sidebar.title("Navigation")

    if role in ["loan_officer", "initiator"]:
        st.sidebar.page_link("pages/1_Initiator.py", label="Initiator")
    elif role in ["credit_analyst", "analyst"]:
        st.sidebar.page_link("pages/2_Analyst.py", label="Analyst")
    elif role == "manager":
        st.sidebar.page_link("pages/3_Manager.py", label="Manager")
        st.sidebar.page_link("pages/5_Analytics.py", label="Analytics")
    elif role == "final_approver":
        st.sidebar.page_link("pages/4_Final_Approver.py", label="Final Approver")
        st.sidebar.page_link("pages/5_Analytics.py", label="Analytics")
    elif role == "institution_admin":
        st.sidebar.page_link("pages/5_Analytics.py", label="Analytics")
        st.sidebar.page_link("pages/6_Admin_Roles.py", label="Institution Admin Panel")
    elif role == "super_admin":
        st.sidebar.page_link("pages/1_Initiator.py", label="Initiator")
        st.sidebar.page_link("pages/2_Analyst.py", label="Analyst")
        st.sidebar.page_link("pages/3_Manager.py", label="Manager")
        st.sidebar.page_link("pages/4_Final_Approver.py", label="Final Approver")
        st.sidebar.page_link("pages/5_Analytics.py", label="Analytics")
        st.sidebar.page_link("pages/6_Admin_Roles.py", label="Super Admin Panel")

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.go_to_login = False
        st.rerun()
