# Initiator page

import streamlit as st
from db.supabase_client import supabase
from workflow.sidebar_menu import render_sidebar
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
resp = supabase.table("user_profiles").select("*").eq("id", user.id).execute()
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

role = (profile.get("role") or "").strip().lower()
institution = profile.get("institution") or ""

render_sidebar(role)


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
    revenue = safe_float(record.get("revenue"))
    bank_inflow = safe_float(record.get("bank_inflow"))
    expenses = safe_float(record.get("monthly_expenses"))
    deductions = safe_float(record.get("deductions"))
    daily_sales = safe_float(record.get("daily_sales"))
    avg_balance = safe_float(record.get("avg_account_balance"))
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
    avg_balance = safe_float(record.get("avg_account_balance"))
    default_history = str(record.get("default_history") or "").strip().lower()
    years = safe_float(record.get("years"))
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
            "The facility is recommended for APPROVAL subject to standard documentation, drawdown conditions, and routine post-disbursement monitoring."
        )
    elif credit_score >= 65 and dscr >= 1.00:
        risk_grade = "B"
        risk_level = "Moderate Risk"
        decision = "APPROVE WITH CONDITIONS"
        recommendation = (
            "The facility is recommended for APPROVAL WITH CONDITIONS subject to verification of income/cash flow, perfection of collateral, and closer repayment monitoring."
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
            "The facility is recommended for REJECTION due to weak repayment capacity and/or insufficient risk mitigants relative to the proposed exposure."
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
        f"Estimated monthly net cash flow is {format_money(estimated_net_cash_flow)}. Existing outstanding obligations stand at {format_money(outstanding)} while cash reserve and average account balance stand at {format_money(cash_reserve)} and {format_money(avg_balance)} respectively."
    )
    risk_assessment = (
        f"The obligor is graded {risk_grade} ({risk_level}) with a credit score of {credit_score}/100 and DSCR of {dscr:.2f}x. Collateral cover is {collateral_cover:.2f}x. The assessment reflects repayment capacity, leverage, collateral support, liquidity profile, and credit history."
    )
    decision_summary = (
        f"Final recommendation is {decision}. The obligor is classified as Risk Grade {risk_grade} with a score of {credit_score}/100."
    )

    return {
        "credit_score": credit_score,
        "score": credit_score,
        "risk_grade": risk_grade,
        "risk_level": risk_level,
        "decision": decision,
        "dscr": round(dscr, 2),
        "collateral_cover": collateral_cover,
        "borrower_profile": borrower_profile,
        "facility_details": facility_details,
        "financial_summary": financial_summary,
        "risk_assessment": risk_assessment,
        "mitigants": unique_list(mitigants),
        "recommendation": recommendation,
        "borrower_summary": borrower_profile,
        "facility_request": facility_details,
        "decision_summary": decision_summary,
        "ai_strengths": unique_list(strengths) or ["No strong factors identified"],
        "ai_risk_flags": unique_list(risks) or ["No major risks identified"],
        "ai_recommendation": recommendation,
    }

st.title("📌 Loan Initiation Desk")
st.caption(f"Institution: {institution or 'Not set'}")

if not institution:
    st.warning("Your profile has no institution yet. The application can be saved, but it will not appear correctly for Analyst until your institution is set.")

st.markdown("## 🆕 Loan Application Details")
col1, col2 = st.columns(2)
client_name = col1.text_input("Client Name", value=st.session_state.get("client_name", ""), key="client_name")
borrower_type = col2.selectbox(
    "Borrower Type",
    ["Salary Earner", "SME", "Retail Business"],
    index=["Salary Earner", "SME", "Retail Business"].index(st.session_state.get("borrower_type", "Salary Earner")),
    key="borrower_type"
)

col3, col4 = st.columns(2)
loan_amount = col3.number_input("Requested Loan Amount", value=st.session_state.get("loan_amount", 500000.0), key="loan_amount")
tenor = col4.number_input("Tenor (Months)", value=st.session_state.get("tenor", 6), key="tenor")
loan_purpose = st.selectbox(
    "Loan Purpose",
    ["Working Capital", "Business Expansion", "Asset Purchase", "Personal Use"],
    index=["Working Capital", "Business Expansion", "Asset Purchase", "Personal Use"].index(st.session_state.get("loan_purpose", "Working Capital")),
    key="loan_purpose"
)

st.markdown("## 📊 Financial Information")
monthly_income = revenue = expenses = bank_inflow = daily_sales = deductions = years = 0.0
employment_type = ""

if borrower_type == "Salary Earner":
    employment_type = st.selectbox("Employment Type", ["Government/Public", "Private (Employee)", "Self-Employed"])
    c1, c2, c3 = st.columns(3)
    monthly_income = c1.number_input("Monthly Income", value=st.session_state.get("monthly_income", 200000.0), key="monthly_income")
    bank_inflow = c2.number_input("Average Bank Inflow", value=st.session_state.get("bank_inflow", 180000.0), key="bank_inflow")
    years = c3.number_input("Years in Role", value=st.session_state.get("years", 2.0), key="years")
    deductions = st.number_input("Existing Deductions", value=st.session_state.get("deductions", 50000.0), key="deductions")
elif borrower_type == "SME":
    c1, c2, c3 = st.columns(3)
    revenue = c1.number_input("Monthly Revenue", value=st.session_state.get("revenue", 2000000.0), key="revenue")
    bank_inflow = c2.number_input("Bank Inflow", value=st.session_state.get("bank_inflow", 1800000.0), key="bank_inflow")
    expenses = c3.number_input("Monthly Expenses", value=st.session_state.get("expenses", 1500000.0), key="expenses")
    years = st.number_input("Years in Business", value=st.session_state.get("years", 3.0), key="years")
else:
    c1, c2 = st.columns(2)
    daily_sales = c1.number_input("Daily Sales", value=st.session_state.get("daily_sales", 50000.0), key="daily_sales")
    expenses = c2.number_input("Monthly Expenses", value=st.session_state.get("expenses", 800000.0), key="expenses")
    years = st.number_input("Years in Business", value=st.session_state.get("years", 2.0), key="years")

st.markdown("## 📉 Debt & Credit Profile")
c1, c2, c3, c4 = st.columns(4)
total_outstanding_loans = c1.number_input("Total Outstanding Loans", value=st.session_state.get("total_loans", 200000.0), key="total_loans")
monthly_repayment = c2.number_input("Monthly Loan Repayment", value=st.session_state.get("monthly_repayment", 50000.0), key="monthly_repayment")
default_history = c3.selectbox("Past Default History", ["No", "Yes"], index=["No", "Yes"].index(st.session_state.get("default_history", "No")), key="default_history")
active_loans = c4.number_input("Number of Active Loans", value=st.session_state.get("active_loans", 1), key="active_loans")

st.markdown("## 🏦 Stability, Buffer & Support")
c1, c2, c3 = st.columns(3)
avg_account_balance = c1.number_input("Average Account Balance", value=st.session_state.get("avg_account_balance", 100000.0), key="avg_account_balance")
cash_reserve = c2.number_input("Cash / Savings Reserve", value=st.session_state.get("cash_reserve", 200000.0), key="cash_reserve")
location = c3.selectbox("Location", ["Urban", "Semi-Urban", "Rural"], index=["Urban", "Semi-Urban", "Rural"].index(st.session_state.get("location", "Urban")), key="location")
c4, c5 = st.columns(2)
collateral_type = c4.selectbox("Collateral Type", ["None", "Vehicle", "Property", "Equipment", "Inventory", "Guarantor"], index=["None", "Vehicle", "Property", "Equipment", "Inventory", "Guarantor"].index(st.session_state.get("collateral_type", "None")), key="collateral_type")
collateral_value = c5.number_input("Collateral Value", value=st.session_state.get("collateral_value", 0.0), key="collateral_value")

application_record = {
    "client_name": client_name,
    "borrower_type": borrower_type,
    "loan_amount": loan_amount,
    "tenor": tenor,
    "loan_purpose": loan_purpose,
    "monthly_income": monthly_income,
    "revenue": revenue,
    "monthly_expenses": expenses,
    "bank_inflow": bank_inflow,
    "daily_sales": daily_sales,
    "deductions": deductions,
    "years": years,
    "total_outstanding_loans": total_outstanding_loans,
    "monthly_repayment": monthly_repayment,
    "default_history": default_history,
    "active_loans": active_loans,
    "avg_account_balance": avg_account_balance,
    "cash_reserve": cash_reserve,
    "location": location,
    "employment_type": employment_type,
    "collateral_type": collateral_type,
    "collateral_value": collateral_value,
}

run_btn = st.button("Run AI Assessment", key="init_ai_btn")
if run_btn:
    bank_result = calculate_bank_grade(application_record)
    st.session_state.last_result = bank_result

if "last_result" in st.session_state:
    result = st.session_state.last_result
    st.success(
        f"Credit Score: {result['credit_score']}/100 | Risk Grade: {result['risk_grade']} | DSCR: {result['dscr']:.2f}x | Decision: {result['decision']}"
    )

    st.markdown("## 🏦 Bank-Grade Risk Metrics")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Credit Score", f"{result['credit_score']}/100")
    m2.metric("Risk Grade", result["risk_grade"])
    m3.metric("DSCR", f"{result['dscr']:.2f}x")
    m4.metric("Collateral Cover", f"{result['collateral_cover']:.2f}x")

    st.markdown("## 🤖 AI Credit Insight")
    st.markdown("### ✅ Key Strengths")
    for s in result.get("ai_strengths", []):
        st.markdown(f"• {s}")
    st.markdown("### ⚠️ Key Risks")
    for r in result.get("ai_risk_flags", []):
        st.markdown(f"• {r}")
    st.markdown("### 📌 AI Recommendation")
    st.write(result.get("ai_recommendation"))

    mitigants_html = "<br>".join([f"• {item}" for item in result.get("mitigants", [])])
    memo_html = f"""
<div style='border:1px solid #e6e6e6; border-radius:12px; padding:20px; background:#fafafa; line-height:1.8;'>
<b>Borrower Profile</b><br>
{result.get('borrower_profile')}<br><br>
<b>Facility Details</b><br>
{result.get('facility_details')}<br><br>
<b>Financial Summary</b><br>
{result.get('financial_summary')}<br><br>
<b>Risk Assessment</b><br>
{result.get('risk_assessment')}<br><br>
<b>Mitigating Factors</b><br>
{mitigants_html}<br><br>
<b>Recommendation</b><br>
<b>{result.get('recommendation')}</b>
</div>
"""
    st.markdown("## 🧾 Structured Credit Memo")
    st.markdown(memo_html, unsafe_allow_html=True)

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
            "score": result["credit_score"],
            "decision": result["decision"],
            "ai_recommendation": result.get("ai_recommendation"),
            "ai_strengths": result.get("ai_strengths"),
            "ai_risk_flags": result.get("ai_risk_flags"),
            "ai_narrative": f"Credit Score: {result['credit_score']}/100 | Risk Grade: {result['risk_grade']} | DSCR: {result['dscr']:.2f}x | Decision: {result['decision']}",
            "borrower_summary": result.get("borrower_summary"),
            "facility_request": result.get("facility_request"),
            "risk_assessment": result.get("risk_assessment"),
            "decision_summary": result.get("decision_summary"),
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
            "approval_history": [],
        }

        optional_payload = {
            "credit_score": result["credit_score"],
            "risk_grade": result["risk_grade"],
            "risk_level": result["risk_level"],
            "dscr": result["dscr"],
            "collateral_cover": result["collateral_cover"],
            "monthly_income": monthly_income,
            "revenue": revenue,
            "monthly_expenses": expenses,
            "bank_inflow": bank_inflow,
            "daily_sales": daily_sales,
            "deductions": deductions,
            "years": years,
            "employment_type": employment_type,
        }
        known_columns = get_known_application_columns()
        for key, value in optional_payload.items():
            if key in known_columns:
                payload[key] = value

        try:
            insert_resp = supabase.table("loan_applications").insert(payload).execute()
            if insert_resp.data:
                st.success("Application submitted successfully to Analyst.")
            else:
                st.warning("Submit action completed, but no record was returned. Please verify on Analyst page.")
        except Exception as e:
            st.error(f"Submission failed: {e}")

st.markdown("## 🔄 Returned Applications")
rejected = supabase.table("loan_applications").select("*").eq("initiated_by", user.id).execute().data or []
for r in rejected:
    if str(r.get("workflow_status") or "").endswith("REJECTED"):
        st.warning(f"{r['client_name']} → {r['workflow_status']}")

st.markdown("## 💰 Approved Loans")
approved = supabase.table("loan_applications").select("*").eq("initiated_by", user.id).eq("workflow_status", "FINAL_APPROVED").execute().data or []
for r in approved:
    st.success(f"{r['client_name']} → Approved")
    if st.button(f"🖨️ Generate Memo - {r['client_name']}", key=f"memo_btn_{r['id']}"):
        file_path = generate_credit_memo(r)
        with open(file_path, "rb") as f:
            st.download_button(
                label="Download Memo",
                data=f,
                file_name=f"{r['client_name']}_credit_memo.pdf",
                mime="application/pdf"
            )
