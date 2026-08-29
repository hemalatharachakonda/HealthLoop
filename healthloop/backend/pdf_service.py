"""
Generates a downloadable diet plan PDF from a report analysis.
Uses fpdf2 - pure Python, no system dependencies (unlike wkhtmltopdf/pandoc),
so this works reliably on Render's free tier without extra setup.

Includes everything the web page shows: primary finding (with cause and how
to reduce it), other findings, normal findings, and the weekly diet plan -
previously this only included the primary summary and diet plan, silently
dropping the rest even though it was saved and shown on the web page.
"""
from fpdf import FPDF
from fpdf.enums import XPos, YPos


def build_diet_plan_pdf(
    patient_name: str,
    primary_finding: dict,
    other_findings: list,
    normal_findings: list,
    diet_plan: dict,
    language: str,
) -> bytes:
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(44, 122, 123)
    pdf.cell(0, 12, "HealthLoop - Your Report & Diet Plan", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 8, f"Prepared for: {_safe(patient_name)}   |   Language: {_safe(language)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # ---- Primary finding ----
    _section_header(pdf, "Your Main Result")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 6.5, _safe(primary_finding.get("summary", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if primary_finding.get("cause"):
        pdf.ln(2)
        _label(pdf, "Why this happens:")
        pdf.multi_cell(0, 6.5, _safe(primary_finding["cause"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if primary_finding.get("effects_if_untreated"):
        pdf.ln(2)
        _label(pdf, "If left unaddressed:")
        pdf.multi_cell(0, 6.5, _safe(primary_finding["effects_if_untreated"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if primary_finding.get("how_to_reduce"):
        pdf.ln(2)
        _label(pdf, "What can help:")
        for tip in primary_finding["how_to_reduce"]:
            pdf.multi_cell(0, 6.5, f"- {_safe(tip)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if primary_finding.get("diet_tips"):
        pdf.ln(2)
        _label(pdf, "Diet & lifestyle tips:")
        for tip in primary_finding["diet_tips"]:
            pdf.multi_cell(0, 6.5, f"- {_safe(tip)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # ---- Other findings ----
    if other_findings:
        _section_header(pdf, "We Also Noticed")
        for f in other_findings:
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(44, 122, 123)
            pdf.cell(0, 7, _safe(f.get("value_name", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 11)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 6.5, _safe(f.get("summary", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            if f.get("cause"):
                pdf.multi_cell(0, 6.5, f"Why: {_safe(f['cause'])}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            if f.get("food_suggestions"):
                pdf.multi_cell(0, 6.5, "Foods that help: " + ", ".join(_safe(x) for x in f["food_suggestions"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)
        pdf.ln(2)

    # ---- Normal findings ----
    if normal_findings:
        _section_header(pdf, "What Looks Fine")
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(40, 40, 40)
        for line in normal_findings:
            pdf.multi_cell(0, 6.5, f"- {_safe(line)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)

    # ---- Diet plan ----
    if diet_plan:
        _section_header(pdf, "Your Weekly Meal Plan")
        for day, meals in diet_plan.items():
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(44, 122, 123)
            pdf.cell(0, 8, _safe(day), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 11)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 6, f"  Veg: {_safe(meals.get('veg', '-'))}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.multi_cell(0, 6, f"  Non-veg: {_safe(meals.get('non_veg', '-'))}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)

    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.ln(4)
    pdf.multi_cell(
        0, 6,
        "This is general guidance based on your report and is not a substitute for advice from a doctor or dietitian.",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )

    return bytes(pdf.output())


def _section_header(pdf: FPDF, title: str):
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 9, _safe(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)


def _label(pdf: FPDF, text: str):
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 6, _safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(40, 40, 40)


def _safe(text) -> str:
    """fpdf2's core Helvetica font only supports Latin-1 characters. Non-Latin
    scripts (Hindi, Telugu, etc.) will render as '?' with this approach -
    a known limitation. A full fix would bundle a Unicode TTF font via
    pdf.add_font(). Also handles non-string inputs defensively."""
    if text is None:
        return ""
    text = str(text)
    try:
        text.encode("latin-1")
        return text
    except UnicodeEncodeError:
        return text.encode("latin-1", errors="replace").decode("latin-1")
