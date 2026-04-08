import streamlit as st
import pandas as pd

from db.supabase_client import supabase
from workflow.application_service import get_all_applications, get_institution_applications
from workflow.sidebar_menu import render_sidebar
from institution_access import normalize_role, get_display_name, enforce_institution_access

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

role = normalize_role(profile.get("role"))
institution = profile.get("institution") or ""
email = profile.get("email") or ""
display_name = get_display_name(profile, user)

# ===============================
# SIDEBAR
# ===============================
render_sidebar(role)
enforce_institution_access(profile, "analytics")

# ===============================
# ACCESS CONTROL
# ===============================
allowed_roles = ["manager", "final_approver", "institution_admin", "super_admin"]
if role not in allowed_roles:
    st.error("Access denied")
    st.stop()

st.title("📊 Portfolio Analytics Dashboard")
st.caption(f"Institution: {institution} | User: {display_name} | Email: {email} | Role: {role}")

# ===============================
# LOAD DATA
# ===============================
try:
    if role == "super_admin":
        data = get_all_applications().data

        if not data:
            st.info("No data available yet.")
            st.stop()

        df_all = pd.DataFrame(data)

        if "institution" in df_all.columns and not df_all.empty:
            institutions = sorted([i for i in df_all["institution"].dropna().unique().tolist() if str(i).strip()])
            if institutions:
                selected_institution = st.selectbox("Select Institution", institutions)
                df = df_all[df_all["institution"] == selected_institution].copy()
            else:
                df = df_all.copy()
        else:
            df = df_all.copy()

    else:
        data = get_institution_applications(institution).data
        if not data:
            st.info("No data available yet for your institution.")
            st.stop()
        df = pd.DataFrame(data)

except Exception as e:
    st.error(f"Data load failed: {e}")
    st.stop()

if df.empty:
    st.info("No records found for the selected institution.")
    st.stop()

# ===============================
# NORMALIZE COLUMNS
# ===============================
if "score" not in df.columns:
    df["score"] = 0
if "loan_amount" not in df.columns:
    df["loan_amount"] = 0
if "workflow_status" not in df.columns:
    df["workflow_status"] = "UNKNOWN"
if "risk_grade" not in df.columns:
    df["risk_grade"] = "N/A"
if "dscr" not in df.columns:
    df["dscr"] = 0.0

# ===============================
# EXECUTIVE SUMMARY
# ===============================
st.markdown("## 📌 Executive Summary")

total_loans = len(df)
total_exposure = pd.to_numeric(df["loan_amount"], errors="coerce").fillna(0).sum()
avg_score = pd.to_numeric(df["score"], errors="coerce").fillna(0).mean()
avg_dscr = pd.to_numeric(df["dscr"], errors="coerce").fillna(0).mean()

approval_rate = (df["workflow_status"] == "FINAL_APPROVED").mean() if total_loans else 0
rejection_rate = df["workflow_status"].astype(str).str.contains("REJECTED", case=False, na=False).mean() if total_loans else 0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Loans", total_loans)
col2.metric("Total Exposure", f"₦{total_exposure:,.0f}")
col3.metric("Avg Score", f"{avg_score:.0f}")
col4.metric("Approval Rate", f"{approval_rate:.0%}")
col5.metric("Avg DSCR", f"{avg_dscr:.2f}x")

st.markdown("---")

# ===============================
# WORKFLOW DISTRIBUTION
# ===============================
st.markdown("## 📈 Loan Status Distribution")
status_counts = df["workflow_status"].astype(str).value_counts()
st.bar_chart(status_counts)

st.markdown("---")

# ===============================
# RISK ANALYSIS
# ===============================
st.markdown("## ⚠️ Risk Grade Distribution")

if "risk_grade" in df.columns:
    risk_counts = df["risk_grade"].fillna("N/A").astype(str).value_counts()
    st.bar_chart(risk_counts)
else:
    st.info("Risk grade data not available yet.")

st.markdown("---")

# ===============================
# LOAN SIZE VS RISK SCORE
# ===============================
st.markdown("## 📊 Loan Amount vs Credit Score")
plot_df = df[["loan_amount", "score"]].copy()
plot_df["loan_amount"] = pd.to_numeric(plot_df["loan_amount"], errors="coerce").fillna(0)
plot_df["score"] = pd.to_numeric(plot_df["score"], errors="coerce").fillna(0)
st.scatter_chart(plot_df)

st.markdown("---")

# ===============================
# APPROVAL PIPELINE
# ===============================
st.markdown("## 🔄 Approval Pipeline")
pipeline = df["workflow_status"].astype(str).value_counts()

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
    st.bar_chart(df["borrower_type"].fillna("Unknown").astype(str).value_counts())
else:
    st.info("Borrower type data not available.")

st.markdown("---")

# ===============================
# PORTFOLIO TABLE
# ===============================
st.markdown("## 📋 Portfolio Details")

sort_col = "created_at" if "created_at" in df.columns else df.columns[0]
st.dataframe(df.sort_values(sort_col, ascending=False), use_container_width=True)
