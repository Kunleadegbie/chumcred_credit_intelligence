import streamlit as st

def render_sidebar(role: str) -> None:
    st.markdown("""
    <style>
    [data-testid="stSidebarNav"] {display: none;}
    </style>
    """, unsafe_allow_html=True)

    st.sidebar.title("Navigation")

    if role == "loan_officer":
        st.sidebar.page_link("pages/1_Initiator.py", label="Initiator")

    elif role in ["credit_analyst", "analyst"]:
        st.sidebar.page_link("pages/2_Analyst.py", label="Analyst")

    elif role == "manager":
        st.sidebar.page_link("pages/3_Manager.py", label="Manager")

    elif role == "final_approver":
        st.sidebar.page_link("pages/1_Initiator.py", label="Initiator")
        st.sidebar.page_link("pages/2_Analyst.py", label="Analyst")
        st.sidebar.page_link("pages/3_Manager.py", label="Manager")
        st.sidebar.page_link("pages/4_Final_Approver.py", label="Final Approver")
        st.sidebar.page_link("pages/5_Analytics.py", label="Analytics")

    elif role in ["institution_admin", "super_admin"]:
        st.sidebar.page_link("pages/1_Initiator.py", label="Initiator")
        st.sidebar.page_link("pages/2_Analyst.py", label="Analyst")
        st.sidebar.page_link("pages/3_Manager.py", label="Manager")
        st.sidebar.page_link("pages/4_Final_Approver.py", label="Final Approver")
        st.sidebar.page_link("pages/5_Analytics.py", label="Analytics")
        st.sidebar.page_link("pages/6_Admin_Roles.py", label="Admin Panel")

    # ===============================
    # LOGOUT (NOW FIXED)
    # ===============================
    st.sidebar.markdown("---")

    if st.sidebar.button("🚪 Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]

        st.session_state.go_to_login = False
        st.rerun()