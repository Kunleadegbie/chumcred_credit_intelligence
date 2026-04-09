from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import re


# ===============================
# HELPERS
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


def safe_text(value, fallback="N/A"):
    if value is None:
        return fallback
    text = str(value).strip()
    if text in ["", "None", "null"]:
        return fallback
    return text


def clean_filename(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def money(value) -> str:
    try:
        return f"NGN {float(value or 0):,.0f}"
    except Exception:
        return "NGN 0"


def resolve_logo_path(data: dict) -> str | None:
    """
    Logo resolution order:
    1. institution_logo_path in application data
    2. assets/institutions/<institution_slug or variants>.(png|jpg|jpeg|webp)
    3. assets/<institution_slug or variants>.(png|jpg|jpeg|webp)
    4. assets/logo.png fallback
    """
    explicit_logo = str(data.get("institution_logo_path") or "").strip()
    if explicit_logo and os.path.exists(explicit_logo):
        return explicit_logo

    institution = str(data.get("institution") or data.get("institution_name") or "").strip()
    candidate_names = []
    if institution:
        slug = clean_filename(institution)
        candidate_names.extend([slug, slug.replace("_microfinance_bank", ""), slug.replace("_mfb", "")])
        raw = institution.strip().lower().replace("&", "and")
        trimmed = raw.replace(" microfinance bank", "").replace(" mfb", "").strip()
        if trimmed:
            candidate_names.extend([
                clean_filename(trimmed),
                trimmed.replace(" ", "_"),
                trimmed.replace(" ", "-"),
                trimmed.replace(" ", ""),
            ])

    seen = set()
    deduped_names = []
    for name in candidate_names:
        if name and name not in seen:
            seen.add(name)
            deduped_names.append(name)

    search_dirs = [
        os.path.join(os.getcwd(), "assets", "institutions"),
        os.path.join(os.getcwd(), "assets"),
    ]

    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for base_name in deduped_names:
            for ext in ["png", "jpg", "jpeg", "webp"]:
                candidate = os.path.join(search_dir, f"{base_name}.{ext}")
                if os.path.exists(candidate):
                    return candidate

    fallback_logo = os.path.join(os.getcwd(), "assets", "logo.png")
    if os.path.exists(fallback_logo):
        return fallback_logo

    return None


def get_memo_title(data: dict) -> str:
    institution = str(data.get("institution") or data.get("institution_name") or "").strip()
    if institution:
        return f"{institution.upper()} CREDIT MEMO"
    return "CREDIT MEMO"




def register_unicode_font() -> str:
    """
    Register a Unicode-capable font family so ₦ and other symbols render correctly in PDF,
    including bold text fragments used inside Paragraph tags.
    Returns the base font name to use in paragraph styles.
    """
    regular_candidates = [
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    bold_candidates = [
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]

    regular_path = next((p for p in regular_candidates if os.path.exists(p)), None)
    bold_path = next((p for p in bold_candidates if os.path.exists(p)), None)

    if regular_path:
        try:
            pdfmetrics.registerFont(TTFont("MemoUnicode", regular_path))
            if bold_path:
                pdfmetrics.registerFont(TTFont("MemoUnicode-Bold", bold_path))
                pdfmetrics.registerFontFamily(
                    "MemoUnicode",
                    normal="MemoUnicode",
                    bold="MemoUnicode-Bold",
                    italic="MemoUnicode",
                    boldItalic="MemoUnicode-Bold",
                )
            return "MemoUnicode"
        except Exception:
            pass

    return "Helvetica"


# ===============================
# MAIN PDF GENERATOR
# ===============================
def generate_credit_memo(data, filename="credit_memo.pdf"):
    doc = SimpleDocTemplate(filename, pagesize=A4, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    font_name = register_unicode_font()

    styles["Normal"].fontName = font_name
    styles["Title"].fontName = font_name
    styles["Heading2"].fontName = font_name
    styles["Normal"].boldFontName = f"{font_name}-Bold" if font_name != "Helvetica" else "Helvetica-Bold"
    styles["Title"].boldFontName = f"{font_name}-Bold" if font_name != "Helvetica" else "Helvetica-Bold"
    styles["Heading2"].boldFontName = f"{font_name}-Bold" if font_name != "Helvetica" else "Helvetica-Bold"

    title_style = ParagraphStyle(
        "MemoTitle",
        parent=styles["Title"],
        fontName=font_name,
        boldFontName=f"{font_name}-Bold" if font_name != "Helvetica" else "Helvetica-Bold",
        textColor=colors.HexColor("#1f3c88"),
        fontSize=18,
        leading=22,
        spaceAfter=6,
    )

    section_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontName=font_name,
        boldFontName=f"{font_name}-Bold" if font_name != "Helvetica" else "Helvetica-Bold",
        textColor=colors.HexColor("#1f3c88"),
        fontSize=13,
        leading=15,
        spaceAfter=6,
        spaceBefore=6,
    )

    content = []

    def section(title):
        content.append(Spacer(1, 10))
        content.append(Paragraph(f"<b>{title}</b>", section_style))
        content.append(Spacer(1, 4))

    def row(label, value):
        content.append(Paragraph(f"<b>{safe_text(label)}:</b> {safe_text(value)}", styles["Normal"]))
        content.append(Spacer(1, 4))

    # ===============================
    # LOGO + HEADER
    # ===============================
    logo_path = resolve_logo_path(data)
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=1.6 * inch, height=1.0 * inch)
            content.append(logo)
            content.append(Spacer(1, 8))
        except Exception:
            pass

    content.append(Paragraph(f"<b>{get_memo_title(data)}</b>", title_style))
    institution_name = safe_text(data.get("institution") or data.get("institution_name"), "Institution Not Stated")
    content.append(Paragraph(f"<b>Institution:</b> {institution_name}", styles["Normal"]))
    content.append(Spacer(1, 12))

    # ===============================
    # EXECUTIVE SUMMARY
    # ===============================
    section("1. Executive Summary")
    row("Client Name", data.get("client_name"))
    row("Loan Amount", money(data.get("loan_amount", 0)))
    row("Tenor", f"{safe_text(data.get('tenor'), 'N/A')} months")
    row("Loan Purpose", data.get("loan_purpose"))
    row("Borrower Type", data.get("borrower_type"))

    # ===============================
    # CREDIT RISK RATING
    # ===============================
    section("2. Credit Risk Rating")
    score = data.get("credit_score", data.get("score", 0))
    dscr = data.get("dscr")
    risk_grade_value = data.get("risk_grade") or risk_grade(float(score or 0))

    row("Risk Score", score)
    row("Risk Grade", risk_grade_value)
    if dscr not in [None, "", "None", "null"]:
        try:
            row("DSCR", f"{float(dscr):.2f}x")
        except Exception:
            row("DSCR", dscr)

    if data.get("collateral_cover") not in [None, "", "None", "null"]:
        try:
            row("Collateral Cover", f"{float(data.get('collateral_cover')):.2f}x")
        except Exception:
            row("Collateral Cover", data.get("collateral_cover"))

    # ===============================
    # AI / CREDIT ASSESSMENT
    # ===============================
    section("3. Credit Assessment")

    borrower_summary = data.get("borrower_summary") or data.get("borrower_profile")
    facility_request = data.get("facility_request") or data.get("facility_details")
    financial_summary = data.get("financial_summary")
    risk_assessment = data.get("risk_assessment")
    decision_summary = data.get("decision_summary") or data.get("ai_recommendation")

    row("Borrower Summary", borrower_summary)
    row("Facility Request", facility_request)
    if safe_text(financial_summary, ""):
        row("Financial Summary", financial_summary)
    row("Risk Assessment", risk_assessment)
    row("Decision Summary", decision_summary)

    strengths = data.get("ai_strengths") or []
    if strengths:
        content.append(Spacer(1, 6))
        content.append(Paragraph("<b>Key Strengths:</b>", styles["Normal"]))
        for item in strengths:
            content.append(Paragraph(f"• {safe_text(item)}", styles["Normal"]))
        content.append(Spacer(1, 4))

    risks = data.get("ai_risk_flags") or []
    if risks:
        content.append(Spacer(1, 6))
        content.append(Paragraph("<b>Key Risks:</b>", styles["Normal"]))
        for item in risks:
            content.append(Paragraph(f"• {safe_text(item)}", styles["Normal"]))
        content.append(Spacer(1, 4))

    narrative = safe_text(data.get("ai_narrative"), "")
    if narrative:
        narrative = narrative.replace("$", "NGN ").replace("₦", "NGN ").replace("*", "").replace("_", "").strip()
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
            stage = safe_text(h.get("stage"), "Unknown")
            action = safe_text(h.get("action"), "")
            note = safe_text(h.get("note"), "")
            time = safe_text(h.get("timestamp"), "")
            row(f"{stage} ({action})", f"Note: {note} | Time: {time}")
    else:
        row("Approval Status", "No approvals recorded")

    # ===============================
    # SIGNATURES
    # ===============================
    section("5. Approval Sign-Off")
    content.append(Spacer(1, 16))
    content.append(Paragraph("Credit Officer: ____________________", styles["Normal"]))
    content.append(Spacer(1, 12))
    content.append(Paragraph("Credit Analyst: ____________________", styles["Normal"]))
    content.append(Spacer(1, 12))
    content.append(Paragraph("Credit Manager: ____________________", styles["Normal"]))
    content.append(Spacer(1, 12))
    content.append(Paragraph("Final Approver: ____________________", styles["Normal"]))

    doc.build(content)
    return filename
