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

if not allow("analyst", "credit_analyst"):
    st.error("Access denied")
    st.stop()

# ===============================
# STYLE
# ===============================
st.markdown("""
<style>
.card {background-color:#fff;padding:20px;border-radius:12px;border:1px solid #e6e6e6;margin-bottom:15px;}
.header-card {background:linear-gradient(135deg,#1f3c88,#3f72af);padding:25px;border-radius:12px;color:white;}
</style>
""", unsafe_allow_html=True)


# (ONLY THE FIXED SECTION — REST OF YOUR FILE REMAINS SAME)

# ===============================
# LOAD APPLICATIONS
# ===============================
response = supabase.table("loan_applications") \
    .select("*") \
    .execute()

applications = response.data or []

# ===============================
# SELECT APPLICATION (FIXED)
# ===============================
app_options = {
    f"{a.get('client_name','Unknown')} - ₦{a.get('loan_amount',0):,.0f}": a["id"]
    for a in applications
}

selected_label = st.selectbox("Select Application", list(app_options.keys()))

selected_id = app_options[selected_label]

# ===============================
# FETCH FULL RECORD (CRITICAL FIX)
# ===============================
app_resp = supabase.table("loan_applications") \
    .select("*") \
    .eq("id", selected_id) \
    .single() \
    .execute()

app = app_resp.data

# 🔥 KEEP LAST VIEWED LOGIC (UNCHANGED)
if "last_viewed_app" in st.session_state:

    last_id = st.session_state.last_viewed_app

    result = supabase.table("loan_applications") \
        .select("*") \
        .eq("id", last_id) \
        .execute().data

    if result:
        app = result[0]

# =========================================================
# APPLICATION DETAILS
# =========================================================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 📄 Application Details")

col1, col2 = st.columns(2)

col1.write(f"**Client Name:** {app['client_name']}")
col1.write(f"**Loan Amount:** ₦{app['loan_amount']:,.0f}")
col1.write(f"**Tenor:** {app.get('tenor')} months")

col2.write(f"**Borrower Type:** {app.get('borrower_type')}")
col2.write(f"**Loan Purpose:** {app.get('loan_purpose')}")
col2.write(f"**Score:** {app.get('score')}")

st.markdown("---")
st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# FINANCIAL SNAPSHOT
# =========================================================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 📊 Financial Snapshot")

st.write(f"**Outstanding Loans:** ₦{app.get('total_outstanding_loans', 0):,.0f}")
st.write(f"**Monthly Repayment:** ₦{app.get('monthly_repayment', 0):,.0f}")
st.write(f"**Default History:** {app.get('default_history')}")

st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# COLLATERAL
# =========================================================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 🏦 Collateral & Buffer")

st.write(f"**Collateral Type:** {app.get('collateral_type')}")
st.write(f"**Collateral Value:** ₦{app.get('collateral_value', 0):,.0f}")
st.write(f"**Cash Reserve:** ₦{app.get('cash_reserve', 0):,.0f}")

st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# AI INSIGHT (SCORING MODEL - BANK STANDARD)
# =========================================================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("## 🤖 AI Credit Insight")

def generate_bank_grade_memo(app):

    name = app.get("client_name", "Borrower")
    loan_amount = app.get("loan_amount", 0)
    purpose = app.get("loan_purpose", "")
    tenor = app.get("tenor", 0)

    repayment = app.get("monthly_repayment", 0)
    reserve = app.get("cash_reserve", 0)
    outstanding = app.get("total_outstanding_loans", 0)
    collateral = app.get("collateral_value", 0)
    default_history = str(app.get("default_history", "")).lower()

    # ===============================
    # CREDIT SCORING MODEL
    # ===============================
    score = 0
    strengths = []
    risks = []

    # --- Cash Flow Strength ---
    if reserve > repayment * 3:
        score += 3
        strengths.append("Strong liquidity buffer relative to repayment obligations")
    elif reserve > repayment:
        score += 2
        strengths.append("Moderate liquidity support for repayment")
    else:
        risks.append("Weak liquidity position relative to repayment burden")

    # --- Collateral Strength ---
    if collateral >= loan_amount:
        score += 3
        strengths.append("Fully secured facility with adequate collateral coverage")
    elif collateral >= 0.5 * loan_amount:
        score += 2
        strengths.append("Partial collateral support available")
    else:
        risks.append("Insufficient collateral coverage")

    # --- Credit History ---
    if default_history in ["none", "", "no"]:
        score += 2
        strengths.append("No prior default history observed")
    else:
        score -= 2
        risks.append("Adverse credit history detected")

    # --- Existing Exposure ---
    if outstanding < loan_amount:
        score += 1
        strengths.append("Manageable existing debt exposure")
    else:
        risks.append("High existing financial obligations")

    # ===============================
    # FINAL DECISION
    # ===============================
    if score >= 6:
        decision = "APPROVE"
        risk_level = "Low Risk"

    elif score >= 3:
        decision = "APPROVE WITH CONDITIONS"
        risk_level = "Moderate Risk"

    else:
        decision = "REJECT"
        risk_level = "High Risk"

    # ===============================
    # BUILD MEMO
    # ===============================
    memo = {
        "borrower_summary":
            f"{name} is requesting a loan facility to finance {purpose}. "
            f"The borrower currently maintains outstanding obligations of ₦{outstanding:,.0f} "
            f"with a proposed monthly repayment of ₦{repayment:,.0f}.",

        "facility_request":
            f"A facility of ₦{loan_amount:,.0f} is requested for a tenor of {tenor} months "
            f"to support {purpose}.",

        "risk_assessment":
            f"The facility is assessed as {risk_level}. "
            f"The evaluation is based on liquidity position, collateral adequacy, "
            f"existing exposure, and credit history.",

        "decision_summary":
            f"Based on the overall credit assessment, the facility is recommended for {decision}.",

        "key_strength": "\n".join([f"• {s}" for s in strengths]) if strengths else "• No strong factors identified",

        "key_risk": "\n".join([f"• {r}" for r in risks]) if risks else "• No major risks identified",

        "recommendation":
            (
                f"The facility is recommended for APPROVAL without conditions."
                if decision == "APPROVE"
                else
                f"The facility is recommended for APPROVAL subject to:\n"
                f"• Verification of income and financial records\n"
                f"• Monitoring of repayment performance\n"
                f"• Proper collateral documentation"
                if decision == "APPROVE WITH CONDITIONS"
                else
                f"The facility is recommended for REJECTION due to weak credit fundamentals."
            )
    }

    return memo


# ===============================
# GENERATE MEMO
# ===============================
memo = generate_bank_grade_memo(app)

# ===============================
# SAVE TO DATABASE
# ===============================
try:
    supabase.table("loan_applications").update({
        "borrower_summary": memo["borrower_summary"],
        "facility_request": memo["facility_request"],
        "risk_assessment": memo["risk_assessment"],
        "decision_summary": memo["decision_summary"],
        "ai_strengths": memo["key_strength"].split("\n"),
        "ai_risk_flags": memo["key_risk"].split("\n"),
        "ai_recommendation": memo["recommendation"]
    }).eq("id", app["id"]).execute()
except:
    pass

# ===============================
# DISPLAY MEMO
# ===============================
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
for s in memo["key_strength"].split("\n"):
    st.markdown(s)

st.markdown("### ⚠️ Key Risks")
for r in memo["key_risk"].split("\n"):
    st.markdown(r)

st.markdown("### 📌 Recommendation")
st.markdown(memo["recommendation"])

st.markdown('</div>', unsafe_allow_html=True)

# ===============================
# GENERATE MEMO
# ===============================
memo = generate_bank_grade_memo(app)

# ===============================
# SAVE TO DATABASE (CRITICAL FIX)
# ===============================
supabase.table("loan_applications").update({
    "borrower_summary": memo["borrower_summary"],
    "facility_request": memo["facility_request"],
    "risk_assessment": memo["risk_assessment"],
    "decision_summary": memo["decision_summary"],
    "ai_strengths": memo["key_strength"].split("\n"),
    "ai_risk_flags": memo["key_risk"].split("\n"),
    "ai_recommendation": memo["recommendation"]
}).eq("id", app["id"]).execute()

# ===============================
# DISPLAY MEMO (BANK STANDARD)
# ===============================
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
{memo["borrower_summary"]}

<br><br>

<b>Facility Request</b><br>
{memo["facility_request"]}

<br><br>

<b>Risk Assessment</b><br><br>
<p style="text-align:justify; margin:0;">
{memo["risk_assessment"]}
</p>

<br><br>

<b>Decision Summary</b><br>
{memo["decision_summary"]}

</div>
""",
    unsafe_allow_html=True
)

# ===============================
# KEY INSIGHTS (NOW FIXED)
# ===============================
st.markdown("### ✅ Key Strengths")
for s in memo["key_strength"].split("\n"):
    st.markdown(s)

st.markdown("### ⚠️ Key Risks")
for r in memo["key_risk"].split("\n"):
    st.markdown(r)

st.markdown("### 📌 Recommendation")
st.markdown(memo["recommendation"])

st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# APPROVAL HISTORY
# =========================================================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 🧾 Approval History")

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

st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# ANALYST DECISION
# =========================================================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### ✍️ Analyst Decision")

analyst_notes = st.text_area("Analyst Notes")

decision_note = st.text_area(
    "Approval / Rejection Note",
    key="decision_note"
)

col1, col2 = st.columns(2)

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
                "workflow_status": "ANALYST_APPROVED",
                "approval_history": history
            }) \
            .eq("id", app["id"]) \
            .execute()

        st.session_state.last_viewed_app = app["id"]
        st.success("Approved successfully")

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
                "workflow_status": "ANALYST_REJECTED",
                "approval_history": history
            }) \
            .eq("id", app["id"]) \
            .execute()

        st.session_state.last_viewed_app = app["id"]
        st.success("Rejected successfully")

st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# HISTORY
# =========================================================
st.markdown("---")
st.markdown("## 🧾 Workflow History")

st.write(f"**Initiated By:** {app.get('initiated_by')}")
st.write(f"**Current Status:** {app.get('workflow_status')}")