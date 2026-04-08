import streamlit as st
from db.supabase_client import supabase
from datetime import datetime
from workflow.sidebar_menu import render_sidebar
from institution_access import normalize_role, get_display_name, enforce_institution_access, build_actor_entry, render_history, get_stage_actor

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
role = normalize_role(profile.get("role"))
institution = profile.get("institution") or ""

# ===============================
# SIDEBAR
# ===============================
render_sidebar(role)
enforce_institution_access(profile, "page")

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
st.caption(f"Institution: {institution} | User: {display_name} | Email: {email} | Role: {role}")

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
    f"{a['client_name']} | ₦{a['loan_amount']:,.0f} | Score {a.get('score', 0)}": a["id"]
    for a in applications
}

selected_label = st.selectbox("Select Application", list(app_map.keys()))
selected_id = app_map[selected_label]

# ALWAYS FETCH FRESH RECORD
app_resp = supabase.table("loan_applications") \
    .select("*") \
    .eq("id", selected_id) \
    .single() \
    .execute()

app = app_resp.data

# =========================================================
# HELPERS
# =========================================================
def safe_text(val, fallback="—"):
    if val is None:
        return fallback
    if isinstance(val, str) and val.strip() in ["", "None", "null"]:
        return fallback
    return val

def clean_list(values):
    if not values:
        return []
    cleaned = []
    for v in values:
        if v is None:
            continue
        s = str(v).replace("•", "").strip()
        if s and s.lower() not in ["none", "null", "—"]:
            cleaned.append(s)
    return cleaned

def generate_bank_grade_memo(record):
    name = record.get("client_name", "Borrower")
    loan_amount = float(record.get("loan_amount") or 0)
    purpose = record.get("loan_purpose") or "business operations"
    tenor = record.get("tenor") or 0

    repayment = float(record.get("monthly_repayment") or 0)
    reserve = float(record.get("cash_reserve") or 0)
    outstanding = float(record.get("total_outstanding_loans") or 0)
    collateral = float(record.get("collateral_value") or 0)
    default_history = str(record.get("default_history") or "").strip().lower()

    score = 0
    strengths = []
    risks = []

    if repayment <= 0:
        score += 2
        strengths.append("No immediate repayment burden has been recorded")
    elif reserve > repayment * 3:
        score += 3
        strengths.append("Strong liquidity buffer relative to repayment obligations")
    elif reserve > repayment:
        score += 2
        strengths.append("Moderate liquidity support for repayment")
    else:
        risks.append("Weak liquidity position relative to repayment burden")

    if loan_amount > 0:
        if collateral >= loan_amount:
            score += 3
            strengths.append("Fully secured facility with adequate collateral coverage")
        elif collateral >= 0.5 * loan_amount:
            score += 2
            strengths.append("Partial collateral support available")
        else:
            risks.append("Insufficient collateral coverage")
    else:
        risks.append("Loan amount requires validation")

    if default_history in ["none", "", "no", "nil", "n/a"]:
        score += 2
        strengths.append("No prior default history observed")
    else:
        score -= 2
        risks.append("Adverse credit history detected")

    if outstanding <= 0:
        score += 1
        strengths.append("No material existing debt exposure recorded")
    elif outstanding < loan_amount:
        score += 1
        strengths.append("Manageable existing debt exposure")
    else:
        risks.append("High existing financial obligations")

    if score >= 6:
        decision = "APPROVE"
        risk_level = "Low Risk"
    elif score >= 3:
        decision = "APPROVE WITH CONDITIONS"
        risk_level = "Moderate Risk"
    else:
        decision = "REJECT"
        risk_level = "High Risk"

    borrower_summary = (
        f"{name} is requesting a loan facility to support {purpose}. "
        f"The borrower currently maintains outstanding obligations of ₦{outstanding:,.0f} "
        f"and a proposed monthly repayment obligation of ₦{repayment:,.0f}."
    )

    facility_request = (
        f"A facility of ₦{loan_amount:,.0f} is requested for a tenor of {tenor} months "
        f"to finance {purpose}."
    )

    risk_assessment = (
        f"The facility is assessed as {risk_level}. The evaluation reflects the borrower’s "
        f"liquidity position, collateral adequacy, existing exposure profile, and credit history. "
        f"Collateral coverage stands at ₦{collateral:,.0f} while available liquidity buffer is "
        f"estimated at ₦{reserve:,.0f}."
    )

    decision_summary = (
        f"Based on the overall credit assessment, the facility is recommended for {decision}."
    )

    if decision == "APPROVE":
        recommendation = "The facility is recommended for APPROVAL without conditions."
    elif decision == "APPROVE WITH CONDITIONS":
        recommendation = (
            "The facility is recommended for APPROVAL subject to:\n"
            "• Verification of financial and operating records\n"
            "• Ongoing monitoring of repayment performance\n"
            "• Proper perfection of collateral documentation"
        )
    else:
        recommendation = (
            "The facility is recommended for REJECTION due to weak credit fundamentals "
            "and an unfavorable risk-return profile."
        )

    return {
        "borrower_summary": borrower_summary,
        "facility_request": facility_request,
        "risk_assessment": risk_assessment,
        "decision_summary": decision_summary,
        "ai_strengths": strengths if strengths else ["No strong factors identified"],
        "ai_risk_flags": risks if risks else ["No major risks identified"],
        "ai_recommendation": recommendation
    }

# =========================================================
# FALLBACK MEMO LOGIC
# =========================================================
saved_strengths = clean_list(app.get("ai_strengths"))
saved_risks = clean_list(app.get("ai_risk_flags"))

has_saved_memo = any([
    safe_text(app.get("borrower_summary"), "") != "",
    safe_text(app.get("facility_request"), "") != "",
    safe_text(app.get("risk_assessment"), "") != "",
    safe_text(app.get("decision_summary"), "") != "",
    len(saved_strengths) > 0,
    len(saved_risks) > 0,
    safe_text(app.get("ai_recommendation"), "") != ""
])

if has_saved_memo:
    memo = {
        "borrower_summary": safe_text(app.get("borrower_summary")),
        "facility_request": safe_text(app.get("facility_request")),
        "risk_assessment": safe_text(app.get("risk_assessment")),
        "decision_summary": safe_text(app.get("decision_summary")),
        "ai_strengths": saved_strengths if saved_strengths else ["No strong factors identified"],
        "ai_risk_flags": saved_risks if saved_risks else ["No major risks identified"],
        "ai_recommendation": safe_text(app.get("ai_recommendation"))
    }
else:
    memo = generate_bank_grade_memo(app)

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
# CREDIT ASSESSMENT MEMO
# =========================================================
st.markdown("## 🧾 Credit Assessment Memo")

st.markdown(f"""
**Borrower Summary**  
{memo["borrower_summary"]}

**Facility Request**  
{memo["facility_request"]}

**Risk Assessment**  
{memo["risk_assessment"]}

**Decision Summary**  
{memo["decision_summary"]}
""")

st.markdown("### ✅ Key Strengths")
for s in memo["ai_strengths"]:
    st.markdown(f"• {s}")

st.markdown("### ⚠️ Key Risks")
for r in memo["ai_risk_flags"]:
    st.markdown(f"• {r}")

st.markdown("### 📌 Recommendation")
st.markdown(memo["ai_recommendation"])

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
render_history(history)

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

with col1:
    if st.button("Approve"):
        history = app.get("approval_history") or []
        history.append(build_actor_entry(profile, user, role, "APPROVED", decision_note))

        supabase.table("loan_applications") \
            .update({
                "workflow_status": "FINAL_APPROVED",
                "approval_history": history,
                "final_notes": final_notes
            }) \
            .eq("id", app["id"]) \
            .execute()

        st.session_state.last_viewed_app = app["id"]
        st.success("Approved successfully")
        st.rerun()

with col2:
    if st.button("Reject"):
        history = app.get("approval_history") or []
        history.append(build_actor_entry(profile, user, role, "REJECTED", decision_note))

        supabase.table("loan_applications") \
            .update({
                "workflow_status": "FINAL_REJECTED",
                "approval_history": history,
                "final_notes": final_notes
            }) \
            .eq("id", app["id"]) \
            .execute()

        st.session_state.last_viewed_app = app["id"]
        st.success("Rejected successfully")
        st.rerun()

# =========================================================
# WORKFLOW TRACE
# =========================================================
st.markdown("---")
st.markdown("## 🔄 Workflow Trace")

st.write(f"**Initiated By:** {get_stage_actor(history, 'initiator')}")
st.write(f"**Analyst:** {get_stage_actor(history, 'analyst')}")
st.write(f"**Manager:** {get_stage_actor(history, 'manager')}")
st.write(f"**Current Status:** {app.get('workflow_status')}")