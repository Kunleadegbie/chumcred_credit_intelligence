# Analyst page

import streamlit as st
from db.supabase_client import supabase
from datetime import datetime
from workflow.sidebar_menu import render_sidebar

if "user" not in st.session_state:
    st.switch_page("app.py")

user = st.session_state.user
resp = supabase.table("user_profiles").select("*").eq("id", user.id).execute()
if resp.data:
    profile = resp.data[0]
else:
    profile = {"id": user.id, "email": user.email, "role": "pending", "institution": ""}
    supabase.table("user_profiles").insert(profile).execute()


def normalize_role(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "_")


def get_display_name(profile_dict, current_user) -> str:
    for key in ["full_name", "name", "display_name", "username"]:
        value = str(profile_dict.get(key) or "").strip()
        if value:
            return value
    email_value = str(profile_dict.get("email") or getattr(current_user, "email", "") or "").strip()
    if email_value:
        return email_value.split("@")[0]
    return "User"


role = normalize_role(profile.get("role"))
institution = profile.get("institution") or ""
email = profile.get("email") or getattr(user, "email", "") or ""
display_name = get_display_name(profile, user)
render_sidebar(role)


def allow(*allowed):
    allowed = [normalize_role(r) for r in allowed]
    return role in allowed or role == "super_admin"


if not allow("analyst", "credit_analyst"):
    st.error("Access denied")
    st.stop()

st.markdown(
    """
<style>
.card {background-color:#fff;padding:20px;border-radius:12px;border:1px solid #e6e6e6;margin-bottom:15px;}
</style>
""",
    unsafe_allow_html=True,
)

st.title("🔎 Credit Analyst Desk")
st.caption(f"Institution: {institution or 'Not set'} | User: {display_name} | Email: {email} | Role: {role}")


def format_money(value):
    try:
        return f"₦{float(value or 0):,.0f}"
    except Exception:
        return "₦0"



def safe_float(value, default=0.0):
    try:
        if value in [None, "", "None", "null"]:
            return float(default)
        return float(value)
    except Exception:
        return float(default)



def safe_text(value, fallback="—"):
    if value is None:
        return fallback
    if isinstance(value, str) and value.strip() in ["", "None", "null"]:
        return fallback
    return value



def clean_list(values):
    if not values:
        return []
    cleaned = []
    for item in values:
        if item is None:
            continue
        text = str(item).replace("•", "").strip()
        if text and text.lower() not in ["none", "null", "—"]:
            cleaned.append(text)
    return cleaned



def unique_list(values):
    output = []
    seen = set()
    for item in values or []:
        text = str(item or "").strip()
        if not text:
            continue
        low = text.lower()
        if low not in seen:
            seen.add(low)
            output.append(text)
    return output



def build_safe_update_payload(existing_record, payload):
    return {key: value for key, value in payload.items() if key in (existing_record or {})}



def get_latest_stage_note(history_items, stage_name):
    for item in reversed(history_items or []):
        if str(item.get("stage", "")).upper() == str(stage_name).upper():
            note = str(item.get("note", "") or "").strip()
            if note:
                return note
    return ""



def estimate_monthly_net_cash_flow(record):
    borrower_type = str(record.get("borrower_type") or "").strip().lower()
    monthly_income = safe_float(record.get("monthly_income"))
    revenue = safe_float(record.get("revenue"))
    bank_inflow = safe_float(record.get("bank_inflow"))
    expenses = safe_float(record.get("monthly_expenses") or record.get("expenses"))
    deductions = safe_float(record.get("deductions"))
    daily_sales = safe_float(record.get("daily_sales"))
    avg_balance = safe_float(record.get("avg_account_balance") or record.get("average_balance"))
    cash_reserve = safe_float(record.get("cash_reserve"))
    loan_amount = safe_float(record.get("loan_amount"))
    tenor = max(int(safe_float(record.get("tenor"), 1) or 1), 1)

    if borrower_type == "salary earner":
        net_cash_flow = max(monthly_income - deductions, 0.0)
        gross_cash_flow = max(monthly_income, bank_inflow, 0.0)
    elif borrower_type == "sme":
        operating_surplus = revenue - expenses
        net_cash_flow = max(operating_surplus, bank_inflow - (expenses * 0.8), 0.0)
        gross_cash_flow = max(revenue, bank_inflow, 0.0)
    else:
        monthly_sales = daily_sales * 26 if daily_sales > 0 else 0.0
        net_cash_flow = max(monthly_sales - expenses, monthly_sales * 0.22, 0.0)
        gross_cash_flow = max(monthly_sales, bank_inflow, monthly_income, 0.0)

    if net_cash_flow <= 0:
        net_cash_flow = max((cash_reserve * 0.20), (avg_balance * 0.35), (loan_amount / tenor) * 1.10, 0.0)

    return round(net_cash_flow, 2), round(gross_cash_flow, 2)



def calculate_bank_grade(record):
    name = record.get("client_name", "Borrower")
    borrower_type = str(record.get("borrower_type") or "Borrower").strip()
    purpose = str(record.get("loan_purpose") or "business operations").strip()
    loan_amount = safe_float(record.get("loan_amount"))
    tenor = max(int(safe_float(record.get("tenor"), 1) or 1), 1)
    monthly_repayment = safe_float(record.get("monthly_repayment"))
    outstanding = safe_float(record.get("total_outstanding_loans"))
    collateral_value = safe_float(record.get("collateral_value"))
    cash_reserve = safe_float(record.get("cash_reserve"))
    avg_balance = safe_float(record.get("avg_account_balance") or record.get("average_balance"))
    default_history = str(record.get("default_history") or "").strip().lower()
    years = safe_float(record.get("years"))

    estimated_net_cash_flow, gross_cash_flow = estimate_monthly_net_cash_flow(record)
    dscr = 9.99 if monthly_repayment <= 0 else round(estimated_net_cash_flow / monthly_repayment, 2)
    collateral_cover = 0.0 if loan_amount <= 0 else round(collateral_value / loan_amount, 2)
    liquidity_ratio = 9.99 if monthly_repayment <= 0 else round((cash_reserve + avg_balance) / monthly_repayment, 2)

    score = 0
    strengths = []
    risks = []
    if dscr >= 2.00:
        score += 35
        strengths.append(f"Strong repayment capacity with DSCR of {dscr:.2f}x")
    elif dscr >= 1.50:
        score += 30
        strengths.append(f"Good repayment coverage with DSCR of {dscr:.2f}x")
    elif dscr >= 1.25:
        score += 25
        strengths.append(f"Acceptable repayment capacity with DSCR of {dscr:.2f}x")
    elif dscr >= 1.00:
        score += 18
        risks.append(f"Borderline repayment capacity with DSCR of {dscr:.2f}x")
    elif dscr >= 0.75:
        score += 10
        risks.append(f"Weak repayment capacity with DSCR of {dscr:.2f}x")
    else:
        score += 3
        risks.append(f"Unsatisfactory repayment capacity with DSCR of {dscr:.2f}x")

    if collateral_cover >= 1.20:
        score += 20
        strengths.append(f"Facility is well secured with collateral cover of {collateral_cover:.2f}x")
    elif collateral_cover >= 1.00:
        score += 18
        strengths.append(f"Facility is fully secured with collateral cover of {collateral_cover:.2f}x")
    elif collateral_cover >= 0.75:
        score += 14
        strengths.append(f"Reasonable collateral support available at {collateral_cover:.2f}x cover")
    elif collateral_cover >= 0.50:
        score += 9
        risks.append(f"Collateral support is moderate at {collateral_cover:.2f}x cover")
    elif collateral_cover > 0:
        score += 5
        risks.append(f"Collateral support is weak at {collateral_cover:.2f}x cover")
    else:
        risks.append("Facility is effectively unsecured")

    if liquidity_ratio >= 6:
        score += 15
        strengths.append("Strong liquidity buffer relative to repayment burden")
    elif liquidity_ratio >= 3:
        score += 12
        strengths.append("Good liquidity buffer supports repayment stability")
    elif liquidity_ratio >= 1.5:
        score += 9
        strengths.append("Moderate liquidity support available")
    elif liquidity_ratio >= 1.0:
        score += 6
        risks.append("Liquidity is adequate but not strong")
    else:
        score += 2
        risks.append("Liquidity buffer is weak for the proposed debt service")

    if outstanding <= 0:
        score += 10
        strengths.append("No material existing debt exposure recorded")
    elif loan_amount > 0 and outstanding <= (0.50 * loan_amount):
        score += 8
        strengths.append("Existing debt exposure is within manageable level")
    elif loan_amount > 0 and outstanding <= loan_amount:
        score += 6
        strengths.append("Existing debt exposure is moderate")
    else:
        score += 2
        risks.append("Existing debt exposure is high relative to requested facility")

    if default_history in ["no", "none", "", "nil", "n/a"]:
        score += 10
        strengths.append("No prior default history observed")
    else:
        risks.append("Adverse credit history/default flag detected")

    if years >= 5:
        score += 5
        strengths.append("Strong operating/employment stability track record")
    elif years >= 2:
        score += 4
        strengths.append("Moderate operating/employment stability observed")
    elif years >= 1:
        score += 3
    else:
        score += 1
        risks.append("Limited operating/employment history available")

    credit_score = int(max(0, min(round(score), 100)))
    if credit_score >= 80 and dscr >= 1.25 and default_history in ["no", "none", "", "nil", "n/a"]:
        risk_grade = "A"
        risk_level = "Low Risk"
        decision = "APPROVE"
    elif credit_score >= 65 and dscr >= 1.00:
        risk_grade = "B"
        risk_level = "Moderate Risk"
        decision = "APPROVE WITH CONDITIONS"
    else:
        risk_grade = "C"
        risk_level = "High Risk"
        decision = "REJECT"

    return {
        "credit_score": credit_score,
        "score": credit_score,
        "risk_grade": risk_grade,
        "risk_level": risk_level,
        "decision": decision,
        "dscr": round(dscr, 2),
        "borrower_summary": f"{name} is requesting a loan facility for {purpose}.",
        "facility_request": f"A facility of {format_money(loan_amount)} is requested for {tenor} months.",
        "risk_assessment": f"The obligor is graded {risk_grade} ({risk_level}) with a credit score of {credit_score}/100 and DSCR of {dscr:.2f}x.",
        "decision_summary": f"Final recommendation is {decision}.",
        "ai_strengths": unique_list(strengths) or ["No strong factors identified"],
        "ai_risk_flags": unique_list(risks) or ["No major risks identified"],
        "ai_recommendation": f"Facility recommendation: {decision}.",
    }


rows = (
    supabase.table("loan_applications")
    .select("*")
    .eq("institution", institution)
    .order("created_at", desc=True)
    .execute()
    .data
    or []
)
allowed_statuses = {
    "SUBMITTED",
    "ANALYST_APPROVED",
    "ANALYST_REJECTED",
    "MANAGER_APPROVED",
    "MANAGER_REJECTED",
    "FINAL_APPROVED",
    "FINAL_REJECTED",
}
applications = [row for row in rows if (row.get("workflow_status") or "") in allowed_statuses]

if not applications:
    st.info("No applications available for analyst review. If Initiator submitted a request and it is not showing here, confirm both users have the same institution in user_profiles.")
    st.stop()

app_options = {}
labels = []
for a in applications:
    label = f"{a.get('client_name','Unknown')} - {format_money(a.get('loan_amount'))} - Score {a.get('score',0)} - {a.get('workflow_status','UNKNOWN')}"
    labels.append(label)
    app_options[label] = a["id"]

default_index = 0
last_id = st.session_state.get("last_viewed_app")
if last_id:
    for idx, label in enumerate(labels):
        if app_options[label] == last_id:
            default_index = idx
            break

selected_label = st.selectbox("Select Application", labels, index=default_index)
selected_id = app_options[selected_label]
app = supabase.table("loan_applications").select("*").eq("id", selected_id).single().execute().data
bank_result = calculate_bank_grade(app)
history = app.get("approval_history") or []
existing_analyst_notes = str(app.get("analyst_notes") or "")
existing_decision_note = get_latest_stage_note(history, role.upper())
is_pending_analyst_action = (app.get("workflow_status") or "") == "SUBMITTED"

saved_strengths = clean_list(app.get("ai_strengths"))
saved_risks = clean_list(app.get("ai_risk_flags"))
memo = {
    "borrower_summary": safe_text(app.get("borrower_summary"), bank_result["borrower_summary"]),
    "facility_request": safe_text(app.get("facility_request"), bank_result["facility_request"]),
    "risk_assessment": safe_text(app.get("risk_assessment"), bank_result["risk_assessment"]),
    "decision_summary": safe_text(app.get("decision_summary"), bank_result["decision_summary"]),
    "ai_strengths": saved_strengths if saved_strengths else bank_result["ai_strengths"],
    "ai_risk_flags": saved_risks if saved_risks else bank_result["ai_risk_flags"],
    "ai_recommendation": safe_text(app.get("ai_recommendation"), bank_result["ai_recommendation"]),
}

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 📄 Application Details")
c1, c2 = st.columns(2)
c1.write(f"**Client Name:** {app['client_name']}")
c1.write(f"**Loan Amount:** {format_money(app.get('loan_amount'))}")
c1.write(f"**Tenor:** {app.get('tenor')} months")
c2.write(f"**Borrower Type:** {app.get('borrower_type')}")
c2.write(f"**Loan Purpose:** {app.get('loan_purpose')}")
c2.write(f"**Score:** {bank_result['credit_score']}/100")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 🏦 Bank-Grade Risk Metrics")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Credit Score", f"{bank_result['credit_score']}/100")
m2.metric("Risk Grade", bank_result["risk_grade"])
m3.metric("DSCR", f"{bank_result['dscr']:.2f}x")
m4.metric("Decision", bank_result["decision"])
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("## 🧾 Credit Assessment Memo")
st.markdown(
    f"""
**Borrower Summary**  
{memo['borrower_summary']}

**Facility Request**  
{memo['facility_request']}

**Risk Assessment**  
{memo['risk_assessment']}

**Decision Summary**  
{memo['decision_summary']}
"""
)
st.markdown("### ✅ Key Strengths")
for s in memo["ai_strengths"]:
    st.markdown(f"• {s}")
st.markdown("### ⚠️ Key Risks")
for r in memo["ai_risk_flags"]:
    st.markdown(f"• {r}")
st.markdown("### 📌 Recommendation")
st.markdown(memo["ai_recommendation"])
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### ✍️ Analyst Decision")
analyst_notes = st.text_area("Analyst Notes", value=existing_analyst_notes, key=f"analyst_notes_{app['id']}")
decision_note = st.text_area("Approval / Rejection Note", value=existing_decision_note, key=f"decision_note_{app['id']}")
if not is_pending_analyst_action:
    st.info("This application has already been reviewed at analyst stage. Saved data is shown for reference.")

col1, col2 = st.columns(2)
with col1:
    if st.button("Approve", disabled=not is_pending_analyst_action, key=f"approve_analyst_{app['id']}"):
        updated_history = app.get("approval_history") or []
        updated_history.append({"stage": role.upper(), "action": "APPROVED", "user": email, "timestamp": str(datetime.now()), "note": decision_note})
        payload = build_safe_update_payload(
            app,
            {
                "workflow_status": "ANALYST_APPROVED",
                "approval_history": updated_history,
                "analyst_notes": analyst_notes,
                "score": bank_result["credit_score"],
                "decision": bank_result["decision"],
                "credit_score": bank_result["credit_score"],
                "risk_grade": bank_result["risk_grade"],
                "risk_level": bank_result["risk_level"],
                "dscr": bank_result["dscr"],
                "borrower_summary": memo["borrower_summary"],
                "facility_request": memo["facility_request"],
                "risk_assessment": memo["risk_assessment"],
                "decision_summary": memo["decision_summary"],
                "ai_strengths": memo["ai_strengths"],
                "ai_risk_flags": memo["ai_risk_flags"],
                "ai_recommendation": memo["ai_recommendation"],
                "analyst_review_by": email,
                "analyst_review_at": str(datetime.now()),
            },
        )
        supabase.table("loan_applications").update(payload).eq("id", app["id"]).execute()
        st.session_state.last_viewed_app = app["id"]
        st.success("Approved successfully")
        st.rerun()
with col2:
    if st.button("Reject", disabled=not is_pending_analyst_action, key=f"reject_analyst_{app['id']}"):
        updated_history = app.get("approval_history") or []
        updated_history.append({"stage": role.upper(), "action": "REJECTED", "user": email, "timestamp": str(datetime.now()), "note": decision_note})
        payload = build_safe_update_payload(
            app,
            {
                "workflow_status": "ANALYST_REJECTED",
                "approval_history": updated_history,
                "analyst_notes": analyst_notes,
                "score": bank_result["credit_score"],
                "decision": bank_result["decision"],
                "credit_score": bank_result["credit_score"],
                "risk_grade": bank_result["risk_grade"],
                "risk_level": bank_result["risk_level"],
                "dscr": bank_result["dscr"],
                "borrower_summary": memo["borrower_summary"],
                "facility_request": memo["facility_request"],
                "risk_assessment": memo["risk_assessment"],
                "decision_summary": memo["decision_summary"],
                "ai_strengths": memo["ai_strengths"],
                "ai_risk_flags": memo["ai_risk_flags"],
                "ai_recommendation": memo["ai_recommendation"],
                "analyst_review_by": email,
                "analyst_review_at": str(datetime.now()),
            },
        )
        supabase.table("loan_applications").update(payload).eq("id", app["id"]).execute()
        st.session_state.last_viewed_app = app["id"]
        st.success("Rejected successfully")
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)
