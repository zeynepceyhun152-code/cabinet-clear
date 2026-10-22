"""
test_language.py - tests for the Turkish support on the server. No API key or internet needed.

Run:  python3 test_language.py
"""
import io
import os
import sys
import types

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
from lang_ctx import set_lang, reset_lang, get_lang, language_instruction

failures = []


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)


# ---------------------------------------------------------------- 1. the language of a request
check("default language is English", get_lang() == "en" and language_instruction() == "")
tok = set_lang("tr"); check("Turkish is picked up", get_lang() == "tr" and "Turkish" in language_instruction()); reset_lang(tok)
tok = set_lang("TR-tr"); check("'TR-tr' counts as Turkish", get_lang() == "tr"); reset_lang(tok)
tok = set_lang(None); check("missing header means English", get_lang() == "en"); reset_lang(tok)
tok = set_lang("de"); check("other languages fall back to English", get_lang() == "en"); reset_lang(tok)

# ---------------------------------------------------------------- 2. the header reaches the code (sync and async endpoints)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lang_middleware import install

app = FastAPI()
install(app)

@app.get("/a")
async def a():
    return {"lang": get_lang()}

@app.get("/s")
def s():
    return {"lang": get_lang()}

c = TestClient(app)
check("async endpoint sees X-Lang: tr", c.get("/a", headers={"X-Lang": "tr"}).json()["lang"] == "tr")
check("sync endpoint sees X-Lang: tr", c.get("/s", headers={"X-Lang": "tr"}).json()["lang"] == "tr")
check("next request without header is English again", c.get("/a").json()["lang"] == "en")
check("X-Lang: en is English", c.get("/s", headers={"X-Lang": "en"}).json()["lang"] == "en")

# ---------------------------------------------------------------- 3. server-written text
from translate_server import tx, translate
tok = set_lang("tr")
check("fixed warning translated", tx("Complete the full course even if feeling better.") == "Daha iyi hissetseniz bile kürü tamamlayın.")
check("text with a drug name translated", tx("Your discharge letter prescribes Ibuprofen — please get a new supply from your pharmacist.") ==
      "Taburcu belgenizde Ibuprofen yazılı — lütfen eczanenizden yeni bir kutu alın.")
check("unknown text is left alone", tx("Some text nobody translated") == "Some text nobody translated")
reset_lang(tok)
check("English request gets English back", tx("Complete the full course even if feeling better.") == "Complete the full course even if feeling better.")

# ---------------------------------------------------------------- 4. adaptive explanation in Turkish
import json, explain
data = {
    "diagnosis_summary": "Maya'nın astım atağı tedavi edildi ve geçti.",
    "medications": [{"name": "Prednizolon", "dosage": "20mg", "frequency": "günde bir kez", "duration": "5 gün (son doz 17 Haziran)", "purpose": "hava yollarını sakinleştirmek için"}],
    "follow_up_appointments": [{"type": "Çocuk doktoru kontrolü", "timeframe": "1 hafta içinde (19 Haziran'a kadar)", "reason": "solunumu kontrol etmek"}],
    "warning_signs": ["Nefes almada zorluk veya hızlı nefes alıp verme"],
    "activity_restrictions": [], "extraction_confidence": "high", "confidence_notes": "",
}
good = {
    "opening": "Belgenizi birlikte, adım adım inceleyelim.",
    "what_happened": "Maya'nın astım atağı tedavi edildi ve geçti.",
    "do_now": ["Maya'ya prednizolonu günde bir kez verin.", "19 Haziran'a kadar çocuk doktoruna gidin."],
    "medicines": [{"name": "Prednizolon", "what_for": "Hava yollarını sakinleştirir.", "how_to_take": "20mg, günde bir kez, 5 gün (son doz 17 Haziran)."}],
    "warning_signs": [{"original": "Nefes almada zorluk veya hızlı nefes alıp verme", "plain": "Nefes alması zorlaşırsa veya çok hızlı nefes alırsa."}],
    "follow_up": [{"appointment": "Çocuk doktoru kontrolü", "when": "1 hafta içinde (19 Haziran'a kadar)", "why": "Solunumu kontrol etmek için."}],
    "good_to_know": [],
}
import copy
check("a good Turkish explanation passes every check", explain.check_faithfulness(good, data) == [])
x = copy.deepcopy(good); x["do_now"].append("Acil durumda 112'yi arayın.")
check("Turkish emergency number 112 is allowed", explain.check_faithfulness(x, data) == [])
x = copy.deepcopy(good); x["do_now"].append("Ateş çıkarsa 999'u arayın.")
check("an invented number is still caught", explain.check_faithfulness(x, data) != [])
x = copy.deepcopy(good); x["medicines"][0]["how_to_take"] = "30mg, günde bir kez, 5 gün (son doz 17 Haziran)."
check("a changed dose is caught in Turkish", explain.check_faithfulness(x, data) != [])
x = copy.deepcopy(good); x["do_now"].append("Kendinizi iyi hissedince ilacı bırakın.")
check("Turkish 'stop the medicine' advice is caught", explain.check_faithfulness(x, data) != [])
x = copy.deepcopy(good); x["do_now"].append("Doktoru aramanıza gerek yok.")
check("Turkish 'no need to call the doctor' is caught", explain.check_faithfulness(x, data) != [])
x = copy.deepcopy(good); x["warning_signs"] = []
check("a dropped warning sign is caught in Turkish", explain.check_faithfulness(x, data) != [])
check("the plain version passes its own checks in Turkish",
      explain.check_faithfulness(explain.fallback_explanation(data, explain.style_profile(5, 1)), data) == [])
p_en = explain.build_prompt(data, explain.style_profile(3, 3))
tok = set_lang("tr"); p_tr = explain.build_prompt(data, explain.style_profile(3, 3)); r = explain.generate_explanation(data, 3, 3, call_model=lambda p: json.dumps(good)); reset_lang(tok)
check("English prompt has no Turkish instruction", "Turkish" not in p_en)
check("Turkish prompt asks for Turkish and says to copy fields exactly", "Turkish (Türkçe)" in p_tr and "exactly as" in p_tr)
check("a good Turkish answer is used (no fallback)", not r["fallback"] and r["problems"] == [])

# ---------------------------------------------------------------- 5. PDF in English and Turkish
from pdf_generator import generate_summary_pdf
from pypdf import PdfReader
cross = {"summary": {"keep": 1, "dispose": 1, "unclear": 0, "missing_from_cabinet": 1},
         "keep": [{"drug_name": "Prednizolon", "expiration_date": "EXP 09/2026", "prescribed_dosage": "20mg", "prescribed_frequency": "günde bir kez",
                   "clinical_warning": "Do not stop suddenly. Take with food."}],
         "dispose": [{"drug_name": "Ibuprofen", "expiration_date": "EXP 03/2024", "warning": "Your discharge letter prescribes Ibuprofen — please get a new supply from your pharmacist."}],
         "unclear": [], "missing_from_cabinet": [{"drug_name": "Albuterol", "dosage": "2 puffs", "frequency": "every 4-6 hours as needed", "purpose": "nefes darlığı için"}]}
inter = [{"drug_a": "Ibuprofen", "drug_b": "Aspirin", "message": "Taking ibuprofen with aspirin can reduce aspirin's effectiveness and increase bleeding risk."}]
pdf_en = generate_summary_pdf({"diagnosis_summary": "Asthma flare-up, treated.", "follow_up_appointments": [{"type": "Pediatrician", "timeframe": "1 week"}], "warning_signs": ["Fast breathing"]}, cross, inter)
tok = set_lang("tr")
pdf_tr = generate_summary_pdf({"diagnosis_summary": "Astım atağı tedavi edildi; şimdi iyi durumda. Çocuğun ığ ş ğ İ harfleri.",
                               "follow_up_appointments": [{"type": "Çocuk doktoru", "timeframe": "1 hafta"}], "warning_signs": ["Hızlı nefes alıp verme"]}, cross, inter)
reset_lang(tok)
text_en = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf_en)).pages)
text_tr = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf_tr)).pages)
check("English PDF is still English", pdf_en[:4] == b"%PDF" and "Diagnosis Summary" in text_en and "Medicine Cabinet Plan" in text_en)
check("Turkish PDF has Turkish headings", pdf_tr[:4] == b"%PDF" and "Tanı Özeti" in text_tr and "İlaç Dolabı Planı" in text_tr)
check("Turkish PDF keeps the special letters", all(ch in text_tr for ch in "şğİı"))
check("Turkish PDF translated the server's fixed warning", "Aniden bırakmayın" in text_tr)
check("Turkish PDF translated the interaction text", "İbuprofeni aspirinle" in text_tr)
check("Turkish PDF translated the footer", "yalnızca bilgi amaçlıdır" in text_tr)

print("\nALL PASSED" if not failures else "\nFAILED: " + ", ".join(failures))
sys.exit(1 if failures else 0)
