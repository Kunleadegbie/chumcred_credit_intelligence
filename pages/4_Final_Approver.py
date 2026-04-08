import streamlit as st
from db.supabase_client import supabase
from workflow.application_service import update_application_status
from datetime import datetime
from workflow.sidebar_menu import render_sidebar

# ===============================
# AUTH CHECK
# ===============================
if "user" not in st.session_state:
    st.switch_page("app.py")

user = st.session_state.user

# ===============================
# FETCH PROFILE (SAFE)
# ===============================
resp = supabase.table("user_profiles") \
    .select("*") \
    .eq("id", user.id) \
    .execute()

if resp.data:
    profile = resp.data[0]
else:
    profile = {
        "id": user.id,
        "email": user.email,
        "role": "pending",
        "institution": ""
    }
    supabase.table("user_profiles").insert(profile).execute()

# ===============================
# EXTRACT ROLE
# ===============================
role = (profile.get("role") or "").strip().lower()
institution = profile.get("institution") or ""

# ===============================
# SIDEBAR
# ===============================
render_sidebar(role)

# ===============================
# ACCESS CONTROL
# ===============================
def allow(*allowed):
    allowed = [r.lower() for r in allowed]
    return role in allowed or role == "super_admin"

if not allow("final_approver"):
    st.error("Access denied")
    st.stop()
st.title("🏛️ Final Credit Authority")
st.caption(f"Institution: {institution}")

# =========================================================
# LOAD APPLICATIONS (ONLY MANAGER APPROVED)
# =========================================================
applications = supabase.table("loan_applications") \
    .select("*") \
    .eq("institution", institution) \
    .eq("workflow_status", "MANAGER_APPROVED") \
    .order("created_at", desc=True) \
    .execute().data

if not applications:
    st.info("No applications awaiting final approval.")
    st.stop()

# =========================================================
# SELECT APPLICATION
# =========================================================
app_map = {
    f"{a['client_name']} | ₦{a['loan_amount']:,.0f} | Score {a['score']}": a
    for a in applications
}

selected_label = st.selectbox("Select Application", list(app_map.keys()))

# DEFAULT SELECTION
app = app_map[selected_label]

# 🔥 OVERRIDE IF USER JUST TOOK ACTION
if "last_viewed_app" in st.session_state:

    last_id = st.session_state.last_viewed_app

    result = supabase.table("loan_applications") \
        .select("*") \
        .eq("id", last_id) \
        .execute().data

    if result:
        app = result[0]
# =========================================================
# EXECUTIVE SUMMARY VIEW
# =========================================================
st.markdown("## 📄 Executive Summary")

col1, col2 = st.columns(2)

col1.write(f"**Client Name:** {app['client_name']}")
col1.write(f"**Loan Amount:** ₦{app['loan_amount']:,.0f}")
col1.write(f"**Tenor:** {app.get('tenor')} months")

col2.write(f"**Borrower Type:** {app.get('borrower_type')}")
col2.write(f"**Loan Purpose:** {app.get('loan_purpose')}")
col2.write(f"**Score:** {app.get('score')}")

st.markdown("---")

# =========================================================
# RISK & FINANCIAL POSITION
# =========================================================
st.markdown("## ⚠️ Risk & Financial Position")

st.write(f"**Outstanding Loans:** ₦{app.get('total_outstanding_loans', 0):,.0f}")
st.write(f"**Monthly Repayment:** ₦{app.get('monthly_repayment', 0):,.0f}")
st.write(f"**Default History:** {app.get('default_history')}")

st.markdown("---")

# =========================================================
# COLLATERAL & SUPPORT
# =========================================================
st.markdown("## 🏦 Collateral & Support")

st.write(f"**Collateral Type:** {app.get('collateral_type')}")
st.write(f"**Collateral Value:** ₦{app.get('collateral_value', 0):,.0f}")
st.write(f"**Cash Reserve:** ₦{app.get('cash_reserve', 0):,.0f}")

st.markdown("---")

# =========================================================
# CREDIT ASSESSMENT MEMO (FROM DATABASE - STANDARDIZED)
# =========================================================

st.markdown("## 🧾 Credit Assessment Memo")

st.markdown(f"""
**Borrower Summary**  
{app.get("borrower_summary", "Not available")}

**Facility Request**  
{app.get("facility_request", "Not available")}

**Risk Assessment**  
{app.get("risk_assessment", "Not available")}

**Decision Summary**  
{app.get("decision_summary", "Not available")}
""")

# ===============================
# KEY STRENGTHS
# ===============================
st.markdown("### ✅ Key Strengths")
strengths = app.get("ai_strengths") or []

for s in strengths:
    st.markdown(f"• {s.replace('•','').strip()}")

# ===============================
# KEY RISKS
# ===============================
st.markdown("### ⚠️ Key Risks")
risks = app.get("ai_risk_flags") or []

for r in risks:
    st.markdown(f"• {r.replace('•','').strip()}")

# ===============================
# RECOMMENDATION
# ===============================
st.markdown("### 📌 Recommendation")
st.markdown(app.get("ai_recommendation", "Not available"))

# =========================================================
# PRIOR REVIEWS (CHAIN OF DECISION)
# =========================================================
st.markdown("## 🧾 Decision Chain")

st.write(f"**Analyst Notes:** {app.get('analyst_notes', 'N/A')}")
st.write(f"**Manager Notes:** {app.get('manager_notes', 'N/A')}")

st.markdown("---")

# ===============================
# APPROVAL HISTORY
# ===============================

st.markdown("## 🧾 Approval History")

history = app.get("approval_history") or []

if history:
    for h in history:
        st.markdown(
            f"**{h['stage']}** → {h['action']}  \n"
            f"Note: {h.get('note','')}  \n"
            f"Time: {h['timestamp']}"
        )
else:
    st.info("No approvals yet")

# =========================================================
# FINAL DECISION
# =========================================================
st.markdown("## 🏁 Final Decision")

final_notes = st.text_area("Final Approval Notes")
decision_note = st.text_area(
    "Approval / Rejection Note",
    key="final_note"
)


col1, col2 = st.columns(2)

# ===============================
# FINAL APPROVE
# ===============================
with col1:

    if st.button("Approve"):

        history = app.get("approval_history") or []

        history.append({
            "stage": role.upper(),
            "action": "APPROVED",
            "user": user.id,
            "timestamp": str(datetime.now()),
            "note": st.session_state.get("decision_note", "")
        })

        supabase.table("loan_applications") \
            .update({
                "workflow_status": "FINAL_APPROVED",
                "approval_history": history
            }) \
            .eq("id", app["id"]) \
            .execute()

        st.session_state.last_viewed_app = app["id"]
        st.success("Approved successfully")
    

# ===============================
# REJECT
# ===============================
with col2:
    if st.button("Reject"):

        history = app.get("approval_history") or []

        history.append({
            "stage": role.upper(),
            "action": "REJECTED",
            "user": user.id,
            "timestamp": str(datetime.now()),
            "note": st.session_state.get("decision_note", "")
        })

        supabase.table("loan_applications") \
            .update({
                "workflow_status": "FINAL_REJECTED",
                "approval_history": history
            }) \
            .eq("id", app["id"]) \
            .execute()

        st.session_state.last_viewed_app = app["id"]
        st.success("Rejected successfully")

# =========================================================
# WORKFLOW TRACE
# =========================================================
st.markdown("---")
st.markdown("## 🔄 Workflow Trace")

st.write(f"**Initiated By:** {app.get('initiated_by')}")
st.write(f"**Analyst:** {app.get('analyst_review_by')}")
st.write(f"**Manager:** {app.get('manager_review_by')}")
st.write(f"**Current Status:** {app.get('workflow_status')}")