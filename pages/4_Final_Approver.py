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
# FETCH PROFILE
# ===============================
resp = supabase.table("user_profiles").select("*").eq("id", user.id).execute()
profile = resp.data[0] if resp.data else {"role": "pending", "institution": ""}

role = (profile.get("role") or "").strip().lower()
institution = profile.get("institution") or ""

render_sidebar(role)

if role not in ["manager", "super_admin"]:
    st.error("Access denied")
    st.stop()

st.title("🏁 Credit Manager Desk")
st.caption(f"Institution: {institution}")

# ===============================
# LOAD APPLICATIONS
# ===============================
apps = supabase.table("loan_applications") \
    .select("*") \
    .eq("institution", institution) \
    .eq("workflow_status", "ANALYST_APPROVED") \
    .order("created_at", desc=True) \
    .execute().data

if not apps:
    st.info("No applications awaiting manager review.")
    st.stop()

# ===============================
# SELECT APPLICATION
# ===============================
app_options = {
    f"{a['client_name']} | ₦{a['loan_amount']:,.0f}": a["id"]
    for a in apps
}

selected = st.selectbox("Select Application", list(app_options.keys()))
selected_id = app_options[selected]

# 🔥 ALWAYS FETCH FRESH DATA (CRITICAL FIX)
app = supabase.table("loan_applications") \
    .select("*") \
    .eq("id", selected_id) \
    .single() \
    .execute().data

def safe(x):
    return x if x not in [None, "", "None"] else "—"

st.markdown("## 📄 Application Overview")
st.write(f"**Client:** {app['client_name']}")
st.write(f"**Amount:** ₦{app['loan_amount']:,.0f}")
st.write(f"**Purpose:** {app.get('loan_purpose')}")

st.markdown("---")

# ===============================
# CREDIT MEMO (FIXED)
# ===============================
st.markdown("## 🧾 Credit Assessment Memo")

st.markdown(f"""
**Borrower Summary**  
{safe(app.get("borrower_summary"))}

**Facility Request**  
{safe(app.get("facility_request"))}

**Risk Assessment**  
{safe(app.get("risk_assessment"))}

**Decision Summary**  
{safe(app.get("decision_summary"))}
""")

st.markdown("### ✅ Key Strengths")
for s in app.get("ai_strengths") or ["—"]:
    st.markdown(f"• {s}")

st.markdown("### ⚠️ Key Risks")
for r in app.get("ai_risk_flags") or ["—"]:
    st.markdown(f"• {r}")

st.markdown("### 📌 Recommendation")
st.markdown(safe(app.get("ai_recommendation")))

st.markdown("---")

# ===============================
# DECISION
# ===============================
note = st.text_area("Decision Note")

col1, col2 = st.columns(2)

with col1:
    if st.button("Approve"):
        supabase.table("loan_applications").update({
            "workflow_status": "MANAGER_APPROVED"
        }).eq("id", app["id"]).execute()
        st.success("Approved")
        st.rerun()

with col2:
    if st.button("Reject"):
        supabase.table("loan_applications").update({
            "workflow_status": "MANAGER_REJECTED"
        }).eq("id", app["id"]).execute()
        st.success("Rejected")
        st.rerun()