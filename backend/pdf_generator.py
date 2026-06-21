from fpdf import FPDF
from datetime import datetime
import io

class SummaryPDF(FPDF):
    def header(self):
        self.set_fill_color(30, 58, 95)
        self.rect(0, 0, 210, 28, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 18)
        self.set_y(8)
        self.cell(0, 10, 'Cabinet Clear', ln=True, align='C')
        self.set_font('Helvetica', '', 9)
        self.cell(0, 6, 'Medicine Management Summary', ln=True, align='C')
        self.set_text_color(0, 0, 0)
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, 'This document is for reference only and does not replace medical advice. Always confirm with your doctor or pharmacist.', align='C')


def _safe(text) -> str:
    """Strip/replace characters that FPDF's core Helvetica font can't encode."""
    if text is None:
        return ""
    text = str(text)
    replacements = {
        "\u2713": "[OK]",    # check mark
        "\u2715": "[X]",     # x mark
        "\u26a0": "[!]",     # warning triangle
        "\u2022": "-",       # bullet
        "\u2014": "-",       # em dash
        "\u2013": "-",       # en dash
        "\u2019": "'",       # right single quote
        "\u2018": "'",       # left single quote
        "\u201c": '"',       # left double quote
        "\u201d": '"',       # right double quote
        "\u2026": "...",     # ellipsis
        "\u2693\ufe0f": "",  # any stray emoji + variation selector
        "\ufe0f": "",        # variation selector (used after emoji like ⚕️)
        "\u2695": "[Rx]",    # medical/staff of hermes symbol
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    # Final safety net: drop any remaining non-Latin-1 characters
    return text.encode("latin-1", "ignore").decode("latin-1")


def generate_summary_pdf(discharge_data: dict, cross_ref_result: dict, interactions: list) -> bytes:
    discharge_data = discharge_data or {}
    cross_ref_result = cross_ref_result or {}
    interactions = interactions or []

    pdf = SummaryPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Date
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, _safe(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"), ln=True, align='R')
    pdf.ln(2)

    # Diagnosis
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(30, 58, 95)
    pdf.cell(0, 8, 'Diagnosis Summary', ln=True)
    pdf.set_draw_color(30, 58, 95)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 6, _safe(discharge_data.get('diagnosis_summary', 'N/A')))
    pdf.ln(4)

    # Medicine Plan
    summary = cross_ref_result.get('summary', {}) or {}
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(30, 58, 95)
    pdf.cell(0, 8, 'Medicine Cabinet Plan', ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)

    # Summary boxes
    boxes = [
        (summary.get('keep', 0), 'Keep', (22, 163, 74)),
        (summary.get('dispose', 0), 'Dispose', (220, 38, 38)),
        (summary.get('unclear', 0), 'Unclear', (180, 83, 9)),
        (summary.get('missing_from_cabinet', 0), 'Get from Pharmacy', (124, 58, 237)),
    ]
    x_start = 10
    box_w = 45
    for count, label, color in boxes:
        pdf.set_fill_color(*color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x_start, pdf.get_y())
        pdf.set_font('Helvetica', 'B', 16)
        pdf.cell(box_w - 2, 10, str(count), ln=False, align='C', fill=True)
        pdf.set_xy(x_start, pdf.get_y() + 10)
        pdf.set_font('Helvetica', '', 7)
        pdf.cell(box_w - 2, 6, label, ln=False, align='C', fill=True)
        x_start += box_w
    pdf.ln(20)

    def section(title, items, color, fields):
        if not items:
            return
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(*color)
        pdf.cell(0, 7, _safe(title), ln=True)
        pdf.set_text_color(0, 0, 0)
        for item in items:
            pdf.set_fill_color(245, 245, 245)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(0, 6, _safe(item.get('drug_name', 'Unknown')), ln=True, fill=True)
            pdf.set_font('Helvetica', '', 9)
            for field in fields:
                val = item.get(field)
                if val:
                    label = field.replace('_', ' ').title()
                    pdf.multi_cell(0, 5, _safe(f"  {label}: {val}"))
            pdf.ln(2)

    section('[OK] Keep & Take As Directed', cross_ref_result.get('keep', []),
            (22, 163, 74), ['prescribed_dosage', 'prescribed_frequency', 'expiration_date', 'clinical_warning'])
    section('[X] Dispose (Expired)', cross_ref_result.get('dispose', []),
            (220, 38, 38), ['expiration_date', 'warning'])
    section('[?] Unclear - Needs Attention', cross_ref_result.get('unclear', []),
            (180, 83, 9), ['reason', 'action'])
    section('[!] Get From Pharmacy', cross_ref_result.get('missing_from_cabinet', []),
            (124, 58, 237), ['dosage', 'frequency', 'purpose'])

    # Follow-up appointments
    followups = discharge_data.get('follow_up_appointments', [])
    if followups:
        pdf.set_font('Helvetica', 'B', 13)
        pdf.set_text_color(30, 58, 95)
        pdf.cell(0, 8, 'Follow-up Appointments', ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(0, 0, 0)
        for f in followups:
            pdf.cell(0, 6, _safe(f"- {f.get('type', '')} - {f.get('timeframe', '')}"), ln=True)
        pdf.ln(4)

    # Warning signs
    warnings = discharge_data.get('warning_signs', [])
    if warnings:
        pdf.set_font('Helvetica', 'B', 13)
        pdf.set_text_color(220, 38, 38)
        pdf.cell(0, 8, 'Warning Signs - Go To ER If:', ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(0, 0, 0)
        for w in warnings:
            pdf.cell(0, 6, _safe(f"- {w}"), ln=True)
        pdf.ln(4)

    # Drug interactions
    if interactions:
        pdf.set_font('Helvetica', 'B', 13)
        pdf.set_text_color(180, 83, 9)
        pdf.cell(0, 8, 'Drug Interaction Alerts', ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(0, 0, 0)
        for interaction in interactions:
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(0, 6, _safe(f"{interaction.get('drug_a','')} + {interaction.get('drug_b','')}"), ln=True)
            pdf.set_font('Helvetica', '', 9)
            pdf.multi_cell(0, 5, _safe(f"  {interaction.get('message','')}"))
            pdf.ln(2)

    return bytes(pdf.output())