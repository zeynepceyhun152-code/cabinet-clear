"""
test_pdf_fonts.py - the Turkish PDF must not depend on anything installed on the computer.
Run from the backend folder:  python3 test_pdf_fonts.py
"""
import os
import subprocess
import sys

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
failures = []


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)


here = os.path.dirname(os.path.abspath(__file__))
fonts = os.path.join(here, "fonts")
need = ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf"]
check("the three font files are inside the project (backend/fonts)", all(os.path.exists(os.path.join(fonts, f)) and os.path.getsize(os.path.join(fonts, f)) > 100_000 for f in need))
check("the font's license text is shipped next to it", os.path.exists(os.path.join(fonts, "LICENSE_DEJAVU.txt")))

# run in a fresh process where matplotlib CANNOT be imported (like a computer that does not have it)
code = r'''
import io, sys
sys.modules["matplotlib"] = None
sys.path.insert(0, ".")
from lang_ctx import set_lang
from pdf_generator import generate_summary_pdf, _find_unicode_fonts
f = _find_unicode_fonts()
print("FONT_FOUND", bool(f), "FROM_PROJECT", bool(f) and "fonts" in str(f[""]))
set_lang("tr")
cross = {"summary": {"keep": 1}, "keep": [{"drug_name": "Prednizolon", "expiration_date": "EXP 09/2026", "prescribed_dosage": "20mg", "prescribed_frequency": "günde bir kez", "clinical_warning": "Do not stop suddenly. Take with food."}]}
b = generate_summary_pdf({"diagnosis_summary": "Astım atağı şğİı", "follow_up_appointments": [], "warning_signs": []}, cross, [])
print("EMBEDDED", b"DejaVu" in b)
try:
    import pypdf
    t = "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(b)).pages)
    print("TEXT_OK", all(x in t for x in ("Tanı Özeti", "İlaç Dolabı Planı", "şğİı", "Aniden bırakmayın", "Reçeteli Sıklık")))
except ImportError:
    print("TEXT_SKIPPED")
'''
out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=here, env=dict(os.environ, ANTHROPIC_API_KEY="test")).stdout
check("without matplotlib, the font is still found, and it comes from the project", "FONT_FOUND True FROM_PROJECT True" in out)
check("without matplotlib, the Turkish font is embedded in the PDF", "EMBEDDED True" in out)
if "TEXT_SKIPPED" in out:
    print("SKIP reading the text back (install it with: pip install pypdf)")
else:
    check("without matplotlib, every Turkish letter is in the PDF (Tanı, İlaç, şğİı, bırakmayın, Sıklık)", "TEXT_OK True" in out)

print("\nALL PASSED" if not failures else "\nFAILED: " + ", ".join(failures))
sys.exit(1 if failures else 0)
