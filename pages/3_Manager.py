
# Manager page

import streamlit as st
from db.supabase_client import supabase
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
        lower = text.lower()
        if lower not in seen:
            seen.add(lower)
            output.append(text)
    return output

def get_latest_stage_note(history_items, stage_name):
    for item in reversed(history_items or []):
        if str(item.get("stage", "")).upper() == str(stage_name).upper():
            note = str(item.get("note", "") or "").strip()
            if note:
                return note
    return ""

def split_final_history_note(note_text):
    text = str(note_text or "").strip()
    if not text.startswith("Final Approval Notes:"):
        return "", text

    if "\n\nDecision Note:" in text:
        first_part, second_part = text.split("\n\nDecision Note:", 1)
        parsed_final_notes = first_part.replace("Final Approval Notes:", "", 1).strip()
        parsed_decision_note = second_part.strip()
        return parsed_final_notes, parsed_decision_note

    parsed_final_notes = text.replace("Final Approval Notes:", "", 1).strip()
    return parsed_final_notes, ""

def build_safe_update_payload(existing_record, payload):
    return {key: value for key, value in payload.items() if key in (existing_record or {})}

def get_known_application_columns():
    try:
        rows = supabase.table("loan_applications").select("*").limit(1).execute().data or []
        if rows:
            return set(rows[0].keys())
    except Exception:
        pass
    return set()

def estimate_monthly_net_cash_flow(record):
    borrower_type = str(record.get("borrower_type") or "").strip().lower()

    monthly_income = safe_float(record.get("monthly_income"))
    revenue = safe_float(record.get("revenue") or record.get("monthly_revenue"))
    bank_inflow = safe_float(record.get("bank_inflow") or record.get("average_bank_inflow") or record.get("inflow"))
    expenses = safe_float(record.get("monthly_expenses") or record.get("expenses"))
    deductions = safe_float(record.get("deductions") or record.get("existing_deductions"))
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
        fallback_cash_flow = max((cash_reserve * 0.20), (avg_balance * 0.35), (loan_amount / tenor) * 1.10, 0.0)
        net_cash_flow = fallback_cash_flow

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
    years = safe_float(
        record.get("years")
        or record.get("years_in_business")
        or record.get("years_in_role")
    )
    employment_type = str(record.get("employment_type") or "").strip()
    location = str(record.get("location") or "").strip()

    estimated_net_cash_flow, gross_cash_flow = estimate_monthly_net_cash_flow(record)
    dscr = 9.99 if monthly_repayment <= 0 else round(estimated_net_cash_flow / monthly_repayment, 2)
    collateral_cover = 0.0 if loan_amount <= 0 else round(collateral_value / loan_amount, 2)
    liquidity_ratio = 9.99 if monthly_repayment <= 0 else round((cash_reserve + avg_balance) / monthly_repayment, 2)

    score = 0
    strengths = []
    risks = []
    mitigants = []

    # Repayment Capacity - 35
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

    # Collateral Support - 20
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

    # Liquidity - 15
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

    # Existing Exposure - 10
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

    # Credit History - 10
    if default_history in ["no", "none", "", "nil", "n/a"]:
        score += 10
        strengths.append("No prior default history observed")
    else:
        risks.append("Adverse credit history/default flag detected")

    # Stability - 5
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

    # Account Conduct / Behaviour - 5
    if gross_cash_flow > 0 and avg_balance >= (gross_cash_flow * 0.15):
        score += 5
        strengths.append("Average account balance supports stable account conduct")
    elif avg_balance >= monthly_repayment and monthly_repayment > 0:
        score += 4
        strengths.append("Account balance trend offers some comfort for repayment")
    elif cash_reserve > 0:
        score += 3
        mitigants.append("Available cash reserve provides partial comfort")
    else:
        score += 1
        risks.append("Average balance profile is weak relative to the facility size")

    credit_score = int(max(0, min(round(score), 100)))

    if credit_score >= 80 and dscr >= 1.25 and default_history in ["no", "none", "", "nil", "n/a"]:
        risk_grade = "A"
        risk_level = "Low Risk"
        decision = "APPROVE"
        recommendation = (
            "The facility is recommended for APPROVAL subject to standard documentation, "
            "drawdown conditions, and routine post-disbursement monitoring."
        )
    elif credit_score >= 65 and dscr >= 1.00:
        risk_grade = "B"
        risk_level = "Moderate Risk"
        decision = "APPROVE WITH CONDITIONS"
        recommendation = (
            "The facility is recommended for APPROVAL WITH CONDITIONS subject to verification "
            "of income/cash flow, perfection of collateral, and closer repayment monitoring."
        )
        mitigants.extend([
            "Verify recent cash-flow or salary evidence before drawdown",
            "Perfect collateral and supporting legal documentation",
            "Place account turnover and repayment monitoring on watchlist for first 3 months",
        ])
    else:
        risk_grade = "C"
        risk_level = "High Risk"
        decision = "REJECT"
        recommendation = (
            "The facility is recommended for REJECTION due to weak repayment capacity and/or "
            "insufficient risk mitigants relative to the proposed exposure."
        )
        mitigants.append("Consider restructuring facility size, tenor, or collateral support before reconsideration")

    if employment_type:
        mitigants.append(f"Employment/Business classification noted: {employment_type}")
    if location:
        mitigants.append(f"Location factor captured as {location}")

    borrower_profile = (
        f"{name} is a {borrower_type.lower()} requesting credit support for {purpose}. "
        f"The proposed facility amount is {format_money(loan_amount)} for a tenor of {tenor} months."
    )

    facility_details = (
        f"Requested facility: {format_money(loan_amount)} over {tenor} months for {purpose}. "
        f"Monthly debt service obligation is estimated at {format_money(monthly_repayment)}."
    )

    financial_summary = (
        f"Estimated monthly net cash flow is {format_money(estimated_net_cash_flow)}. "
        f"Existing outstanding obligations stand at {format_money(outstanding)} while "
        f"cash reserve and average account balance stand at {format_money(cash_reserve)} "
        f"and {format_money(avg_balance)} respectively."
    )

    risk_assessment = (
        f"The obligor is graded {risk_grade} ({risk_level}) with a credit score of "
        f"{credit_score}/100 and DSCR of {dscr:.2f}x. Collateral cover is {collateral_cover:.2f}x. "
        f"The assessment reflects repayment capacity, leverage, collateral support, "
        f"liquidity profile, and credit history."
    )

    borrower_summary = borrower_profile
    facility_request = facility_details
    decision_summary = (
        f"Final recommendation is {decision}. The obligor is classified as Risk Grade {risk_grade} "
        f"with a score of {credit_score}/100."
    )

    if not mitigants:
        mitigants = ["Standard documentation and post-disbursement monitoring will apply"]

    return {
        "credit_score": credit_score,
        "score": credit_score,
        "risk_grade": risk_grade,
        "risk_level": risk_level,
        "decision": decision,
        "dscr": round(dscr, 2),
        "collateral_cover": collateral_cover,
        "liquidity_ratio": liquidity_ratio,
        "estimated_net_cash_flow": round(estimated_net_cash_flow, 2),
        "borrower_profile": borrower_profile,
        "facility_details": facility_details,
        "financial_summary": financial_summary,
        "risk_assessment": risk_assessment,
        "mitigants": "\n".join([f"• {item}" for item in unique_list(mitigants)]),
        "recommendation": recommendation,
        "borrower_summary": borrower_summary,
        "facility_request": facility_request,
        "decision_summary": decision_summary,
        "ai_strengths": unique_list(strengths) or ["No strong factors identified"],
        "ai_risk_flags": unique_list(risks) or ["No major risks identified"],
        "ai_recommendation": recommendation,
    }

def merge_ai_result(bank_result, external_ai=None):
    external_ai = external_ai or {}

    merged_strengths = unique_list(
        list(bank_result.get("ai_strengths", [])) +
        list(external_ai.get("ai_strengths", []))
    )
    merged_risks = unique_list(
        list(bank_result.get("ai_risk_flags", [])) +
        list(external_ai.get("ai_risk_flags", []))
    )

    return {
        "borrower_profile": bank_result.get("borrower_profile"),
        "facility_details": bank_result.get("facility_details"),
        "financial_summary": bank_result.get("financial_summary"),
        "risk_assessment": bank_result.get("risk_assessment"),
        "mitigants": bank_result.get("mitigants"),
        "recommendation": bank_result.get("recommendation"),
        "ai_strengths": merged_strengths or ["No strong factors identified"],
        "ai_risk_flags": merged_risks or ["No major risks identified"],
        "ai_recommendation": bank_result.get("ai_recommendation"),
        "ai_narrative": (
            f"Credit Score: {bank_result.get('credit_score')}/100 | "
            f"Risk Grade: {bank_result.get('risk_grade')} | "
            f"DSCR: {bank_result.get('dscr'):.2f}x | "
            f"Decision: {bank_result.get('decision')}"
        ),
        "borrower_summary": bank_result.get("borrower_summary"),
        "facility_request": bank_result.get("facility_request"),
        "decision_summary": bank_result.get("decision_summary"),
    }


st.title("🏁 Credit Manager Desk")
st.caption(f"Institution: {institution}")

# =========================================================
# LOAD APPLICATIONS
# Pending manager reviews + manager-reviewed records retained
# =========================================================
all_applications = supabase.table("loan_applications") \
    .select("*") \
    .eq("institution", institution) \
    .order("created_at", desc=True) \
    .execute().data or []

allowed_statuses = {
    "ANALYST_APPROVED",
    "MANAGER_APPROVED",
    "MANAGER_REJECTED",
    "FINAL_APPROVED",
    "FINAL_REJECTED",
}

applications = [
    a for a in all_applications
    if (a.get("workflow_status") or "") in allowed_statuses
]

if not applications:
    st.info("No applications awaiting manager review.")
    st.stop()

# =========================================================
# SELECT APPLICATION
# =========================================================
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

# ALWAYS FETCH FRESH RECORD
app_resp = supabase.table("loan_applications") \
    .select("*") \
    .eq("id", selected_id) \
    .single() \
    .execute()

app = app_resp.data
bank_result = calculate_bank_grade(app)

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
        "ai_strengths": saved_strengths if saved_strengths else bank_result["ai_strengths"],
        "ai_risk_flags": saved_risks if saved_risks else bank_result["ai_risk_flags"],
        "ai_recommendation": safe_text(app.get("ai_recommendation"), bank_result["ai_recommendation"])
    }
else:
    memo = {
        "borrower_summary": bank_result["borrower_summary"],
        "facility_request": bank_result["facility_request"],
        "risk_assessment": bank_result["risk_assessment"],
        "decision_summary": bank_result["decision_summary"],
        "ai_strengths": bank_result["ai_strengths"],
        "ai_risk_flags": bank_result["ai_risk_flags"],
        "ai_recommendation": bank_result["ai_recommendation"]
    }

silent_update_payload = build_safe_update_payload(app, {
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
})
try:
    if silent_update_payload:
        supabase.table("loan_applications").update(silent_update_payload).eq("id", app["id"]).execute()
except Exception:
    pass

# =========================================================
# APPLICATION DETAILS (READ ONLY)
# =========================================================
st.markdown("## 📄 Application Overview")

col1, col2 = st.columns(2)

col1.write(f"**Client Name:** {app['client_name']}")
col1.write(f"**Loan Amount:** {format_money(app.get('loan_amount'))}")
col1.write(f"**Tenor:** {app.get('tenor')} months")

col2.write(f"**Borrower Type:** {app.get('borrower_type')}")
col2.write(f"**Loan Purpose:** {app.get('loan_purpose')}")
col2.write(f"**Score:** {bank_result['credit_score']}/100")

st.markdown("---")

# =========================================================
# FINANCIAL SUMMARY
# =========================================================
st.markdown("## 📊 Financial Summary")

st.write(f"**Outstanding Loans:** {format_money(app.get('total_outstanding_loans'))}")
st.write(f"**Monthly Repayment:** {format_money(app.get('monthly_repayment'))}")
st.write(f"**Default History:** {app.get('default_history')}")

st.markdown("---")

# =========================================================
# COLLATERAL & BUFFER
# =========================================================
st.markdown("## 🏦 Collateral & Buffer")

st.write(f"**Collateral Type:** {app.get('collateral_type')}")
st.write(f"**Collateral Value:** {format_money(app.get('collateral_value'))}")
st.write(f"**Cash Reserve:** {format_money(app.get('cash_reserve'))}")

st.markdown("---")

# =========================================================
# BANK-GRADE RISK METRICS
# =========================================================
st.markdown("## 🏦 Bank-Grade Risk Metrics")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Credit Score", f"{bank_result['credit_score']}/100")
m2.metric("Risk Grade", bank_result["risk_grade"])
m3.metric("DSCR", f"{bank_result['dscr']:.2f}x")
m4.metric("Decision", bank_result["decision"])

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

existing_manager_notes = str(app.get("manager_notes") or "")
existing_decision_note = get_latest_stage_note(history, role.upper())
is_pending_manager_action = (app.get("workflow_status") or "") == "ANALYST_APPROVED"

manager_notes = st.text_area(
    "Manager Notes",
    value=existing_manager_notes,
    key=f"manager_notes_{app['id']}"
)
decision_note = st.text_area(
    "Approval / Rejection Note",
    value=existing_decision_note,
    key=f"manager_note_{app['id']}"
)

if not is_pending_manager_action:
    st.info("This application has already been reviewed at manager stage. Saved data is shown for reference.")

col1, col2 = st.columns(2)

with col1:
    if st.button("Approve", disabled=not is_pending_manager_action, key=f"approve_manager_{app['id']}"):
        updated_history = app.get("approval_history") or []
        updated_history.append({
            "stage": role.upper(),
            "action": "APPROVED",
            "user": user.id,
            "timestamp": str(datetime.now()),
            "note": decision_note
        })

        update_payload = build_safe_update_payload(app, {
            "workflow_status": "MANAGER_APPROVED",
            "approval_history": updated_history,
            "manager_notes": manager_notes,
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
            "manager_review_by": user.id,
            "manager_review_at": str(datetime.now())
        })

        supabase.table("loan_applications") \
            .update(update_payload) \
            .eq("id", app["id"]) \
            .execute()

        st.session_state.last_viewed_app = app["id"]
        st.success("Approved successfully")
        st.rerun()

with col2:
    if st.button("Reject", disabled=not is_pending_manager_action, key=f"reject_manager_{app['id']}"):
        updated_history = app.get("approval_history") or []
        updated_history.append({
            "stage": role.upper(),
            "action": "REJECTED",
            "user": user.id,
            "timestamp": str(datetime.now()),
            "note": decision_note
        })

        update_payload = build_safe_update_payload(app, {
            "workflow_status": "MANAGER_REJECTED",
            "approval_history": updated_history,
            "manager_notes": manager_notes,
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
            "manager_review_by": user.id,
            "manager_review_at": str(datetime.now())
        })

        supabase.table("loan_applications") \
            .update(update_payload) \
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

st.write(f"**Initiated By:** {app.get('initiated_by')}")
st.write(f"**Analyst:** {app.get('analyst_review_by')}")
st.write(f"**Current Status:** {app.get('workflow_status')}")
