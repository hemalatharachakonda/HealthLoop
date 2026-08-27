"""
Generates a downloadable diet plan PDF from a report analysis.
Uses fpdf2 - pure Python, no system dependencies (unlike wkhtmltopdf/pandoc),
so this works reliably on Render's free tier without extra setup.
"""
from fpdf import FPDF
from fpdf.enums import XPos, YPos


def build_diet_plan_pdf(patient_name: str, primary_summary: str, diet_plan: dict, language: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(44, 122, 123)
    pdf.cell(0, 12, "HealthLoop - Weekly Diet Plan", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 8, f"Prepared for: {_safe(patient_name)}   |   Language: {_safe(language)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "What your report showed:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, _safe(primary_summary), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Your weekly meal plan:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)

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
        "This plan is general guidance based on your report and is not a substitute for advice from a doctor or dietitian.",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )

    return bytes(pdf.output())


def _safe(text: str) -> str:
    """fpdf2's core Helvetica font only supports Latin-1 characters. Non-Latin
    scripts (Hindi, Telugu, etc.) will render as '?' with this approach -
    a known limitation, flagged here rather than silently producing broken PDFs.
    A full fix would bundle a Unicode TTF font via pdf.add_font()."""
    if not text:
        return ""
    try:
        text.encode("latin-1")
        return text
    except UnicodeEncodeError:
        return text.encode("latin-1", errors="replace").decode("latin-1")
