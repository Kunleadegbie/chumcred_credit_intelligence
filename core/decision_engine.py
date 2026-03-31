def make_decision(score: int) -> str:
    if score >= 75:
        return "APPROVE"
    elif score >= 50:
        return "REVIEW"
    return "REJECT"


def risk_level(score: int) -> str:
    if score >= 75:
        return "LOW RISK"
    elif score >= 50:
        return "MODERATE RISK"
    return "HIGH RISK"