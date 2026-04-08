import streamlit as st
import pandas as pd

from workflow.sidebar_menu import render_sidebar


from db.supabase_client import supabase
from workflow.application_service import (
    get_all_applications,
    get_institution_applications
)

# ===============================
# EXTRACT ROLE
# ===============================
role = (profile.get("role") or "").strip().lower()

# ===============================
# RENDER SIDEBAR (NOW SAFE)
# ===============================
render_sidebar(role)


# ===============================
# AUTH CHECK
# ===============================
if "user" not in st.session_state:
    st.warning("Please login first.")
    st.stop()

user = st.session_state.user

profile_resp = (
    supabase.table("user_profiles")
    .select("*")
    .eq("id", user.id)
    .execute()
)

profile = profile_resp.data[0] if profile_resp.data else {}

role = profile.get("role", "pending")
institution = profile.get("institution", "")
email = profile.get("email", "")

# ===============================
# ROLE ACCESS CONTROL
# ===============================
if role not in ["manager", "institution_admin", "super_admin"]:
    st.error("You do not have access to this page.")
    st.stop()

# ===============================
# HEADER
# ===============================
st.title("📊 Portfolio Analytics Dashboard")
st.caption(f"Institution: {institution} | User: {email}")

# ===============================
# LOAD DATA
# ===============================
try:
    if role == "super_admin":
        data = get_all_applications().data
    else:
        data = get_institution_applications(institution).data

    if not data:
        st.info("No portfolio data available yet.")
        st.stop()

    df = pd.DataFrame(data)

    # ===============================
    # EXECUTIVE SUMMARY
    # ===============================
    st.subheader("📌 Executive Summary")

    total_loans = len(df)
    total_exposure = df["loan_amount"].sum()
    avg_score = df["score"].mean()

    approval_rate = (df["workflow_status"] == "FINAL_APPROVED").mean()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Loans", total_loans)
    col2.metric("Total Exposure", f"₦{total_exposure:,.0f}")
    col3.metric("Average Score", f"{avg_score:.1f}")
    col4.metric("Approval Rate", f"{approval_rate:.0%}")

    st.markdown("---")

    # ===============================
    # WORKFLOW DISTRIBUTION
    # ===============================
    st.subheader("📈 Loan Status Distribution")

    st.bar_chart(df["workflow_status"].value_counts())

    st.markdown("---")

    # ===============================
    # RISK DISTRIBUTION
    # ===============================
    st.subheader("⚠️ Risk Distribution")

    def map_risk(score):
        if score >= 75:
            return "Low Risk"
        elif score >= 50:
            return "Moderate Risk"
        return "High Risk"

    df["risk_level"] = df["score"].apply(map_risk)

    st.bar_chart(df["risk_level"].value_counts())

    st.markdown("---")

    # ===============================
    # LOAN SIZE VS SCORE
    # ===============================
    st.subheader("📊 Loan Amount vs Risk Score")

    st.scatter_chart(df[["loan_amount", "score"]])

    st.markdown("---")

    # ===============================
    # DETAILED TABLE
    # ===============================
    st.subheader("📋 Portfolio Details")


    display_df = df.copy()
    if "id" in display_df.columns:
        display_df = display_df.drop(columns=["id"])
    if "initiated_by" in display_df.columns:
        if "initiated_by_email" in display_df.columns:
            display_df = display_df.drop(columns=["initiated_by"]).rename(columns={"initiated_by_email": "initiated_by"})
        else:
            display_df = display_df.drop(columns=["initiated_by"])
    st.dataframe(display_df)

except Exception as e:
    st.error(f"Dashboard error: {e}")