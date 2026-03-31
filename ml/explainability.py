from ml.explainability import explain_prediction
explanation = explain_prediction(ai_data, score, pd)

def explain_prediction(data, score, pd):

    explanations = []
    positive_factors = []
    negative_factors = []

    income = data.get("monthly_income") or data.get("monthly_revenue") or 0
    expenses = data.get("monthly_expenses") or 0
    repayment = data.get("monthly_repayment") or 0
    collateral = data.get("collateral_value") or 0
    loan_amount = data.get("loan_amount") or 1
    reserve = data.get("cash_reserve") or 0
    default_history = data.get("default_history")

    # ===============================
    # FINANCIAL STRENGTH
    # ===============================
    net_income = income - expenses

    if net_income > 300000:
        positive_factors.append("Strong net income position")
    elif net_income < 0:
        negative_factors.append("Negative net income (expenses exceed income)")
    else:
        negative_factors.append("Weak net income margin")

    # ===============================
    # DEBT BURDEN
    # ===============================
    if income > 0:
        dti = repayment / income
    else:
        dti = 1

    if dti < 0.2:
        positive_factors.append("Low debt-to-income ratio")
    elif dti > 0.5:
        negative_factors.append("High debt burden relative to income")

    # ===============================
    # CREDIT HISTORY
    # ===============================
    if default_history == "No":
        positive_factors.append("No prior default history")
    else:
        negative_factors.append("History of default increases risk")

    # ===============================
    # COLLATERAL
    # ===============================
    coverage = collateral / loan_amount

    if coverage >= 1:
        positive_factors.append("Fully secured by collateral")
    elif coverage < 0.5:
        negative_factors.append("Weak collateral coverage")

    # ===============================
    # LIQUIDITY BUFFER
    # ===============================
    if reserve > 500000:
        positive_factors.append("Strong liquidity buffer")
    elif reserve < 50000:
        negative_factors.append("Low cash reserve")


    st.markdown("## 🧠 Explainable AI (Why this decision?)")

    # POSITIVE
    st.write("### ✅ Positive Factors")
    for p in explanation["positive_factors"]:
        st.markdown(f"• {p}")

    # NEGATIVE
    st.write("### ⚠️ Risk Factors")
    for n in explanation["negative_factors"]:
        st.markdown(f"• {n}")

    # SUMMARY
    st.write("### 📌 Model Summary")
    st.write(explanation["summary"])

    return explanation

ai_result = run_ai_analysis(
    ai_data,
    score,
    decision,
    explanation=explanation
)