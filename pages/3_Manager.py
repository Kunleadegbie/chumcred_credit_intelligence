
import streamlit as st
from db.supabase_client import supabase
from workflow.sidebar_menu import render_sidebar
from institution_access import normalize_role, get_display_name, enforce_institution_access, build_actor_entry, render_history, get_stage_actor
from workflow.email_notifications import send_next_stage_notification, send_initiator_outcome

if "user" not in st.session_state:
    st.switch_page("app.py")

user = st.session_state.user
resp = supabase.table("user_profiles").select("*").eq("id", user.id).execute()
if resp.data:
    profile = resp.data[0]
else:
    profile = {"id": user.id, "email": getattr(user, "email", ""), "role": "pending", "institution": ""}
    supabase.table("user_profiles").insert(profile).execute()

role = normalize_role(profile.get("role"))
institution = profile.get("institution") or ""
email = profile.get("email") or getattr(user, "email", "") or ""
display_name = get_display_name(profile, user)

render_sidebar(role)
enforce_institution_access(profile, "page")

def allow(*allowed):
    allowed = [normalize_role(r) for r in allowed]
    return role in allowed or role == "super_admin"

if not allow("manager"):
    st.error("Access denied")
    st.stop()

st.title("🏁 Credit Manager Desk")
st.caption(f"Institution: {institution} | User: {display_name} | Email: {email} | Role: {role}")

all_applications = (
    supabase.table("loan_applications")
    .select("*")
    .eq("institution", institution)
    .order("created_at", desc=True)
    .execute().data or []
)

allowed_statuses = {
    "ANALYST_APPROVED", "MANAGER_APPROVED", "MANAGER_REJECTED", "MANAGER_POSTPONED",
    "FINAL_APPROVED", "FINAL_REJECTED", "FINAL_POSTPONED",
}
applications = [a for a in all_applications if str(a.get("workflow_status") or "").strip().upper() in allowed_statuses]

if not applications:
    st.info("No applications awaiting manager review.")
    st.stop()

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
app = supabase.table("loan_applications").select("*").eq("id", selected_id).single().execute().data

original_loan_amount = float(app.get("approved_amount") or app.get("recommended_amount") or app.get("loan_amount") or 0)
original_tenor = int(app.get("approved_tenor") or app.get("recommended_tenor") or app.get("tenor") or 1)

st.markdown("## ✏️ Facility Adjustment")
adj1, adj2 = st.columns(2)
with adj1:
    revised_loan_amount = st.number_input("Adjust Loan Amount", min_value=0.0, value=float(original_loan_amount), step=1000.0, key=f"manager_revised_loan_amount_{app['id']}")
with adj2:
    revised_tenor = st.number_input("Adjust Tenor (Months)", min_value=1, value=int(original_tenor), step=1, key=f"manager_revised_tenor_{app['id']}")

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

def safe_float(value, default=0.0):
    try:
        if value in [None, "", "None", "null"]:
            return float(default)
        return float(value)
    except Exception:
        return float(default)

def calculate_bank_grade_metrics(record):
    loan_amount = safe_float(record.get("recommended_amount") or record.get("approved_amount") or record.get("loan_amount"))
    monthly_repayment = safe_float(record.get("monthly_repayment"))
    collateral_value = safe_float(record.get("collateral_value"))
    cash_reserve = safe_float(record.get("cash_reserve"))
    avg_balance = safe_float(record.get("avg_account_balance") or record.get("average_balance"))
    income = safe_float(record.get("monthly_income") or record.get("revenue"))
    expenses = safe_float(record.get("monthly_expenses") or record.get("expenses"))
    available = max(income - expenses, 0.0)
    dscr = round(available / monthly_repayment, 2) if monthly_repayment > 0 else 0.0
    collateral_cover = round(collateral_value / loan_amount, 2) if loan_amount > 0 else 0.0
    score = int(float(record.get("credit_score") or record.get("score") or 0))
    risk_grade = "A" if score >= 80 else "B" if score >= 65 else "C"
    return {"credit_score": score, "risk_grade": risk_grade, "dscr": dscr, "collateral_cover": collateral_cover}

def get_canonical_metrics(record):
    metrics = calculate_bank_grade_metrics(record)
    stored_score = record.get("credit_score", record.get("score"))
    stored_grade = record.get("risk_grade")
    stored_dscr = record.get("dscr")
    stored_decision = record.get("decision")
    if stored_score not in [None, "", "None", "null"]:
        try:
            metrics["credit_score"] = int(float(stored_score))
        except Exception:
            pass
    if stored_grade not in [None, "", "None", "null"]:
        metrics["risk_grade"] = str(stored_grade).strip().upper()
    if stored_dscr not in [None, "", "None", "null"]:
        try:
            metrics["dscr"] = round(float(stored_dscr), 2)
        except Exception:
            pass
    if stored_decision not in [None, "", "None", "null"]:
        metrics["decision"] = str(stored_decision).strip()
    else:
        metrics["decision"] = "APPROVE" if metrics["risk_grade"] == "A" else "APPROVE WITH CONDITIONS" if metrics["risk_grade"] == "B" else "REJECT"
    return metrics

def generate_bank_grade_memo(record):
    name = record.get("client_name", "Borrower")
    loan_amount = float(record.get("approved_amount") or record.get("recommended_amount") or record.get("loan_amount") or 0)
    purpose = record.get("loan_purpose") or "business operations"
    tenor = record.get("approved_tenor") or record.get("recommended_tenor") or record.get("tenor") or 0
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

    decision = "APPROVE" if score >= 6 else "APPROVE WITH CONDITIONS" if score >= 3 else "REJECT"
    risk_level = "Low Risk" if score >= 6 else "Moderate Risk" if score >= 3 else "High Risk"

    borrower_summary = (
        f"{name} is requesting a loan facility to support {purpose}. "
        f"The borrower currently maintains outstanding obligations of ₦{outstanding:,.0f} "
        f"and a proposed monthly repayment obligation of ₦{repayment:,.0f}."
    )
    facility_request = f"A facility of ₦{loan_amount:,.0f} is requested for a tenor of {tenor} months to finance {purpose}."
    risk_assessment = (
        f"The facility is assessed as {risk_level}. The evaluation reflects the borrower’s "
        f"liquidity position, collateral adequacy, existing exposure profile, and credit history. "
        f"Collateral coverage stands at ₦{collateral:,.0f} while available liquidity buffer is "
        f"estimated at ₦{reserve:,.0f}."
    )
    decision_summary = f"Based on the overall credit assessment, the facility is recommended for {decision}."

    if decision == "APPROVE":
        recommendation = "The facility is recommended for APPROVAL without conditions."
    elif decision == "APPROVE WITH CONDITIONS":
        recommendation = """The facility is recommended for APPROVAL subject to:
• Verification of financial and operating records
• Ongoing monitoring of repayment performance
• Proper perfection of collateral documentation"""
    else:
        recommendation = "The facility is recommended for REJECTION due to weak credit fundamentals and an unfavorable risk-return profile."

    return {
        "borrower_summary": borrower_summary,
        "facility_request": facility_request,
        "risk_assessment": risk_assessment,
        "decision_summary": decision_summary,
        "ai_strengths": strengths if strengths else ["No strong factors identified"],
        "ai_risk_flags": risks if risks else ["No major risks identified"],
        "ai_recommendation": recommendation
    }

def build_consistent_manager_memo(record, metrics):
    risk_grade = str(metrics.get("risk_grade") or "C").strip().upper()
    risk_level = "Low Risk" if risk_grade == "A" else "Moderate Risk" if risk_grade == "B" else "High Risk"
    credit_score = int(metrics.get("credit_score") or record.get("credit_score") or record.get("score") or 0)
    dscr = float(metrics.get("dscr") or record.get("dscr") or 0)
    decision = str(metrics.get("decision") or record.get("decision") or "REJECT").strip()
    fallback = generate_bank_grade_memo(record)
    return {
        "borrower_summary": safe_text(record.get("borrower_summary"), fallback["borrower_summary"]),
        "facility_request": safe_text(record.get("facility_request"), fallback["facility_request"]),
        "risk_assessment": f"The obligor is graded {risk_grade} ({risk_level}) with a credit score of {credit_score}/100 and DSCR of {dscr:.2f}x.",
        "decision_summary": f"Final recommendation is {decision}.",
        "ai_strengths": clean_list(record.get("ai_strengths")) or fallback["ai_strengths"],
        "ai_risk_flags": clean_list(record.get("ai_risk_flags")) or fallback["ai_risk_flags"],
        "ai_recommendation": safe_text(record.get("ai_recommendation"), f"Facility recommendation: {decision}."),
    }

metrics = get_canonical_metrics(app)
memo = build_consistent_manager_memo(app, metrics)
history = app.get("approval_history") or []
existing_manager_notes = str(app.get("manager_notes") or "")
existing_decision_note = ""
for item in reversed(history):
    if str(item.get("stage", "")).upper() == role.upper():
        existing_decision_note = str(item.get("note", "") or "")
        break

is_pending_manager_action = str(app.get("workflow_status") or "").strip().upper() == "ANALYST_APPROVED"

st.markdown("## 📄 Application Overview")
col1, col2, col3 = st.columns(3)
col1.write(f"**Client Name:** {app['client_name']}")
col1.write(f"**Loan Amount:** {format_money(app.get('loan_amount'))}")
col1.write(f"**Tenor:** {app.get('tenor')} months")
col2.write(f"**Borrower Type:** {app.get('borrower_type')}")
col2.write(f"**Loan Purpose:** {app.get('loan_purpose')}")
col2.write(f"**Score:** {metrics.get('credit_score', app.get('score'))}/100")

st.markdown("---")
st.markdown("## 🏦 Bank-Grade Risk Metrics")
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
st.markdown(f'''
**Borrower Summary**  
{memo["borrower_summary"]}

**Facility Request**  
{memo["facility_request"]}

**Risk Assessment**  
{memo["risk_assessment"]}

**Decision Summary**  
{memo["decision_summary"]}
''')

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
decision_note = st.text_area("Approval / Rejection / Postpone Note", value=existing_decision_note, key=f"manager_note_{app['id']}")

if not is_pending_manager_action:
    st.info("This application has already been reviewed at manager stage. Saved data is shown for reference.")

act1, act2, act3 = st.columns(3)
common_payload = {
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
    "loan_amount": revised_loan_amount,
    "tenor": int(revised_tenor),
    "recommended_amount": revised_loan_amount,
    "recommended_tenor": int(revised_tenor),
}

with act1:
    if st.button("Approve", disabled=not is_pending_manager_action, key=f"approve_manager_{app['id']}"):
        updated_history = app.get("approval_history") or []
        updated_history.append(build_actor_entry(profile, user, role, "APPROVED", decision_note))
        payload = {
            **common_payload,
            "workflow_status": "MANAGER_APPROVED",
            "approval_history": updated_history,
            "decision": metrics.get("decision", app.get("decision")),
        }
        supabase.table("loan_applications").update(payload).eq("id", app["id"]).execute()
        send_next_stage_notification(institution, "manager", {**app, **payload}, display_name)
        st.session_state.last_viewed_app = app["id"]
        st.success("Approved successfully")
        st.rerun()

with act2:
    if st.button("Reject", disabled=not is_pending_manager_action, key=f"reject_manager_{app['id']}"):
        updated_history = app.get("approval_history") or []
        updated_history.append(build_actor_entry(profile, user, role, "REJECTED", decision_note))
        payload = {
            **common_payload,
            "workflow_status": "MANAGER_REJECTED",
            "approval_history": updated_history,
            "decision": "REJECTED",
        }
        supabase.table("loan_applications").update(payload).eq("id", app["id"]).execute()
        send_initiator_outcome({**app, **payload}, "Rejected by Manager")
        st.session_state.last_viewed_app = app["id"]
        st.success("Rejected successfully")
        st.rerun()

with act3:
    if st.button("Postpone", disabled=not is_pending_manager_action, key=f"postpone_manager_{app['id']}"):
        updated_history = app.get("approval_history") or []
        updated_history.append(build_actor_entry(profile, user, role, "POSTPONED", decision_note))
        payload = {
            **common_payload,
            "workflow_status": "MANAGER_POSTPONED",
            "approval_history": updated_history,
            "decision": "POSTPONED",
            "decision_summary": "Decision postponed pending additional review / documentation.",
            "ai_recommendation": "Postpone pending additional review / documentation.",
        }
        supabase.table("loan_applications").update(payload).eq("id", app["id"]).execute()
        send_initiator_outcome({**app, **payload}, "Postponed by Manager")
        st.session_state.last_viewed_app = app["id"]
        st.success("Postponed successfully")
        st.rerun()

st.markdown("---")
st.markdown("## 🔄 Workflow Trace")
st.write(f"**Initiated By:** {app.get('initiated_by_email') or app.get('initiated_by')}")
st.write(f"**Analyst:** {get_stage_actor(history, 'analyst')}")
st.write(f"**Manager:** {get_stage_actor(history, 'manager')}")
st.write(f"**Current Status:** {app.get('workflow_status')}")
