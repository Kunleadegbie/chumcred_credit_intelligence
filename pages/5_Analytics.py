import streamlit as st
import pandas as pd

from db.supabase_client import supabase
from workflow.application_service import get_all_applications, get_institution_applications
from workflow.sidebar_menu import render_sidebar

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
institution = profile.get("institution") or ""
email = profile.get("email") or ""

# ===============================
# SIDEBAR
# ===============================
render_sidebar(role)

# ===============================
# ACCESS CONTROL
# ===============================
if role not in ["manager", "institution_admin", "super_admin"]:
    st.error("Access denied")
    st.stop()
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
        st.info("No data available yet.")
        st.stop()

    df = pd.DataFrame(data)

except Exception as e:
    st.error(f"Data load failed: {e}")
    st.stop()

# ===============================
# EXECUTIVE SUMMARY
# ===============================
st.markdown("## 📌 Executive Summary")

total_loans = len(df)
total_exposure = df["loan_amount"].sum()
avg_score = df["score"].mean()

approval_rate = (df["workflow_status"] == "FINAL_APPROVED").mean()
rejection_rate = df["workflow_status"].str.contains("REJECTED").mean()

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Loans", total_loans)
col2.metric("Total Exposure", f"₦{total_exposure:,.0f}")
col3.metric("Approval Rate", f"{approval_rate:.0%}")
col4.metric("Rejection Rate", f"{rejection_rate:.0%}")

st.markdown("---")

# ===============================
# WORKFLOW DISTRIBUTION
# ===============================
st.markdown("## 📈 Loan Status Distribution")

status_counts = df["workflow_status"].value_counts()
st.bar_chart(status_counts)

st.markdown("---")

# ===============================
# RISK ANALYSIS
# ===============================
st.markdown("## ⚠️ Risk Distribution")

def map_risk(score):
    if score >= 75:
        return "Low Risk"
    elif score >= 50:
        return "Moderate Risk"
    return "High Risk"

df["risk_level"] = df["score"].apply(map_risk)

risk_counts = df["risk_level"].value_counts()
st.bar_chart(risk_counts)

st.markdown("---")

# ===============================
# LOAN SIZE VS RISK SCORE
# ===============================
st.markdown("## 📊 Loan Amount vs Risk Score")

st.scatter_chart(df[["loan_amount", "score"]])

st.markdown("---")

# ===============================
# APPROVAL PIPELINE
# ===============================
st.markdown("## 🔄 Approval Pipeline")

pipeline = df["workflow_status"].value_counts()

col1, col2, col3, col4 = st.columns(4)

col1.metric("Submitted", int(pipeline.get("SUBMITTED", 0)))
col2.metric("Analyst Approved", int(pipeline.get("ANALYST_APPROVED", 0)))
col3.metric("Manager Approved", int(pipeline.get("MANAGER_APPROVED", 0)))
col4.metric("Final Approved", int(pipeline.get("FINAL_APPROVED", 0)))

st.markdown("---")

# ===============================
# BORROWER TYPE ANALYSIS
# ===============================
st.markdown("## 🧑‍💼 Borrower Type Distribution")

if "borrower_type" in df.columns:
    st.bar_chart(df["borrower_type"].value_counts())

st.markdown("---")

# ===============================
# PORTFOLIO TABLE
# ===============================
st.markdown("## 📋 Portfolio Details")

st.dataframe(df.sort_values("created_at", ascending=False))