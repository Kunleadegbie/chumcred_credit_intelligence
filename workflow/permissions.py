def can_create_application(role: str) -> bool:
    return role in ["loan_officer", "institution_admin", "super_admin"]


def can_review_analyst(role: str) -> bool:
    return role in ["credit_analyst", "institution_admin", "super_admin"]


def can_final_approve(role: str) -> bool:
    return role in ["manager", "institution_admin", "super_admin"]


def can_manage_users(role: str) -> bool:
    return role in ["institution_admin", "super_admin"]