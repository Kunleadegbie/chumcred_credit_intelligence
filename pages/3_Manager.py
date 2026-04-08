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

if not allow("manager"):
    st.error("Access denied")
    st.stop()
st.title("🏁 Credit Manager Desk")
st.caption(f"Institution: {institution}")

# =========================================================
# LOAD APPLICATIONS (ONLY ANALYST APPROVED)
# =========================================================
applications = supabase.table("loan_applications") \
    .select("*") \
    .eq("institution", institution) \
    .eq("workflow_status", "ANALYST_APPROVED") \
    .order("created_at", desc=True) \
    .execute().data

if not applications:
    st.info("No applications awaiting manager review.")
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
# APPLICATION DETAILS (READ ONLY)
# =========================================================
st.markdown("## 📄 Application Overview")

col1, col2 = st.columns(2)

col1.write(f"**Client Name:** {app['client_name']}")
col1.write(f"**Loan Amount:** ₦{app['loan_amount']:,.0f}")
col1.write(f"**Tenor:** {app.get('tenor')} months")

col2.write(f"**Borrower Type:** {app.get('borrower_type')}")
col2.write(f"**Loan Purpose:** {app.get('loan_purpose')}")
col2.write(f"**Score:** {app.get('score')}")

st.markdown("---")

# =========================================================
# FINANCIAL SUMMARY
# =========================================================
st.markdown("## 📊 Financial Summary")

st.write(f"**Outstanding Loans:** ₦{app.get('total_outstanding_loans', 0):,.0f}")
st.write(f"**Monthly Repayment:** ₦{app.get('monthly_repayment', 0):,.0f}")
st.write(f"**Default History:** {app.get('default_history')}")

st.markdown("---")

# =========================================================
# COLLATERAL & BUFFER
# =========================================================
st.markdown("## 🏦 Collateral & Buffer")

st.write(f"**Collateral Type:** {app.get('collateral_type')}")
st.write(f"**Collateral Value:** ₦{app.get('collateral_value', 0):,.0f}")
st.write(f"**Cash Reserve:** ₦{app.get('cash_reserve', 0):,.0f}")

st.markdown("---")

# =========================================================
# AI INSIGHT
# =========================================================
st.markdown("## 🤖 AI Credit Insight")

ai = app

st.markdown("## 🧾 Credit Memo")

st.markdown(f"""
<div style="padding:20px;border:1px solid #e6e6e6;border-radius:10px;background:#fafafa;line-height:1.8;">

<b>Borrower Profile</b><br>
{ai.get("borrower_profile")}<br><br>

<b>Facility Details</b><br>
{ai.get("facility_details")}<br><br>

<b>Financial Summary</b><br>
{ai.get("financial_summary")}<br><br>

<b>Risk Assessment</b><br>
{ai.get("risk_assessment")}<br><br>

<b>Mitigating Factors</b><br>
{ai.get("mitigants")}<br><br>

<b>Recommendation</b><br>
<b>{ai.get("recommendation")}</b>

</div>
""", unsafe_allow_html=True)
st.markdown("## 🧾 Credit Assessment Memo")

st.markdown(
    f"""
<div style="
    border:1px solid #e6e6e6;
    border-radius:10px;
    padding:20px;
    background-color:#fafafa;
    font-size:15.5px;
    line-height:1.8;
    color:#222;
">

<b>Borrower Summary</b><br>
{app.get('client_name')} is a {app.get('borrower_type')} customer applying for credit facilities.

<br><br>

<b>Facility Request</b><br>
The applicant is seeking a loan of <b>₦{app.get('loan_amount'):,.0f}</b> 
for <b>{app.get('loan_purpose')}</b> over a tenor of 
<b>{app.get('tenor')} months</b>.

<br><br>

<b>Risk Assessment</b><br>

<br><br>

<b>Decision Summary</b><br>
Based on the assessment, the application is recommended for 
<b>{app.get('decision', app.get('ai_recommendation', 'N/A'))}</b>

</div>
""",
    unsafe_allow_html=True
)

# Strengths
st.markdown("### ✅ Key Strengths")
for s in app.get("ai_strengths", []) or []:
    st.markdown(f"• {s}")

# Risks
st.markdown("### ⚠️ Key Risks")
for r in app.get("ai_risk_flags", []) or []:
    st.markdown(f"• {r}")

# Recommendation
st.markdown("### 📌 Recommendation")
st.write(app.get("ai_recommendation"))


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
# ANALYST REVIEW (READ ONLY)
# =========================================================
st.markdown("## 🧾 Analyst Review")

st.write(f"**Analyst Notes:** {app.get('analyst_notes', 'No notes provided')}")

st.markdown("---")

# =========================================================
# MANAGER DECISION
# =========================================================
st.markdown("## ✍️ Manager Decision")

manager_notes = st.text_area("Manager Notes")
decision_note = st.text_area(
    "Approval / Rejection Note",
    key="manager_note"
)


col1, col2 = st.columns(2)

# ===============================
# APPROVE → FINAL APPROVER
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
                "workflow_status": "MANAGER_APPROVED",
                "approval_history": history
            }) \
            .eq("id", app["id"]) \
            .execute()

        st.session_state.last_viewed_app = app["id"]
        st.success("Approved successfully")
    

# ===============================
# REJECT → BACK TO ANALYST + INITIATOR
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
                "workflow_status": "MANAGER_REJECTED",
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
st.write(f"**Current Status:** {app.get('workflow_status')}")