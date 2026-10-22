from fpdf import FPDF
from datetime import datetime
import io
from pathlib import Path

from lang_ctx import get_lang
from translate_server import tx

# Turkish letters (s, g, i with marks) are not in the PDF's built-in font, so Turkish uses a Unicode font.
# DejaVu Sans ships inside matplotlib, which your app already installs. If it is missing we fall back to
# the built-in font and print the Turkish letters without their marks, so nothing is ever dropped.
def _find_unicode_fonts():
    """The Turkish-capable font files. First the project's own backend/fonts folder (so nothing else has to be installed),
    then the copy that ships inside matplotlib. Returns None only if neither is there."""
    folders = [Path(__file__).resolve().parent / "fonts"]
    try:
        import matplotlib
        folders.append(Path(matplotlib.get_data_path()) / "fonts" / "ttf")
    except Exception:
        pass
    for d in folders:
        files = {"": d / "DejaVuSans.ttf", "B": d / "DejaVuSans-Bold.ttf", "I": d / "DejaVuSans-Oblique.ttf"}
        if all(p.exists() for p in files.values()):
            return files
    return None

_TR_ASCII = str.maketrans("şŞğĞıİ", "sSgGiI")

PDF_TR = {
    "Medicine Management Summary": "İlaç Yönetimi Özeti",
    "Generated": "Oluşturulma",
    "at": "saat",
    "Diagnosis Summary": "Tanı Özeti",
    "Medicine Cabinet Plan": "İlaç Dolabı Planı",
    "Keep": "Sakla", "Dispose": "At", "Unclear": "Belirsiz", "Get from Pharmacy": "Eczaneden Al",
    "[OK] Keep & Take As Directed": "[OK] Sakla ve Belirtildiği Gibi Kullan",
    "[X] Dispose (Expired)": "[X] At (Süresi Dolmuş)",
    "[?] Unclear - Needs Attention": "[?] Belirsiz - Dikkat Gerekiyor",
    "[!] Get From Pharmacy": "[!] Eczaneden Alın",
    "Follow-up Appointments": "Kontrol Randevuları",
    "Warning Signs - Go To ER If:": "Uyarı Belirtileri - Şu Durumlarda Acile Gidin:",
    "Drug Interaction Alerts": "İlaç Etkileşimi Uyarıları",
    "This document is for reference only and does not replace medical advice. Always confirm with your doctor or pharmacist.":
        "Bu belge yalnızca bilgi amaçlıdır ve tıbbi tavsiyenin yerini tutmaz. Her zaman doktorunuza veya eczacınıza danışın.",
    "Prescribed Dosage": "Reçeteli Doz", "Prescribed Frequency": "Reçeteli Sıklık", "Expiration Date": "Son Kullanma Tarihi",
    "Clinical Warning": "Klinik Uyarı", "Warning": "Uyarı", "Reason": "Neden", "Action": "Yapılacak",
    "Dosage": "Doz", "Frequency": "Sıklık", "Purpose": "Amaç", "Unknown": "Bilinmiyor", "N/A": "Yok",
}
TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def _t(text):
    """PDF wording for the current language."""
    return PDF_TR.get(text, text) if get_lang() == "tr" else text

class SummaryPDF(FPDF):
    font_name = 'Helvetica'
    unicode_ok = False

    def use_fonts(self):
        """Switch to the Unicode font for Turkish when it is available."""
        if get_lang() == "tr":
            files = _find_unicode_fonts()
            if files:
                self.add_font("DejaVu", "", str(files[""]))
                self.add_font("DejaVu", "B", str(files["B"]))
                self.add_font("DejaVu", "I", str(files["I"]))
                self.font_name = "DejaVu"
                self.unicode_ok = True

    def header(self):
        self.set_fill_color(30, 58, 95)
        self.rect(0, 0, 210, 28, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font(self.font_name, 'B', 18)
        self.set_y(8)
        self.cell(0, 10, 'Cabinet Clear', ln=True, align='C')
        self.set_font(self.font_name, '', 9)
        self.cell(0, 6, _safe(_t('Medicine Management Summary'), self.unicode_ok), ln=True, align='C')
        self.set_text_color(0, 0, 0)
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.font_name, 'I', 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, _safe(_t('This document is for reference only and does not replace medical advice. Always confirm with your doctor or pharmacist.'), self.unicode_ok), align='C')


def _safe(text, unicode_ok=False) -> str:
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
    if unicode_ok:
        return text
    # Built-in font: Turkish letters lose their marks (s, g, i) instead of being dropped
    text = text.translate(_TR_ASCII)
    return text.encode("latin-1", "ignore").decode("latin-1")


def generate_summary_pdf(discharge_data: dict, cross_ref_result: dict, interactions: list) -> bytes:
    discharge_data = discharge_data or {}
    cross_ref_result = cross_ref_result or {}
    interactions = interactions or []

    pdf = SummaryPDF()
    pdf.use_fonts()
    U = pdf.unicode_ok
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Date
    pdf.set_font(pdf.font_name, '', 9)
    pdf.set_text_color(100, 100, 100)
    now = datetime.now()
    if get_lang() == "tr":
        stamp = f"{_t('Generated')}: {now.day} {TR_MONTHS[now.month - 1]} {now.year} {_t('at')} {now.strftime('%H:%M')}"
    else:
        stamp = f"Generated: {now.strftime('%B %d, %Y at %I:%M %p')}"
    pdf.cell(0, 6, _safe(stamp, U), ln=True, align='R')
    pdf.ln(2)

    # Diagnosis
    pdf.set_font(pdf.font_name, 'B', 13)
    pdf.set_text_color(30, 58, 95)
    pdf.cell(0, 8, _safe(_t('Diagnosis Summary'), U), ln=True)
    pdf.set_draw_color(30, 58, 95)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.set_font(pdf.font_name, '', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 6, _safe(tx(discharge_data.get('diagnosis_summary', _t('N/A'))), U), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Medicine Plan
    summary = cross_ref_result.get('summary', {}) or {}
    pdf.set_font(pdf.font_name, 'B', 13)
    pdf.set_text_color(30, 58, 95)
    pdf.cell(0, 8, _safe(_t('Medicine Cabinet Plan'), U), ln=True)
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
        pdf.set_font(pdf.font_name, 'B', 16)
        pdf.cell(box_w - 2, 10, str(count), ln=False, align='C', fill=True)
        pdf.set_xy(x_start, pdf.get_y() + 10)
        pdf.set_font(pdf.font_name, '', 7)
        pdf.cell(box_w - 2, 6, _safe(_t(label), U), ln=False, align='C', fill=True)
        x_start += box_w
    pdf.ln(20)

    def section(title, items, color, fields):
        if not items:
            return
        pdf.set_font(pdf.font_name, 'B', 11)
        pdf.set_text_color(*color)
        pdf.cell(0, 7, _safe(_t(title), U), ln=True)
        pdf.set_text_color(0, 0, 0)
        for item in items:
            pdf.set_fill_color(245, 245, 245)
            pdf.set_font(pdf.font_name, 'B', 10)
            pdf.cell(0, 6, _safe(item.get('drug_name', _t('Unknown')), U), ln=True, fill=True)
            pdf.set_font(pdf.font_name, '', 9)
            for field in fields:
                val = item.get(field)
                if val:
                    label = _t(field.replace('_', ' ').title())
                    pdf.multi_cell(0, 5, _safe(f"  {label}: {tx(val)}", U), new_x="LMARGIN", new_y="NEXT")
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
        pdf.set_font(pdf.font_name, 'B', 13)
        pdf.set_text_color(30, 58, 95)
        pdf.cell(0, 8, _safe(_t('Follow-up Appointments'), U), ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        pdf.set_font(pdf.font_name, '', 10)
        pdf.set_text_color(0, 0, 0)
        for f in followups:
            pdf.cell(0, 6, _safe(f"- {f.get('type', '')} - {f.get('timeframe', '')}", U), ln=True)
        pdf.ln(4)

    # Warning signs
    warnings = discharge_data.get('warning_signs', [])
    if warnings:
        pdf.set_font(pdf.font_name, 'B', 13)
        pdf.set_text_color(220, 38, 38)
        pdf.cell(0, 8, _safe(_t('Warning Signs - Go To ER If:'), U), ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        pdf.set_font(pdf.font_name, '', 10)
        pdf.set_text_color(0, 0, 0)
        for w in warnings:
            pdf.cell(0, 6, _safe(f"- {w}", U), ln=True)
        pdf.ln(4)

    # Drug interactions
    if interactions:
        pdf.set_font(pdf.font_name, 'B', 13)
        pdf.set_text_color(180, 83, 9)
        pdf.cell(0, 8, _safe(_t('Drug Interaction Alerts'), U), ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        pdf.set_font(pdf.font_name, '', 10)
        pdf.set_text_color(0, 0, 0)
        for interaction in interactions:
            pdf.set_font(pdf.font_name, 'B', 10)
            pdf.cell(0, 6, _safe(f"{interaction.get('drug_a','')} + {interaction.get('drug_b','')}", U), ln=True)
            pdf.set_font(pdf.font_name, '', 9)
            pdf.multi_cell(0, 5, _safe(f"  {tx(interaction.get('message',''))}", U), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

    return bytes(pdf.output())