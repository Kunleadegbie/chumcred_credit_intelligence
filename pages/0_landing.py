import streamlit as st

# ===============================
# PAGE CONFIG
# ===============================
st.set_page_config(page_title="Chumcred AI", layout="wide")


# ===============================
# REMOVE DEFAULT SIDEBAR
# ===============================
st.markdown("""
<style>
[data-testid="stSidebar"] {display: none;}
[data-testid="stSidebarNav"] {display: none;}
.hero {
    background: linear-gradient(135deg, #1f3c88, #3f72af);
    padding: 60px;
    border-radius: 12px;
    color: white;
    text-align: center;
}
.feature-box {
    padding: 25px;
    border-radius: 10px;
    background-color: #f8f9fa;
    border: 1px solid #e6e6e6;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# ===============================
# HERO SECTION (NEXUS STYLE)
# ===============================
st.markdown("""
<div class="hero">
    <h1>🧠 Chumcred AI Credit Intelligence</h1>
    <p style="font-size:18px;">
    Transforming credit decisions with AI-powered insights, structured analysis, and automated workflows.
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ===============================
# FEATURES SECTION
# ===============================
st.markdown("## 🚀 What Chumcred AI Does")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="feature-box">
    <h4>🤖 AI Credit Scoring</h4>
    Automated borrower risk evaluation with intelligent decision support.
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="feature-box">
    <h4>📄 Credit Memo Automation</h4>
    Generate structured, bank-grade credit reports instantly.
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="feature-box">
    <h4>🔁 Workflow Automation</h4>
    Seamless multi-level approval system from Initiator to Final Approver.
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br><br>", unsafe_allow_html=True)

# ===============================
# TARGET USERS
# ===============================
st.markdown("## 👥 Who Is This For?")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    - Microfinance Banks  
    - Commercial Banks  
    - Fintech Credit Platforms  
    """)

with col2:
    st.markdown("""
    - Credit Analysts  
    - Risk Managers  
    - Loan Officers  
    """)

st.markdown("<br><br>", unsafe_allow_html=True)

# ===============================
# VALUE PROPOSITION
# ===============================
st.markdown("## 📈 Why Use Chumcred AI?")

st.markdown("""
✔ Improve credit decision accuracy  
✔ Reduce default risk  
✔ Standardize credit approval process  
✔ Gain full visibility into approval workflow  
✔ Scale credit operations efficiently  
""")

st.markdown("<br><br>", unsafe_allow_html=True)

# ===============================
# CTA SECTION
# ===============================
st.markdown("## 🎯 Get Started")

st.markdown("Click below to access your dashboard and begin credit assessment.")

if st.button("🚀 Go to Login"):
    st.session_state.go_to_login = True
    st.switch_page("app.py")