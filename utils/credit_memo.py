from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch


# ===============================
# RISK GRADING
# ===============================
def risk_grade(score):
    if score >= 80:
        return "A (Low Risk)"
    elif score >= 70:
        return "B (Moderate Risk)"
    elif score >= 60:
        return "C (Watchlist)"
    elif score >= 50:
        return "D (High Risk)"
    return "E (Very High Risk)"


# ===============================
# MAIN PDF GENERATOR
# ===============================
def generate_credit_memo(data, filename="credit_memo.pdf"):

    doc = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()

    content = []

    # ===============================
    # HELPERS
    # ===============================
    def section(title):
        content.append(Spacer(1, 10))
        content.append(Paragraph(f"<b>{title}</b>", styles["Heading2"]))
        content.append(Spacer(1, 6))

    def row(label, value):
        value = value if value else "N/A"
        content.append(Paragraph(f"<b>{label}:</b> {value}", styles["Normal"]))
        content.append(Spacer(1, 4))

    # ===============================
    # LOGO
    # ===============================

    import os

    logo_path = os.path.join(os.getcwd(), "assets", "logo.png")

    if os.path.exists(logo_path):
        logo = Image(logo_path, width=1.5 * inch, height=1.5 * inch)
        content.append(logo)

    # ===============================
    # HEADER
    # ===============================
    content.append(Paragraph("<b>CHUMCRED AI CREDIT MEMO</b>", styles["Title"]))
    content.append(Spacer(1, 15))

    # ===============================
    # EXECUTIVE SUMMARY
    # ===============================
    section("1. Executive Summary")

    row("Client Name", data.get("client_name"))
    row("Loan Amount", f"₦{data.get('loan_amount', 0):,.0f}")
    row("Tenor", f"{data.get('tenor')} months")
    row("Loan Purpose", data.get("loan_purpose"))

    # ===============================
    # CREDIT RISK RATING
    # ===============================
    section("2. Credit Risk Rating")

    score = data.get("score", 0)
    row("Risk Score", score)
    row("Risk Grade", risk_grade(score))

    # ===============================
    # AI CREDIT ASSESSMENT (YOUR STRUCTURE)
    # ===============================
    section("3. AI Credit Assessment")

    # Clean narrative safely
    narrative = data.get("ai_narrative", "") or ""
    narrative = narrative.replace("$", "₦").replace("*", "").replace("_", "").strip()

    row("Recommendation", data.get("ai_recommendation"))
    content.append(Spacer(1, 6))
    content.append(Paragraph("<b>Risk Narrative:</b>", styles["Normal"]))
    content.append(Spacer(1, 4))
    content.append(Paragraph(narrative, styles["Normal"]))

    # ===============================
    # APPROVAL TRAIL
    # ===============================
    section("4. Approval Trail")

    history = data.get("approval_history") or []

    if history:
        for h in history:
            stage = h.get("stage", "Unknown")
            action = h.get("action", "")
            note = h.get("note", "")
            time = h.get("timestamp", "")

            row(
                f"{stage} ({action})",
                f"Note: {note} | Time: {time}"
            )
    else:
        row("Approval Status", "No approvals recorded")

    # ===============================
    # SIGNATURES (BANK STYLE)
    # ===============================
    section("5. Approval Sign-Off")

    content.append(Spacer(1, 20))

    content.append(Paragraph("Credit Officer: ____________________", styles["Normal"]))
    content.append(Spacer(1, 12))

    content.append(Paragraph("Credit Analyst: ____________________", styles["Normal"]))
    content.append(Spacer(1, 12))

    content.append(Paragraph("Credit Manager: ____________________", styles["Normal"]))
    content.append(Spacer(1, 12))

    content.append(Paragraph("Final Approver: ____________________", styles["Normal"]))

    # ===============================
    # BUILD DOCUMENT
    # ===============================
    doc.build(content)

    return filename