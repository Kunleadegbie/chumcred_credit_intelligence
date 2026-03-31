def get_dashboard_title(role: str) -> str:
    mapping = {
        "super_admin": "Super Admin Dashboard",
        "institution_admin": "Institution Admin Dashboard",
        "loan_officer": "Loan Officer Dashboard",
        "credit_analyst": "Credit Analyst Dashboard",
        "manager": "Manager Dashboard",
        "pending": "Pending Approval"
    }
    return mapping.get(role, "User Dashboard")