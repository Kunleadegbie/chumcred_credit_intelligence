from ml.early_warning import calculate_ews

def calculate_ews(data):

    risk_score = 0
    flags = []

    income = data.get("monthly_income") or data.get("monthly_revenue") or 0
    repayment = data.get("monthly_repayment") or 0
    reserve = data.get("cash_reserve") or 0
    days_past_due = data.get("days_past_due") or 0
    default_history = data.get("default_history")

    # ===============================
    # 1. PAYMENT STRESS
    # ===============================
    if income > 0:
        dti = repayment / income
    else:
        dti = 1

    if dti > 0.5:
        risk_score += 30
        flags.append("High repayment burden")

    # ===============================
    # 2. EARLY DELINQUENCY SIGNAL
    # ===============================
    if days_past_due > 30:
        risk_score += 40
        flags.append("Payment delay > 30 days")
    elif days_past_due > 0:
        risk_score += 20
        flags.append("Recent payment delay")

    # ===============================
    # 3. LOW LIQUIDITY
    # ===============================
    if reserve < 50000:
        risk_score += 20
        flags.append("Low cash reserve")

    # ===============================
    # 4. CREDIT HISTORY
    # ===============================
    if default_history == "Yes":
        risk_score += 20
        flags.append("Past default history")

    # ===============================
    # RISK LEVEL
    # ===============================
    if risk_score >= 60:
        level = "RED"
    elif risk_score >= 30:
        level = "AMBER"
    else:
        level = "GREEN"

    return {
        "ews_score": risk_score,
        "risk_level": level,
        "flags": flags
    }

df["ews"] = df.apply(lambda row: calculate_ews(row), axis=1)

df["ews_score"] = df["ews"].apply(lambda x: x["ews_score"])
df["ews_level"] = df["ews"].apply(lambda x: x["risk_level"])


st.markdown("## 🚨 Early Warning Signals")

st.bar_chart(df["ews_level"].value_counts())

st.markdown("### 🔴 High Risk Loans")

high_risk = df[df["ews_level"] == "RED"]

st.dataframe(high_risk[[
    "client_name",
    "loan_amount",
    "ews_score",
    "workflow_status"
]])

st.markdown("### ⚠️ Risk Drivers")

for _, row in high_risk.iterrows():
    st.write(f"**{row['client_name']}**")
    for f in row["ews"]["flags"]:
        st.markdown(f"• {f}")

ews = calculate_ews(app)

st.write(f"Risk Level: {ews['risk_level']}")