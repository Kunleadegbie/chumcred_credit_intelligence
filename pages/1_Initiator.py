import streamlit as st
from db.supabase_client import supabase
from workflow.sidebar_menu import render_sidebar
from institution_access import normalize_role, get_display_name, enforce_institution_access, build_actor_entry, render_history

from workflow.application_service import create_application
from ai_layer.ai_engine import run_ai_analysis
from utils.credit_memo import generate_credit_memo

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
email = profile.get("email") or ""
display_name = get_display_name(profile, user)


def get_known_application_columns():
    try:
        rows = supabase.table("loan_applications").select("*").limit(1).execute().data or []
        if rows:
            return set(rows[0].keys())
    except Exception:
        pass
    return set()


def build_professional_ai_fallback(ai_data, score_value, decision_value):
    borrower_type = ai_data.get("borrower_type", "Borrower")
    client_name = ai_data.get("client_name", "Borrower")
    loan_amount = float(ai_data.get("loan_amount", 0) or 0)
    tenor = ai_data.get("tenor", 0)
    purpose = ai_data.get("loan_purpose", "working capital")
    monthly_income = float(ai_data.get("monthly_income", 0) or 0)
    monthly_expenses = float(ai_data.get("monthly_expenses", 0) or 0)
    outstanding = float(ai_data.get("total_outstanding_loans", 0) or 0)
    monthly_repayment = float(ai_data.get("monthly_repayment", 0) or 0)
    cash_reserve = float(ai_data.get("cash_reserve", 0) or 0)
    avg_balance = float(ai_data.get("average_balance", 0) or 0)
    collateral_type = ai_data.get("collateral_type", "None")
    collateral_value = float(ai_data.get("collateral_value", 0) or 0)
    default_history = str(ai_data.get("default_history", "No") or "No")
    location = ai_data.get("location", "N/A")

    strengths = []
    risks = []
    mitigants = []

    if monthly_income > 0 and monthly_expenses >= 0:
        net_position = monthly_income - monthly_expenses
    else:
        net_position = 0

    if score_value >= 75:
        strengths.append("The applicant demonstrates an overall credit profile that falls within the approval range based on the submitted financial position.")
    elif score_value >= 50:
        strengths.append("The application shows moderate credit potential, but requires closer validation before a final lending decision is taken.")
    else:
        risks.append("The application currently falls below the internal approval comfort range and would require major risk mitigants before reconsideration.")

    if monthly_income > 0:
        strengths.append(f"Declared monthly income/cash generation of ₦{monthly_income:,.0f} provides a measurable source for repayment assessment.")
    if monthly_repayment > 0 and cash_reserve >= monthly_repayment:
        strengths.append("Cash reserve appears capable of providing short-term repayment support in the event of temporary income pressure.")
    if collateral_value > 0:
        strengths.append(f"Collateral support of ₦{collateral_value:,.0f} under {collateral_type} provides additional comfort to the proposed facility structure.")
    if default_history.strip().lower() in ["no", "none", "nil", "n/a", ""]:
        strengths.append("No prior default history was indicated in the submitted borrower profile.")
    else:
        risks.append("Declared adverse repayment/default history introduces elevated behavioral credit risk.")
    if outstanding > 0:
        risks.append(f"Existing obligations of ₦{outstanding:,.0f} should be considered in determining the borrower’s final debt service capacity.")
    if monthly_repayment > 0 and net_position > 0 and net_position < monthly_repayment:
        risks.append("Net operating/salary position appears tight relative to the proposed monthly repayment burden.")
    if collateral_value <= 0:
        risks.append("No meaningful collateral cover was indicated, which weakens recovery comfort in a default scenario.")
    if avg_balance > 0:
        strengths.append(f"Average account balance of ₦{avg_balance:,.0f} offers additional visibility into liquidity behavior.")
    if location:
        mitigants.append(f"Location risk context recorded as {location}.")
    if collateral_value > 0:
        mitigants.append("Collateral perfection and enforceability should be confirmed before drawdown.")
    mitigants.append("Independent verification of declared income/cash flow should be completed before final approval.")
    mitigants.append("Repayment performance should be monitored closely during the first repayment cycle.")

    risk_view = "favorable" if score_value >= 75 else "moderate" if score_value >= 50 else "weak"
    recommendation = (
        "Approve subject to standard documentation and verification."
        if decision_value == "APPROVE"
        else "Refer for enhanced review and supporting validation before approval."
        if decision_value == "REVIEW"
        else "Reject in current form pending stronger repayment support and mitigants."
    )

    return {
        "ai_strengths": strengths or ["The application contains some positive indicators but requires fuller validation."],
        "ai_risk_flags": risks or ["No major risk flags were captured from the submitted information."],
        "ai_recommendation": recommendation,
        "borrower_profile": f"{client_name} is presented as a {borrower_type} requesting a facility of ₦{loan_amount:,.0f} for {purpose} over {tenor} months.",
        "facility_details": f"The proposed exposure is ₦{loan_amount:,.0f} for {tenor} months, with stated purpose as {purpose}. Existing obligations and repayment burden should be assessed against verified affordability.",
        "financial_summary": f"Submitted financial indicators show monthly income/cash generation of ₦{monthly_income:,.0f}, monthly expenses of ₦{monthly_expenses:,.0f}, current obligations of ₦{outstanding:,.0f}, monthly repayment of ₦{monthly_repayment:,.0f}, cash reserve of ₦{cash_reserve:,.0f}, and average balance of ₦{avg_balance:,.0f}.",
        "risk_assessment": f"Based on the submitted data, the application currently presents a {risk_view} risk outlook with internal score of {score_value}. Final decision quality depends on verification of income quality, leverage position, repayment behavior, and available credit support.",
        "mitigants": " ".join([f"• {m}" for m in mitigants]),
        "recommendation": recommendation,
        "ai_narrative": f"Internal score outcome is {score_value} with preliminary decision of {decision_value}. The case should be judged on verified repayment capacity, outstanding leverage, liquidity support, behavioral history, and collateral comfort."
    }

# ===============================
# SIDEBAR
# ===============================
render_sidebar(role)
enforce_institution_access(profile, "initiator page")

# ===============================
# ACCESS CONTROL HELPER
# ===============================
def allow(*allowed):
    allowed = [r.lower() for r in allowed]
    return role in allowed or role == "super_admin"

st.title("📌 Loan Initiation Desk")
st.caption(f"Institution: {institution or 'Not set'} | User: {display_name} | Email: {email} | Role: {role}")

# =========================================================
# SECTION 1 — LOAN APPLICATION DETAILS
# =========================================================
st.markdown("## 🆕 Loan Application Details")

col1, col2 = st.columns(2)
client_name = col1.text_input(
    "Client Name",
    value=st.session_state.get("client_name", ""),
    key="client_name"
)

borrower_type = col2.selectbox(
    "Borrower Type",
    ["Salary Earner", "SME", "Retail Business"],
    index=["Salary Earner", "SME", "Retail Business"].index(
        st.session_state.get("borrower_type", "Salary Earner")
    ),
    key="borrower_type"
)    

col3, col4 = st.columns(2)
loan_amount = col3.number_input(
    "Requested Loan Amount",
    value=st.session_state.get("loan_amount", 500000.0),
    key="loan_amount"
)

tenor = col4.number_input(
    "Tenor (Months)",
    value=st.session_state.get("tenor", 6),
    key="tenor"
)

loan_purpose = st.selectbox(
    "Loan Purpose",
    ["Working Capital", "Business Expansion", "Asset Purchase", "Personal Use"],
    index=["Working Capital", "Business Expansion", "Asset Purchase", "Personal Use"].index(
        st.session_state.get("loan_purpose", "Working Capital")
    ),
    key="loan_purpose"
)

# =========================================================
# SECTION 2 — FINANCIAL INFORMATION
# =========================================================
st.markdown("## 📊 Financial Information")

monthly_income = None
revenue = None
expenses = 0.0

if borrower_type == "Salary Earner":

    employment_type = st.selectbox(
        "Employment Type",
        ["Government/Public", "Private (Employee)", "Self-Employed"]
    )

    col1, col2, col3 = st.columns(3)
    monthly_income = col1.number_input(
        "Monthly Income",
        value=st.session_state.get("monthly_income", 200000.0),
        key="monthly_income"
    )
    bank_inflow = col2.number_input("Average Bank Inflow", value=180000.0)
    years = col3.number_input("Years in Role", value=2)

    deductions = st.number_input("Existing Deductions", value=50000.0)

    score = 75 if monthly_income > 150000 else 55

elif borrower_type == "SME":
    expenses = col3.number_input(
        "Monthly Expenses",
        value=st.session_state.get("expenses", 1500000.0),
        key="expenses"
    )

    col1, col2, col3 = st.columns(3)
    revenue = col1.number_input("Monthly Revenue", value=2000000.0)
    inflow = col2.number_input("Bank Inflow", value=1800000.0)
    expenses = col3.number_input("Monthly Expenses", value=1500000.0)

    years = st.number_input("Years in Business", value=3)

    score = 80 if revenue - expenses > 300000 else 60

else:

    col1, col2 = st.columns(2)
    daily_sales = col1.number_input("Daily Sales", value=50000.0)
    expenses = col2.number_input(
        "Monthly Expenses",
        value=st.session_state.get("expenses", 800000.0),
        key="expenses"
    )

    score = 65 if daily_sales > 30000 else 50

decision = "APPROVE" if score >= 75 else "REVIEW" if score >= 50 else "REJECT"

# =========================================================
# SECTION 3 — DEBT & CREDIT PROFILE
# =========================================================
st.markdown("## 📉 Debt & Credit Profile")

col1, col2, col3, col4 = st.columns(4)

total_outstanding_loans = col1.number_input(
    "Total Outstanding Loans",
    value=st.session_state.get("total_loans", 200000.0),
    key="total_loans"
)

monthly_repayment = col2.number_input(
    "Monthly Loan Repayment",
    value=st.session_state.get("monthly_repayment", 50000.0),
    key="monthly_repayment"
)
default_history = col3.selectbox("Past Default History", ["No", "Yes"])
active_loans = col4.number_input("Number of Active Loans", value=1)

# =========================================================
# SECTION 4 — STABILITY, BUFFER & SUPPORT
# =========================================================
st.markdown("## 🏦 Stability, Buffer & Support")

col1, col2, col3 = st.columns(3)

avg_account_balance = col1.number_input("Average Account Balance", value=100000.0)
cash_reserve = col2.number_input(
    "Cash / Savings Reserve",
    value=st.session_state.get("cash_reserve", 200000.0),
    key="cash_reserve"
)

location = col3.selectbox("Location", ["Urban", "Semi-Urban", "Rural"])

col4, col5 = st.columns(2)
collateral_type = col4.selectbox(
    "Collateral Type",
    ["None", "Vehicle", "Property", "Equipment", "Inventory", "Guarantor"]
)
collateral_value = col5.number_input(
    "Collateral Value",
    value=st.session_state.get("collateral_value", 0.0),
    key="collateral_value"
)

# =========================================================
# AI ASSESSMENT
# =========================================================
run_btn = st.button("Run AI Assessment", key="init_ai_btn")

if run_btn:

    ai_data = {
        "client_name": client_name,
        "loan_amount": loan_amount,
        "tenor": tenor,
        "loan_purpose": loan_purpose,
        "borrower_type": borrower_type,

        "monthly_income": monthly_income or 0,
        "monthly_expenses": expenses or 0,

        "total_outstanding_loans": total_outstanding_loans,
        "monthly_repayment": monthly_repayment,
        "default_history": default_history,
        "active_loans": active_loans,

        "cash_reserve": cash_reserve,
        "average_balance": avg_account_balance,
        "location": location,

        "collateral_type": collateral_type,
        "collateral_value": collateral_value
    }

    # ✅ RUN AI
    ai_result = run_ai_analysis(ai_data, score, decision) or {}
    fallback_ai = build_professional_ai_fallback(ai_data, score, decision)

    merged_ai = dict(fallback_ai)
    for key, value in (ai_result or {}).items():
        if key in ["ai_strengths", "ai_risk_flags"]:
            if value:
                merged_ai[key] = value
        else:
            if value not in [None, "", [], {}]:
                merged_ai[key] = value

    # ✅ STORE RESULT
    st.session_state.last_result = {
        "score": score,
        "decision": decision,
        "ai": merged_ai
    }
    
if "last_result" in st.session_state:

    result = st.session_state.last_result
    ai = result["ai"]

    st.success(f"Score: {result['score']} | Decision: {result['decision']}")

    st.markdown("## 🤖 AI Credit Insight")

    st.markdown("### ✅ Key Strengths")
    for s in (ai.get("ai_strengths") or ["No key strengths returned yet."]):
        st.markdown(f"• {s}")

    st.markdown("### ⚠️ Key Risks")
    for r in (ai.get("ai_risk_flags") or ["No key risks returned yet."]):
        st.markdown(f"• {r}")

    st.markdown("### 📌 AI Recommendation")
    st.write(ai.get("ai_recommendation") or ai.get("recommendation") or "No recommendation available.")

    st.markdown("### 🧾 Credit Narrative")

    st.markdown("## 🧾 Structured Credit Memo")

    st.markdown(f"""
    <div style="
    border:1px solid #e6e6e6;
    border-radius:10px;
    padding:20px;
    background:#fafafa;
    line-height:1.8;
    ">

    <b>Borrower Profile</b><br>
    {ai.get("borrower_profile") or "N/A"}<br><br>

    <b>Facility Details</b><br>
    {ai.get("facility_details") or "N/A"}<br><br>

    <b>Financial Summary</b><br>
    {ai.get("financial_summary") or "N/A"}<br><br>

    <b>Risk Assessment</b><br>
    {ai.get("risk_assessment") or "N/A"}<br><br>

    <b>Mitigating Factors</b><br>
    {ai.get("mitigants") or "N/A"}<br><br>

    <b>Recommendation</b><br>
    <b>{ai.get("recommendation") or ai.get("ai_recommendation") or "N/A"}</b>

    </div>
    """, unsafe_allow_html=True)

   
# =========================================================
# SUBMIT TO WORKFLOW
# =========================================================
if "last_result" in st.session_state:

    if st.button("Submit Application", key="submit_init"):

        result = st.session_state.last_result

        payload = {
            "institution": institution,
            "client_name": client_name,
            "borrower_type": borrower_type,
            "loan_amount": loan_amount,
            "tenor": tenor,
            "loan_purpose": loan_purpose,

            "score": result["score"],
            "decision": result["decision"],
            "ai_recommendation": result["ai"].get("ai_recommendation"),
            "ai_strengths": result["ai"].get("ai_strengths"),
            "ai_risk_flags": result["ai"].get("ai_risk_flags"),
            "ai_narrative": result["ai"].get("ai_narrative"),

            "total_outstanding_loans": total_outstanding_loans,
            "monthly_repayment": monthly_repayment,
            "default_history": default_history,
            "active_loans": active_loans,

            "avg_account_balance": avg_account_balance,
            "cash_reserve": cash_reserve,
            "location": location,
            "collateral_type": collateral_type,
            "collateral_value": collateral_value,

            "workflow_status": "SUBMITTED",
            "initiated_by": user.id,
            "approval_history": [build_actor_entry(profile, user, "initiator", "SUBMITTED", "Application submitted")]
        }

        known_columns = get_known_application_columns()
        if "initiated_by_email" in known_columns:
            payload["initiated_by_email"] = email
        if "initiated_by_name" in known_columns:
            payload["initiated_by_name"] = display_name

        create_application(payload)
        st.success("Submitted to Analyst")

        st.session_state.last_result = result
        st.session_state.show_result = True

# =========================================================
# APPLICATION FEEDBACK & DECISIONS
# =========================================================
st.markdown("## 📂 Application Decisions")

all_my_apps = supabase.table("loan_applications")     .select("*")     .eq("initiated_by", user.id)     .order("created_at", desc=True)     .execute().data or []

# =========================================================
# REJECTED / RETURNED APPLICATIONS (DROPDOWN)
# =========================================================
st.markdown("### 🔄 Rejected / Returned Applications")

rejected_statuses = {"ANALYST_REJECTED", "MANAGER_REJECTED", "FINAL_REJECTED"}
rejected = [r for r in all_my_apps if (r.get("workflow_status") or "") in rejected_statuses]

if not rejected:
    st.info("No rejected or returned applications yet.")
else:
    rejected_map = {
        f"{r.get('client_name', 'Unknown')} | ₦{float(r.get('loan_amount', 0) or 0):,.0f} | {r.get('workflow_status', 'REJECTED')}": r
        for r in rejected
    }
    rejected_label = st.selectbox(
        "Select Rejected Application",
        list(rejected_map.keys()),
        key="initiator_rejected_dropdown"
    )
    rejected_app = rejected_map[rejected_label]

    st.warning(f"{rejected_app.get('client_name')} → {rejected_app.get('workflow_status')}")

    rejection_history = rejected_app.get("approval_history") or []
    if rejection_history:
        st.markdown("**Rejection / Feedback Trail**")
        render_history(rejection_history)

    primary_reason = ""
    for item in reversed(rejection_history):
        action = str(item.get("action", "")).upper()
        if "REJECT" in action:
            primary_reason = str(item.get("note", "") or "").strip()
            if primary_reason:
                break

    if primary_reason:
        st.markdown(f"**Primary Rejection Reason:** {primary_reason}")

    extra_feedback = []
    for field_name, label in [
        ("analyst_notes", "Analyst Notes"),
        ("manager_notes", "Manager Notes"),
        ("final_notes", "Final Approval Notes"),
    ]:
        value = str(rejected_app.get(field_name) or "").strip()
        if value:
            extra_feedback.append((label, value))

    if extra_feedback:
        st.markdown("**Additional Feedback**")
        for label, value in extra_feedback:
            st.markdown(f"**{label}:** {value}")

# =========================================================
# APPROVED APPLICATIONS (DROPDOWN)
# =========================================================
st.markdown("### 💰 Approved Applications")

approved = [r for r in all_my_apps if (r.get("workflow_status") or "") == "FINAL_APPROVED"]

if not approved:
    st.info("No approved applications available yet.")
else:
    approved_map = {
        f"{r.get('client_name', 'Unknown')} | ₦{float(r.get('loan_amount', 0) or 0):,.0f} | Score {r.get('score', 'N/A')}": r
        for r in approved
    }
    approved_label = st.selectbox(
        "Select Approved Application",
        list(approved_map.keys()),
        key="initiator_approved_dropdown"
    )
    approved_app = approved_map[approved_label]

    st.success(f"{approved_app.get('client_name')} → Approved")
    st.markdown(
        f"**Score:** {approved_app.get('score', 'N/A')}  \
"
        f"**Decision:** {approved_app.get('decision', 'APPROVED')}  \
"
        f"**Status:** {approved_app.get('workflow_status')}"
    )

    approved_history = approved_app.get("approval_history") or []
    if approved_history:
        st.markdown("**Approval Trail**")
        render_history(approved_history)

    if st.button(
        f"🖨️ Generate Memo - {approved_app.get('client_name')}",
        key=f"memo_btn_{approved_app.get('id')}"
    ):
        file_path = generate_credit_memo(approved_app)

        with open(file_path, "rb") as f:
            st.download_button(
                label="Download Memo",
                data=f,
                file_name=f"{approved_app.get('client_name')}_credit_memo.pdf",
                mime="application/pdf",
                key=f"download_memo_{approved_app.get('id')}"
            )
