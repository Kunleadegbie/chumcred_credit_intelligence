def classify_loan(borrower_type: str, loan_purpose: str) -> str:
    if borrower_type == "Salary Earner":
        return "Retail Loan"
    elif borrower_type == "SME":
        if loan_purpose == "Working Capital":
            return "SME Working Capital"
        return "SME Expansion Loan"
    else:
        return "Micro Retail Loan"