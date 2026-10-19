"""
test_cabinet_scan.py - tests for the whole-shelf scanner. No API key, photos or internet needed.

Run from the backend folder:  python3 test_cabinet_scan.py
"""
import io
import json
import os
import sys
from datetime import date

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
sys.path.insert(0, os.getcwd())
from PIL import Image
import cabinet_scan as cs

failures = []


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)


# ---------------------------------------------------------------- expiry dates
T = date(2026, 10, 19)
cases = [
    ("EXP 09/2026", ("2026-09", True)), ("EXP 10/2026", ("2026-10", False)), ("EXP 11/2026", ("2026-11", False)),
    ("09/26", ("2026-09", True)), ("12/27", ("2027-12", False)), ("2026-03", ("2026-03", True)), ("2027/01", ("2027-01", False)),
    ("Sep 2026", ("2026-09", True)), ("SEPT 2027", ("2027-09", False)), ("Best by Jan 2025", ("2025-01", True)),
    ("EXP: 03.2024", ("2024-03", True)), ("SKT 05/2028", ("2028-05", False)), ("Haz 2027", ("2027-06", False)),
    ("EXP 2026", (None, None)), ("LOT 12345", (None, None)), ("", (None, None)), (None, (None, None)), ("13/2026", (None, None)),
]
bad = [(t, cs.parse_expiry(t, T), want) for t, want in cases if cs.parse_expiry(t, T) != want]
check(f"expiry dates read correctly ({len(cases) - len(bad)}/{len(cases)})", not bad)
for t, got, want in bad:
    print("     ", repr(t), "got", got, "wanted", want)
check("the current month is NOT expired yet", cs.parse_expiry("10/2026", T) == ("2026-10", False))

# ---------------------------------------------------------------- checking the outlines
raw = [
    {"box": [0.10, 0.10, 0.30, 0.40], "name": "Tylenol Extra Strength", "strength": "500 mg", "expiry": "EXP 09/2026", "confidence": "high"},
    {"box": [0.12, 0.11, 0.31, 0.41], "name": "Tylenol", "confidence": "medium"},                 # near-duplicate of the first
    {"box": [0.55, 0.12, 0.80, 0.38], "name": None, "confidence": "high"},                        # unreadable: must not stay 'high'
    {"box": [0.05, 0.60, 0.25, 0.90], "name": "Advil", "confidence": "medium", "expiry": "12/2027"},
    {"box": [0.4, 0.4, 0.401, 0.401], "name": "Tiny"},                                            # far too small
    {"box": [1.2, -0.3, 0.9, 0.5], "name": "Out of bounds", "confidence": "high"},                # clamped and fixed
    {"box": "garbage", "name": "Broken"}, {"name": "No box"}, "not a dict", None,
    {"box": [0.6, 0.6, 0.9, 0.9], "name": "unknown", "confidence": "high"},                       # 'unknown' is not a name
]
items = cs.validate_items(raw, T)
names = [i["name"] for i in items]
check("near-duplicate outline is dropped", sum(1 for n in names if n and n.startswith("Tylenol")) == 1)
check("the better read of a duplicate is kept", "Tylenol Extra Strength" in names)
check("broken, tiny and missing boxes are dropped", "Tiny" not in names and "Broken" not in names and "No box" not in names)
check("an unreadable name is never trusted", all(i["confidence"] == "low" for i in items if i["name"] is None))
check("'unknown' is turned into no name", not any((n or "").lower() == "unknown" for n in names))
check("every box is inside the photo and the right way round", all(0 <= b <= 1 for i in items for b in i["box"]) and all(i["box"][0] < i["box"][2] and i["box"][1] < i["box"][3] for i in items))
check("items are numbered 1..n in order", [i["id"] for i in items] == list(range(1, len(items) + 1)))
top = [i for i in items if (i["box"][1] + i["box"][3]) / 2 < 0.3]
check("reading order: top row comes before the bottom row", items.index(top[0]) < max(items.index(i) for i in items if (i["box"][1] + i["box"][3]) / 2 > 0.6))
check("close-up flag: unreadable or low confidence", all(i["needs_closeup"] for i in items if i["name"] is None or i["confidence"] == "low") and not [i for i in items if i["name"] == "Tylenol Extra Strength"][0]["needs_closeup"])
many = cs.validate_items([{"box": [0.01 * i, 0.5, 0.01 * i + 0.009, 0.52], "name": f"M{i}", "confidence": "high"} for i in range(60)])
check("at most 30 items", len(many) <= 30)
check("an AI reply that is not a list gives no items", cs.validate_items({"a": 1}) == [] and cs.validate_items(None) == [])
check("expired is worked out from the printed date, not trusted from the AI",
      [i for i in items if i["name"] == "Advil"][0]["is_expired"] is False and
      cs.validate_items([{"box": [0.1, 0.1, 0.3, 0.3], "name": "X", "expiry": "03/2024", "is_expired": False, "confidence": "high"}], T)[0]["is_expired"] is True)

# ---------------------------------------------------------------- the same shape as the one-at-a-time scanner
entry = cs.to_cabinet_entry([i for i in items if i["name"] == "Tylenol Extra Strength"][0])
keys = {"drug_name", "active_ingredient", "dosage_strength", "expiration_date", "expiration_parsed", "is_expired", "extraction_confidence", "confidence_notes"}
check("entries have exactly the fields 'Check my cabinet' expects", set(entry) == keys)
check("an unreadable package becomes 'Unknown'", cs.to_cabinet_entry([i for i in items if i["name"] is None][0])["drug_name"] == "Unknown")
from crossreference import cross_reference
discharge = {"medications": [{"name": "Acetaminophen", "dosage": "500mg", "frequency": "every 6 hours"}]}
res = cross_reference(discharge, [i["entry"] if "entry" in i else cs.to_cabinet_entry(i) for i in items])
check("the cabinet check accepts them: unreadable ones go to Unclear",
      any(u["drug_name"] == "Unknown" for u in res["unclear"]) and res["summary"]["total_cabinet_meds"] == len(items))
check("an expired readable one goes to Dispose", any(d["drug_name"] == "Tylenol Extra Strength" for d in res["dispose"]))

# ---------------------------------------------------------------- the photo
im = Image.new("RGB", (3000, 2000), (200, 30, 30))
exif = im.getexif(); exif[274] = 6                       # phone says: rotate 90 degrees
buf = io.BytesIO(); im.save(buf, format="JPEG", exif=exif)
jpeg, w, h = cs.prepare_image(buf.getvalue())
check("a big photo is shrunk to the limit", max(w, h) <= cs.MAX_SIDE)
check("phone rotation is applied (landscape becomes portrait)", h > w)
png = io.BytesIO(); Image.new("RGBA", (100, 50)).save(png, format="PNG")
check("PNG with transparency works", cs.prepare_image(png.getvalue())[1:] == (100, 50))
try:
    cs.prepare_image(b"not an image"); bad_img = False
except Exception:
    bad_img = True
check("a file that is not a photo is refused", bad_img)

# ---------------------------------------------------------------- the whole thing, with a fake AI
reply = json.dumps({"packages": raw[:4], "image_notes": "Slightly dark."})
sent = []
out = cs.scan_cabinet(buf.getvalue(), call_model=lambda b: sent.append(b) or reply, today=T)
check("scan returns items, count, image size and notes", out["count"] == len(out["items"]) >= 2 and out["image"]["height"] > out["image"]["width"] and out["notes"] == "Slightly dark.")
check("each item carries its cabinet entry", all("entry" in i and "drug_name" in i["entry"] for i in out["items"]))
check("the AI received a JPEG", sent and sent[0][:2] == b"\xff\xd8")
out2 = cs.scan_cabinet(buf.getvalue(), call_model=lambda b: "```json\n" + reply + "\n```")
check("a reply wrapped in a code block still works", out2["count"] == out["count"])
try:
    cs.scan_cabinet(buf.getvalue(), call_model=lambda b: "Sorry, I can't help."); no_json = False
except ValueError:
    no_json = True
check("a reply with no JSON gives a clear error", no_json)
check("an empty shelf gives zero items, not an error", cs.scan_cabinet(buf.getvalue(), call_model=lambda b: '{"packages": []}')["count"] == 0)

print("\nALL PASSED" if not failures else "\nFAILED: " + ", ".join(failures))
sys.exit(1 if failures else 0)
