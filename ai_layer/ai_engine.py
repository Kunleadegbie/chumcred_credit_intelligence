def run_ai_analysis(data, score, decision):

    borrower = data.get("borrower_type")
    amount = data.get("loan_amount")
    purpose = data.get("loan_purpose")
    tenor = data.get("tenor")

    income = data.get("monthly_income", 0)
    expenses = data.get("monthly_expenses", 0)

    collateral = data.get("collateral_type")
    collateral_value = data.get("collateral_value", 0)

    # ===============================
    # BORROWER PROFILE
    # ===============================
    borrower_profile = (
        f"The borrower is a {borrower} applying for a credit facility."
    )

    # ===============================
    # FACILITY DETAILS
    # ===============================
    facility_details = (
        f"The applicant requests ₦{amount:,.0f} for {purpose} over {tenor} months."
    )

    # ===============================
    # FINANCIAL SUMMARY
    # ===============================
    surplus = income - expenses
    financial_summary = (
        f"The borrower generates ₦{income:,.0f} monthly with expenses of ₦{expenses:,.0f}, "
        f"resulting in a net surplus of ₦{surplus:,.0f}."
    )

    # ===============================
    # RISK ASSESSMENT
    # ===============================
    if score >= 75:
        risk = "low"
    elif score >= 50:
        risk = "moderate"
    else:
        risk = "high"

    risk_assessment = (
        f"The credit risk is assessed as {risk} based on income stability, repayment capacity, "
        f"and existing obligations."
    )

    # ===============================
    # MITIGANTS
    # ===============================
    mitigants = (
        f"Collateral provided ({collateral}) valued at ₦{collateral_value:,.0f} "
        f"serves as a secondary repayment source."
        if collateral and collateral != "None"
        else "No strong collateral provided; reliance is on cash flow."
    )

    # ===============================
    # FINAL RECOMMENDATION
    # ===============================
    recommendation = decision

    return {
        "borrower_profile": borrower_profile,
        "facility_details": facility_details,
        "financial_summary": financial_summary,
        "risk_assessment": risk_assessment,
        "mitigants": mitigants,
        "recommendation": recommendation,

        # KEEP OLD FIELDS (DO NOT BREAK YOUR APP)
        "ai_narrative": f"{borrower_profile} {facility_details} {risk_assessment}",
        "ai_strengths": [],
        "ai_risk_flags": [],
        "ai_recommendation": recommendation
    }