import streamlit as st
from db.supabase_client import supabase
from workflow.sidebar_menu import render_sidebar

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
role = (profile.get("role") or "").strip().lower()
institution = profile.get("institution") or ""
email = profile.get("email") or ""

# ===============================
# SIDEBAR
# ===============================
render_sidebar(role)

# ===============================
# ACCESS CONTROL HELPER
# ===============================
def allow(*allowed):
    allowed = [r.lower() for r in allowed]
    return role in allowed or role == "super_admin"

st.title("📌 Loan Initiation Desk")

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
    ai_result = run_ai_analysis(ai_data, score, decision)

    # ✅ STORE RESULT

    st.session_state.last_result = {
        "score": score,
        "decision": decision,
        "ai": ai_result
    }
    
if "last_result" in st.session_state:

    result = st.session_state.last_result
    ai = result["ai"]

    st.success(f"Score: {result['score']} | Decision: {result['decision']}")

    st.markdown("## 🤖 AI Credit Insight")

    st.markdown("### ✅ Key Strengths")
    for s in ai.get("ai_strengths", []):
        st.markdown(f"• {s}")

    st.markdown("### ⚠️ Key Risks")
    for r in ai.get("ai_risk_flags", []):
        st.markdown(f"• {r}")

    st.markdown("### 📌 AI Recommendation")
    st.write(ai.get("ai_recommendation"))

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
            "initiated_by": user.id
        }

        create_application(payload)
        st.success("Submitted to Analyst")

        st.session_state.last_result = result
        st.session_state.show_result = True

# =========================================================
# REJECTED APPLICATIONS
# =========================================================
st.markdown("## 🔄 Returned Applications")

rejected = supabase.table("loan_applications") \
    .select("*") \
    .eq("initiated_by", user.id) \
    .like("workflow_status", "REJECTED%") \
    .execute().data

for r in rejected:
    st.warning(f"{r['client_name']} → {r['workflow_status']}")

# =========================================================
# APPROVED APPLICATIONS (DISBURSEMENT)
# =========================================================
st.markdown("## 💰 Approved Loans")

approved = supabase.table("loan_applications") \
    .select("*") \
    .eq("initiated_by", user.id) \
    .eq("workflow_status", "FINAL_APPROVED") \
    .execute().data

for r in approved:
    st.success(f"{r['client_name']} → Approved")

    if st.button(
        f"🖨️ Generate Memo - {r['client_name']}",
        key=f"memo_btn_{r['id']}"
    ):

        file_path = generate_credit_memo(r)

        with open(file_path, "rb") as f:
            st.download_button(
                label="Download Memo",
                data=f,
                file_name=f"{r['client_name']}_credit_memo.pdf",
                mime="application/pdf"
            )

    