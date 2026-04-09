
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
resp = supabase.table("user_profiles").select("*").eq("id", user.id).execute()
if resp.data:
    profile = resp.data[0]
else:
    profile = {
        "id": user.id,
        "email": getattr(user, "email", ""),
        "role": "pending",
        "institution": ""
    }
    supabase.table("user_profiles").insert(profile).execute()

# ===============================
# EXTRACT ROLE
# ===============================
role = normalize_role(profile.get("role"))
institution = profile.get("institution") or ""
email = profile.get("email") or getattr(user, "email", "") or ""
display_name = get_display_name(profile, user)

# ===============================
# SIDEBAR
# ===============================
render_sidebar(role)
enforce_institution_access(profile, "page")

# ===============================
# ACCESS CONTROL
# ===============================
def allow(*allowed):
    allowed = [normalize_role(r) for r in allowed]
    return role in allowed or role == "super_admin"

if not allow("manager"):
    st.error("Access denied")
    st.stop()

st.title("🏁 Credit Manager Desk")
st.caption(f"Institution: {institution} | User: {display_name} | Email: {email} | Role: {role}")

# =========================================================
# LOAD APPLICATIONS
# =========================================================
all_applications = supabase.table("loan_applications")     .select("*")     .eq("institution", institution)     .order("created_at", desc=True)     .execute().data or []

allowed_statuses = {
    "ANALYST_APPROVED",
    "MANAGER_APPROVED",
    "MANAGER_REJECTED",
    "FINAL_APPROVED",
    "FINAL_REJECTED",
}

applications = [
    a for a in all_applications
    if str(a.get("workflow_status") or "").strip().upper() in allowed_statuses
]

if not applications:
    st.info("No applications awaiting manager review.")
    st.stop()

# =========================================================
# SELECT APPLICATION
# =========================================================
def format_money(value):
    try:
        return f"₦{float(value or 0):,.0f}"
    except Exception:
        return "₦0"

app_labels = []
app_map = {}

for a in applications:
    label = (
        f"{a.get('client_name', 'Unknown Client')} | "
        f"{format_money(a.get('loan_amount'))} | "
        f"Score {a.get('score', 0)} | "
        f"{a.get('workflow_status', 'UNKNOWN')}"
    )
    app_labels.append(label)
    app_map[label] = a.get("id")

default_index = 0
last_viewed_app = st.session_state.get("last_viewed_app")
if last_viewed_app:
    for idx, label in enumerate(app_labels):
        if app_map[label] == last_viewed_app:
            default_index = idx
            break

selected_label = st.selectbox("Select Application", app_labels, index=default_index)
selected_id = app_map[selected_label]

app_resp = supabase.table("loan_applications")     .select("*")     .eq("id", selected_id)     .single()     .execute()
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


def build_consistent_memo(record, metrics):
    risk_grade = str(metrics.get("risk_grade") or "C").strip().upper()
    risk_level = "Low Risk" if risk_grade == "A" else "Moderate Risk" if risk_grade == "B" else "High Risk"
    credit_score = int(metrics.get("credit_score") or record.get("credit_score") or record.get("score") or 0)
    dscr = float(metrics.get("dscr") or record.get("dscr") or 0)
    decision = str(record.get("decision") or ("APPROVE" if risk_grade == "A" else "APPROVE WITH CONDITIONS" if risk_grade == "B" else "REJECT")).strip()
    name = record.get("client_name", "Borrower")
    purpose = str(record.get("loan_purpose") or "business operations").strip()
    tenor = int(float(record.get("tenor") or 1))
    loan_amount = float(record.get("loan_amount") or 0)

    return {
        "borrower_summary": safe_text(record.get("borrower_summary"), f"{name} is requesting a loan facility for {purpose}."),
        "facility_request": safe_text(record.get("facility_request"), f"A facility of ₦{loan_amount:,.0f} is requested for a tenor of {tenor} months."),
        "risk_assessment": f"The obligor is graded {risk_grade} ({risk_level}) with a credit score of {credit_score}/100 and DSCR of {dscr:.2f}x.",
        "decision_summary": f"Final recommendation is {decision}.",
        "ai_strengths": clean_list(record.get("ai_strengths")) or ["No strong factors identified"],
        "ai_risk_flags": clean_list(record.get("ai_risk_flags")) or ["No major risks identified"],
        "ai_recommendation": safe_text(record.get("ai_recommendation"), f"Facility recommendation: {decision}."),
    }


def calculate_bank_grade_metrics(record):
    loan_amount = float(record.get("loan_amount", 0) or 0)
    monthly_repayment = float(record.get("monthly_repayment", 0) or 0)
    collateral_value = float(record.get("collateral_value", 0) or 0)
    cash_reserve = float(record.get("cash_reserve", 0) or 0)
    avg_balance = float(record.get("avg_account_balance", 0) or record.get("average_balance", 0) or 0)
    income = float(record.get("monthly_income", 0) or record.get("revenue", 0) or 0)
    expenses = float(record.get("monthly_expenses", 0) or record.get("expenses", 0) or 0)
    available = max(income - expenses, 0)
    dscr = round(available / monthly_repayment, 2) if monthly_repayment > 0 else 0.0
    collateral_cover = round(collateral_value / loan_amount, 2) if loan_amount > 0 else 0.0
    score = int(float(record.get("credit_score") or record.get("score") or 0))
    if score >= 80:
        risk_grade = "A"
    elif score >= 65:
        risk_grade = "B"
    else:
        risk_grade = "C"
    return {"credit_score": score, "risk_grade": risk_grade, "dscr": dscr, "collateral_cover": collateral_cover}


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

saved_strengths = clean_list(app.get("ai_strengths"))
saved_risks = clean_list(app.get("ai_risk_flags"))
metrics = calculate_bank_grade_metrics(app)
memo = build_consistent_memo(app, metrics)

history = app.get("approval_history") or []
existing_manager_notes = str(app.get("manager_notes") or "")
existing_decision_note = ""
for item in reversed(history):
    if str(item.get("stage", "")).upper() == role.upper():
        existing_decision_note = str(item.get("note", "") or "")
        break

is_pending_manager_action = str(app.get("workflow_status") or "").strip().upper() == "ANALYST_APPROVED"

st.markdown("## 📄 Application Overview")
col1, col2 = st.columns(2)
col1.write(f"**Client Name:** {app['client_name']}")
col1.write(f"**Loan Amount:** {format_money(app.get('loan_amount'))}")
col1.write(f"**Tenor:** {app.get('tenor')} months")
col2.write(f"**Borrower Type:** {app.get('borrower_type')}")
col2.write(f"**Loan Purpose:** {app.get('loan_purpose')}")
col2.write(f"**Score:** {app.get('score')}")

st.markdown("---")
st.markdown("## 🏦 Bank-Grade Risk Metrics")
metrics = calculate_bank_grade_metrics(app)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Credit Score", f"{metrics.get('credit_score', app.get('score', 0))}/100")
m2.metric("Risk Grade", metrics.get("risk_grade", "N/A"))
m3.metric("DSCR", f"{metrics.get('dscr', 0):.2f}x")
m4.metric("Collateral Cover", f"{metrics.get('collateral_cover', 0):.2f}x")

st.markdown("---")
st.markdown("## 📊 Financial Summary")
st.write(f"**Outstanding Loans:** {format_money(app.get('total_outstanding_loans'))}")
st.write(f"**Monthly Repayment:** {format_money(app.get('monthly_repayment'))}")
st.write(f"**Default History:** {app.get('default_history')}")

st.markdown("---")
st.markdown("## 🏦 Collateral & Buffer")
st.write(f"**Collateral Type:** {app.get('collateral_type')}")
st.write(f"**Collateral Value:** {format_money(app.get('collateral_value'))}")
st.write(f"**Cash Reserve:** {format_money(app.get('cash_reserve'))}")

st.markdown("---")
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

st.markdown("## 🧾 Approval History")
render_history(history)

st.markdown("## 🧾 Analyst Review")
st.write(f"**Analyst Notes:** {app.get('analyst_notes', 'No notes provided')}")
st.write(f"**Reviewed By:** {get_stage_actor(history, 'analyst')}")

st.markdown("---")
st.markdown("## ✍️ Manager Decision")
manager_notes = st.text_area("Manager Notes", value=existing_manager_notes, key=f"manager_notes_{app['id']}")
decision_note = st.text_area("Approval / Rejection Note", value=existing_decision_note, key=f"manager_note_{app['id']}")

if not is_pending_manager_action:
    st.info("This application has already been reviewed at manager stage. Saved data is shown for reference.")

col1, col2 = st.columns(2)
with col1:
    if st.button("Approve", disabled=not is_pending_manager_action, key=f"approve_manager_{app['id']}"):
        updated_history = app.get("approval_history") or []
        updated_history.append(build_actor_entry(profile, user, role, "APPROVED", decision_note))
        supabase.table("loan_applications").update({
            "workflow_status": "MANAGER_APPROVED",
            "approval_history": updated_history,
            "manager_notes": manager_notes,
            "score": metrics.get("credit_score", app.get("score")),
            "credit_score": metrics.get("credit_score", app.get("credit_score")),
            "risk_grade": metrics.get("risk_grade", app.get("risk_grade")),
            "dscr": metrics.get("dscr", app.get("dscr")),
            "borrower_summary": memo["borrower_summary"],
            "facility_request": memo["facility_request"],
            "risk_assessment": memo["risk_assessment"],
            "decision_summary": memo["decision_summary"],
            "ai_strengths": memo["ai_strengths"],
            "ai_risk_flags": memo["ai_risk_flags"],
            "ai_recommendation": memo["ai_recommendation"],
        }).eq("id", app["id"]).execute()
        st.session_state.last_viewed_app = app["id"]
        st.success("Approved successfully")
        st.rerun()

with col2:
    if st.button("Reject", disabled=not is_pending_manager_action, key=f"reject_manager_{app['id']}"):
        updated_history = app.get("approval_history") or []
        updated_history.append(build_actor_entry(profile, user, role, "REJECTED", decision_note))
        supabase.table("loan_applications").update({
            "workflow_status": "MANAGER_REJECTED",
            "approval_history": updated_history,
            "manager_notes": manager_notes,
            "score": metrics.get("credit_score", app.get("score")),
            "credit_score": metrics.get("credit_score", app.get("credit_score")),
            "risk_grade": metrics.get("risk_grade", app.get("risk_grade")),
            "dscr": metrics.get("dscr", app.get("dscr")),
            "borrower_summary": memo["borrower_summary"],
            "facility_request": memo["facility_request"],
            "risk_assessment": memo["risk_assessment"],
            "decision_summary": memo["decision_summary"],
            "ai_strengths": memo["ai_strengths"],
            "ai_risk_flags": memo["ai_risk_flags"],
            "ai_recommendation": memo["ai_recommendation"],
        }).eq("id", app["id"]).execute()
        st.session_state.last_viewed_app = app["id"]
        st.success("Rejected successfully")
        st.rerun()

st.markdown("---")
st.markdown("## 🔄 Workflow Trace")
st.write(f"**Initiated By:** {app.get('initiated_by')}")
st.write(f"**Analyst:** {get_stage_actor(history, 'analyst')}")
st.write(f"**Manager:** {get_stage_actor(history, 'manager')}")
st.write(f"**Current Status:** {app.get('workflow_status')}")
