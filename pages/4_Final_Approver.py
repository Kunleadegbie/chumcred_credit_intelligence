
import streamlit as st
from db.supabase_client import supabase
from workflow.sidebar_menu import render_sidebar
from institution_access import normalize_role, get_display_name, enforce_institution_access, build_actor_entry, render_history, get_stage_actor
from workflow.email_notifications import send_initiator_outcome

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
    allowed = [r.lower() for r in allowed]
    return role in allowed or role == "super_admin"

if not allow("final_approver"):
    st.error("Access denied")
    st.stop()

st.title("🏛️ Final Credit Authority")
st.caption(f"Institution: {institution} | User: {display_name} | Email: {email} | Role: {role}")

def is_final_queue_candidate(record):
    status = str(record.get("workflow_status") or "").strip().upper()
    if status in {"MANAGER_APPROVED", "FINAL_APPROVED", "FINAL_REJECTED", "FINAL_POSTPONED"}:
        return True
    history = record.get("approval_history") or []
    latest_manager_approval = False
    latest_final_action = False
    for item in reversed(history):
        stage = str(item.get("stage") or "").strip().upper()
        action = str(item.get("action") or "").strip().upper()
        if not latest_final_action and stage in {"FINAL_APPROVER", "FINAL_APPROVAL"} and action in {"APPROVED", "REJECTED", "POSTPONED"}:
            latest_final_action = True
        if stage == "MANAGER":
            if action == "APPROVED":
                latest_manager_approval = True
            break
    return latest_manager_approval or latest_final_action

all_applications = supabase.table("loan_applications").select("*").eq("institution", institution).order("created_at", desc=True).execute().data or []
applications = [a for a in all_applications if is_final_queue_candidate(a)]

if not applications:
    st.info("No applications awaiting final approval.")
    st.stop()

def format_money(value):
    try:
        return f"₦{float(value or 0):,.0f}"
    except Exception:
        return "₦0"

app_map = {
    f"{a['client_name']} | {format_money(a.get('loan_amount'))} | Score {a.get('score', 0)} | {a.get('workflow_status', 'UNKNOWN')}": a["id"]
    for a in applications
}
labels = list(app_map.keys())
default_index = 0
last_viewed_app = st.session_state.get("last_viewed_app")
if last_viewed_app:
    for idx, label in enumerate(labels):
        if app_map[label] == last_viewed_app:
            default_index = idx
            break

selected_label = st.selectbox("Select Application", labels, index=default_index)
selected_id = app_map[selected_label]
app = supabase.table("loan_applications").select("*").eq("id", selected_id).single().execute().data

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
    loan_amount = safe_float(record.get("approved_amount") or record.get("recommended_amount") or record.get("loan_amount"))
    monthly_repayment = safe_float(record.get("monthly_repayment"))
    collateral_value = safe_float(record.get("collateral_value"))
    cash_reserve = safe_float(record.get("cash_reserve"))
    avg_balance = safe_float(record.get("avg_account_balance") or record.get("average_balance"))
    income = safe_float(record.get("monthly_income") or record.get("revenue"))
    expenses = safe_float(record.get("monthly_expenses") or record.get("expenses"))
    available = max(income - expenses, 0)
    computed_dscr = round(available / monthly_repayment, 2) if monthly_repayment > 0 else 0.0
    collateral_cover = round(collateral_value / loan_amount, 2) if loan_amount > 0 else 0.0

    stored_score = record.get("credit_score", record.get("score"))
    stored_grade = record.get("risk_grade")
    stored_dscr = record.get("dscr")
    score = int(float(stored_score or 0))
    dscr = round(float(stored_dscr), 2) if stored_dscr not in [None, "", "None", "null"] else computed_dscr
    risk_grade = str(stored_grade).strip().upper() if stored_grade not in [None, "", "None", "null"] else ("A" if score >= 80 else "B" if score >= 65 else "C")
    return {"credit_score": score, "risk_grade": risk_grade, "dscr": dscr, "collateral_cover": collateral_cover}

def build_professional_final_memo(record):
    name = record.get("client_name", "Borrower")
    borrower_type = record.get("borrower_type", "Borrower")
    purpose = record.get("loan_purpose", "business operations")
    loan_amount = float(record.get("approved_amount") or record.get("recommended_amount") or record.get("loan_amount") or 0)
    tenor = int(record.get("approved_tenor") or record.get("recommended_tenor") or record.get("tenor") or 0)
    outstanding = float(record.get("total_outstanding_loans", 0) or 0)
    monthly_repayment = float(record.get("monthly_repayment", 0) or 0)
    cash_reserve = float(record.get("cash_reserve", 0) or 0)
    collateral_type = record.get("collateral_type", "None")
    collateral_value = float(record.get("collateral_value", 0) or 0)
    metrics = calculate_bank_grade_metrics(record)
    recommendation = "Approve subject to standard documentation and final verification." if metrics["risk_grade"] in ["A", "B"] else "Reject or return for stronger risk support and verification."
    return {
        "borrower_summary": f"{name} is presented as a {borrower_type} borrower requesting a facility of ₦{loan_amount:,.0f} for {purpose} over {tenor} months.",
        "facility_request": f"The proposed facility request is ₦{loan_amount:,.0f} for a tenor of {tenor} months. Existing obligations and proposed debt service should be viewed against verified repayment capacity.",
        "risk_assessment": f"The application carries an internal score of {metrics['credit_score']}/100, risk grade {metrics['risk_grade']}, DSCR of {metrics['dscr']:.2f}x, and collateral cover of {metrics['collateral_cover']:.2f}x. This assessment reflects leverage, repayment pressure, liquidity buffer, and available collateral support.",
        "decision_summary": f"At final approval stage, the case should be judged against verified affordability, existing leverage of ₦{outstanding:,.0f}, monthly repayment burden of ₦{monthly_repayment:,.0f}, cash reserve of ₦{cash_reserve:,.0f}, and collateral support under {collateral_type} valued at ₦{collateral_value:,.0f}.",
        "ai_strengths": ["The application has progressed through prior approval stages and contains decision-chain context for final review.", f"Collateral support of ₦{collateral_value:,.0f} provides additional comfort where enforceability is confirmed." if collateral_value > 0 else "No strong collateral support was provided."],
        "ai_risk_flags": [f"Existing obligations of ₦{outstanding:,.0f} should be weighed against the final repayment structure.", "Final approval should be subject to complete document verification and consistency of borrower disclosures."],
        "ai_recommendation": recommendation
    }

metrics = calculate_bank_grade_metrics(app)
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
    prof = build_professional_final_memo(app)
    memo = {
        "borrower_summary": safe_text(app.get("borrower_summary"), prof["borrower_summary"]),
        "facility_request": safe_text(app.get("facility_request"), prof["facility_request"]),
        "risk_assessment": safe_text(app.get("risk_assessment"), prof["risk_assessment"]),
        "decision_summary": safe_text(app.get("decision_summary"), prof["decision_summary"]),
        "ai_strengths": saved_strengths if saved_strengths else prof["ai_strengths"],
        "ai_risk_flags": saved_risks if saved_risks else prof["ai_risk_flags"],
        "ai_recommendation": safe_text(app.get("ai_recommendation"), prof["ai_recommendation"])
    }
else:
    memo = build_professional_final_memo(app)

st.markdown("## 📄 Executive Summary")
col1, col2, col3 = st.columns(3)
col1.write(f"**Client Name:** {app['client_name']}")
col1.write(f"**Loan Amount:** {format_money(app.get('loan_amount'))}")
col1.write(f"**Tenor:** {app.get('tenor')} months")
col2.write(f"**Borrower Type:** {app.get('borrower_type')}")
col2.write(f"**Loan Purpose:** {app.get('loan_purpose')}")
col2.write(f"**Score:** {app.get('score')}")

st.markdown("---")
st.markdown("## 🏦 Bank-Grade Risk Metrics")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Credit Score", f"{metrics.get('credit_score', app.get('score', 0))}/100")
m2.metric("Risk Grade", metrics.get("risk_grade", "N/A"))
m3.metric("DSCR", f"{metrics.get('dscr', 0):.2f}x")
m4.metric("Collateral Cover", f"{metrics.get('collateral_cover', 0):.2f}x")

st.markdown("---")
st.markdown("## ⚠️ Risk & Financial Position")
st.write(f"**Outstanding Loans:** {format_money(app.get('total_outstanding_loans'))}")
st.write(f"**Monthly Repayment:** {format_money(app.get('monthly_repayment'))}")
st.write(f"**Default History:** {app.get('default_history')}")

st.markdown("---")
st.markdown("## 🏦 Collateral & Support")
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

st.markdown("## 🧾 Decision Chain")
st.write(f"**Analyst Notes:** {app.get('analyst_notes', 'N/A')}")
st.write(f"**Manager Notes:** {app.get('manager_notes', 'N/A')}")

st.markdown("---")
st.markdown("## 🧾 Approval History")
history = app.get("approval_history") or []
render_history(history)

st.markdown("## 🏁 Final Decision")
existing_final_notes = str(app.get("final_notes") or "")
existing_decision_note = ""
history = app.get("approval_history") or []
for item in reversed(history):
    if str(item.get("stage", "")).upper() == role.upper():
        existing_decision_note = str(item.get("note", "") or "")
        break

is_pending_final_action = str(app.get("workflow_status") or "").strip().upper() == "MANAGER_APPROVED"
final_notes = st.text_area("Final Approval Notes", value=existing_final_notes)
decision_note = st.text_area("Approval / Rejection / Postpone Note", value=existing_decision_note, key=f"final_note_{app['id']}")

st.markdown("### ✏️ Superior Officer Adjustment")
adj1, adj2 = st.columns(2)
revised_loan_amount = adj1.number_input("Final Approved / Recommended Loan Amount", min_value=0.0, value=float(app.get("approved_amount") or app.get("recommended_amount") or app.get("loan_amount") or 0), key=f"final_revised_amount_{app['id']}")
revised_tenor = adj2.number_input("Final Approved / Recommended Tenor (Months)", min_value=1, value=int(app.get("approved_tenor") or app.get("recommended_tenor") or app.get("tenor") or 1), key=f"final_revised_tenor_{app['id']}")

if not is_pending_final_action:
    st.info("This application has already been reviewed at final approval stage. Saved data is shown for reference.")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Approve", disabled=not is_pending_final_action, key=f"approve_final_{app['id']}"):
        history = app.get("approval_history") or []
        approval_entry = build_actor_entry(profile, user, role, "APPROVED", decision_note)
        if isinstance(approval_entry, dict):
            approval_entry["user"] = email
        history.append(approval_entry)
        payload = {
            "workflow_status": "FINAL_APPROVED",
            "approval_history": history,
            "final_notes": final_notes,
            "score": metrics.get("credit_score", app.get("score")),
            "credit_score": metrics.get("credit_score", app.get("credit_score")),
            "risk_grade": metrics.get("risk_grade", app.get("risk_grade")),
            "dscr": metrics.get("dscr", app.get("dscr")),
            "decision": "APPROVED",
            "loan_amount": revised_loan_amount,
            "tenor": int(revised_tenor),
            "approved_amount": revised_loan_amount,
            "approved_tenor": int(revised_tenor)
        }
        supabase.table("loan_applications").update(payload).eq("id", app["id"]).execute()
        send_initiator_outcome({**app, **payload}, "Approved")
        st.session_state.last_viewed_app = app["id"]
        st.success("Approved successfully")
        st.rerun()

with col2:
    if st.button("Reject", disabled=not is_pending_final_action, key=f"reject_final_{app['id']}"):
        history = app.get("approval_history") or []
        rejection_entry = build_actor_entry(profile, user, role, "REJECTED", decision_note)
        if isinstance(rejection_entry, dict):
            rejection_entry["user"] = email
        history.append(rejection_entry)
        payload = {
            "workflow_status": "FINAL_REJECTED",
            "approval_history": history,
            "final_notes": final_notes,
            "score": metrics.get("credit_score", app.get("score")),
            "credit_score": metrics.get("credit_score", app.get("credit_score")),
            "risk_grade": metrics.get("risk_grade", app.get("risk_grade")),
            "dscr": metrics.get("dscr", app.get("dscr")),
            "decision": "REJECTED",
            "loan_amount": revised_loan_amount,
            "tenor": int(revised_tenor),
            "approved_amount": revised_loan_amount,
            "approved_tenor": int(revised_tenor)
        }
        supabase.table("loan_applications").update(payload).eq("id", app["id"]).execute()
        send_initiator_outcome({**app, **payload}, "Rejected")
        st.session_state.last_viewed_app = app["id"]
        st.success("Rejected successfully")
        st.rerun()

with col3:
    if st.button("Postpone", disabled=not is_pending_final_action, key=f"postpone_final_{app['id']}"):
        history = app.get("approval_history") or []
        postpone_entry = build_actor_entry(profile, user, role, "POSTPONED", decision_note)
        if isinstance(postpone_entry, dict):
            postpone_entry["user"] = email
        history.append(postpone_entry)
        payload = {
            "workflow_status": "FINAL_POSTPONED",
            "approval_history": history,
            "final_notes": final_notes,
            "score": metrics.get("credit_score", app.get("score")),
            "credit_score": metrics.get("credit_score", app.get("credit_score")),
            "risk_grade": metrics.get("risk_grade", app.get("risk_grade")),
            "dscr": metrics.get("dscr", app.get("dscr")),
            "decision": "POSTPONED",
            "loan_amount": revised_loan_amount,
            "tenor": int(revised_tenor),
            "approved_amount": revised_loan_amount,
            "approved_tenor": int(revised_tenor)
        }
        supabase.table("loan_applications").update(payload).eq("id", app["id"]).execute()
        send_initiator_outcome({**app, **payload}, "Postponed / Put on Hold")
        st.session_state.last_viewed_app = app["id"]
        st.success("Postponed successfully")
        st.rerun()

st.markdown("---")
st.markdown("## 🔄 Workflow Trace")
st.write(f"**Initiated By:** {app.get('initiated_by_email') or get_stage_actor(history, 'initiator')}")
st.write(f"**Analyst:** {get_stage_actor(history, 'analyst')}")
st.write(f"**Manager:** {get_stage_actor(history, 'manager')}")
st.write(f"**Current Status:** {app.get('workflow_status')}")
