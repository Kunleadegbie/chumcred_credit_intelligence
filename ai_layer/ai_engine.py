def run_ai_analysis(data, score, decision):
    borrower = data.get("borrower_type")
    amount = float(data.get("loan_amount", 0) or 0)
    purpose = data.get("loan_purpose")
    tenor = data.get("tenor")

    def safe_float(value, default=0.0):
        try:
            if value in [None, "", "None", "null"]:
                return float(default)
            return float(value)
        except Exception:
            return float(default)

    borrower_lower = str(borrower or "").strip().lower()
    monthly_income = safe_float(data.get("monthly_income", 0))
    monthly_expenses = safe_float(data.get("monthly_expenses", 0))
    deductions = safe_float(data.get("deductions", 0))
    revenue = safe_float(data.get("revenue", 0))
    bank_inflow = safe_float(data.get("bank_inflow", 0))
    daily_sales = safe_float(data.get("daily_sales", 0))
    outstanding = safe_float(data.get("total_outstanding_loans", 0))
    monthly_repayment = safe_float(data.get("monthly_repayment", 0))
    cash_reserve = safe_float(data.get("cash_reserve", 0))
    avg_balance = safe_float(data.get("average_balance", 0))
    collateral = data.get("collateral_type")
    collateral_value = safe_float(data.get("collateral_value", 0))
    default_history = str(data.get("default_history", "No") or "No").strip().lower()

    if borrower_lower == "salary earner":
        effective_income = max(monthly_income, bank_inflow, 0.0)
        effective_expenses = max(monthly_expenses, deductions, 0.0)
    elif borrower_lower == "sme":
        effective_income = max(revenue, bank_inflow, monthly_income, 0.0)
        effective_expenses = max(monthly_expenses, 0.0)
    else:
        estimated_monthly_sales = daily_sales * 26 if daily_sales > 0 else 0.0
        effective_income = max(bank_inflow, estimated_monthly_sales, monthly_income, 0.0)
        effective_expenses = max(monthly_expenses, 0.0)

    surplus = effective_income - effective_expenses
    dscr = round(surplus / monthly_repayment, 2) if monthly_repayment > 0 else 0.0
    collateral_cover = round(collateral_value / amount, 2) if amount > 0 else 0.0

    borrower_profile = f"The borrower is a {borrower} applying for a credit facility."
    facility_details = f"The applicant requests ₦{amount:,.0f} for {purpose} over {tenor} months."

    financial_summary = (
        f"The borrower shows effective monthly cash inflow of ₦{effective_income:,.0f}, "
        f"monthly obligations/expenses of ₦{effective_expenses:,.0f}, and estimated net surplus of ₦{surplus:,.0f}. "
        f"Existing outstanding obligations are ₦{outstanding:,.0f}, proposed monthly repayment is ₦{monthly_repayment:,.0f}, "
        f"while cash reserve and average balance stand at ₦{cash_reserve:,.0f} and ₦{avg_balance:,.0f} respectively."
    )

    if score >= 80:
        risk = "low"
        risk_grade = "A"
    elif score >= 65:
        risk = "moderate"
        risk_grade = "B"
    else:
        risk = "high"
        risk_grade = "C"

    risk_assessment = (
        f"The obligor is graded {risk_grade} with a {risk} risk profile based on cash-flow strength, repayment capacity, "
        f"existing obligations, collateral support, and repayment behavior. "
        f"Indicative DSCR is {dscr:.2f}x and collateral cover is {collateral_cover:.2f}x."
    )

    mitigants = (
        f"Collateral provided ({collateral}) valued at ₦{collateral_value:,.0f} serves as a secondary repayment source."
        if collateral and collateral != "None"
        else "No strong collateral provided; reliance is on cash flow and repayment discipline."
    )

    strengths = []
    risks = []
    if effective_income > 0:
        strengths.append(f"Cash inflow of ₦{effective_income:,.0f} provides a measurable primary repayment source.")
    if monthly_repayment > 0 and surplus >= monthly_repayment:
        strengths.append("Estimated monthly surplus appears adequate to support the proposed repayment obligation.")
    if collateral_value > 0:
        strengths.append(f"Collateral support of ₦{collateral_value:,.0f} improves recovery comfort.")
    if default_history in ["no", "none", "", "nil", "n/a"]:
        strengths.append("No prior default history was indicated in the submitted borrower profile.")

    if surplus < monthly_repayment and monthly_repayment > 0:
        risks.append("Estimated net cash surplus appears weak relative to the proposed monthly repayment.")
    if outstanding > 0:
        risks.append(f"Existing obligations of ₦{outstanding:,.0f} may pressure the borrower’s overall debt service capacity.")
    if not collateral or str(collateral).strip().lower() == "none":
        risks.append("No meaningful collateral support was indicated.")
    risks.append("Final credit decision should remain subject to verification of submitted financial figures and supporting documents.")

    recommendation = decision

    return {
        "borrower_profile": borrower_profile,
        "facility_details": facility_details,
        "financial_summary": financial_summary,
        "risk_assessment": risk_assessment,
        "mitigants": mitigants,
        "recommendation": recommendation,
        "ai_narrative": f"{borrower_profile} {facility_details} {risk_assessment}",
        "ai_strengths": strengths or ["No strong factors identified"],
        "ai_risk_flags": risks or ["No major risks identified"],
        "ai_recommendation": recommendation
    }
