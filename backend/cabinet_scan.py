"""
cabinet_scan.py - find every medicine package in ONE photo of a shelf or cabinet.

For each package it returns an outline (a box), and what could actually be READ on it: name, strength,
expiry date. The result has the same shape the one-at-a-time scanner makes, so the rest of the app
(Keep / Dispose / Unclear, the PDF, Turkish) works on it unchanged.

Safety rules built in:
  * A name is only accepted if it was readable on the package. Nothing is guessed from shape or colour.
    Anything unreadable becomes "Unknown", which the cabinet check files under "Unclear".
  * Whether a medicine is expired is worked out here from the printed date, not by the AI.
  * Outlines are checked (inside the photo, big enough, no near-duplicates) before they are used.

Today the outlines come from Claude's image reading. The function find_packages() is the single place to
swap in your own trained detector later; the screen and the checks stay the same.
"""
import base64
import io
import json
import re
from datetime import date

from PIL import Image, ImageOps

from lang_ctx import language_instruction

MAX_SIDE = 1568          # larger photos are shrunk (cheaper, and plenty to read labels)
MAX_ITEMS = 30
CONF_ORDER = {"high": 2, "medium": 1, "low": 0}

PROMPT = """You are helping a family check a medicine cabinet. The photo shows a shelf, drawer or cabinet.

Find EVERY medicine package you can see: boxes, bottles, tubes, inhalers, blister packs, jars. Count a package
if more than half of it is visible. Do not outline loose pills, people, furniture, bags or receipts.

Return ONLY a JSON object, no markdown, exactly like this:
{
  "packages": [
    {
      "box": [x0, y0, x1, y1],
      "name": "brand or generic name exactly as printed, or null",
      "active_ingredient": "as printed, or null",
      "strength": "e.g. 500 mg, or null",
      "expiry": "exactly as printed, e.g. EXP 09/2026, or null",
      "kind": "box | bottle | tube | inhaler | other",
      "confidence": "high | medium | low",
      "notes": "what was hard to read, or empty"
    }
  ],
  "image_notes": "one short sentence if the photo is blurry, dark or cut off, otherwise empty"
}

Rules:
- box coordinates are fractions of the photo from 0 to 1. x runs left to right, y runs top to bottom, the
  top-left corner is (0, 0). The box must fit tightly around that one package.
- If two packages overlap, give each its own box.
- name: ONLY what you can actually READ on the package. NEVER guess a medicine from its shape, colour or
  where it sits. If you cannot read it, use null and confidence "low".
- Use "high" only when the name is clearly readable, "medium" when partly readable, "low" otherwise.
- Never invent an expiry date. If you cannot read one, use null. Small text on a shelf photo is often unreadable.
- At most 30 packages."""


# ---------------------------------------------------------------- the photo
def prepare_image(raw):
    """Straighten phone-photo rotation, shrink, and re-encode as JPEG. Returns (jpeg_bytes, width, height)."""
    im = Image.open(io.BytesIO(raw))
    im = ImageOps.exif_transpose(im).convert("RGB")      # boxes must match the picture the person sees
    im.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=88)
    return out.getvalue(), im.size[0], im.size[1]


# ---------------------------------------------------------------- expiry dates (worked out here, not by the AI)
_MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_MONTHS.update({"sept": 9, "oca": 1, "şub": 2, "sub": 2, "nis": 4, "haz": 6, "tem": 7, "ağu": 8, "agu": 8,
                "eyl": 9, "eki": 10, "kas": 11, "ara": 12})


def parse_expiry(text, today=None):
    """Returns ("YYYY-MM", is_expired) or (None, None) when the date cannot be read for sure.
    A medicine is good until the end of the printed month."""
    if not text:
        return None, None
    today = today or date.today()
    t = str(text).lower()
    y = m = None
    mm = re.search(r"\b(20\d{2})\s*[-/.]\s*(0?[1-9]|1[0-2])\b", t)
    if mm:
        y, m = int(mm.group(1)), int(mm.group(2))
    if y is None:
        mm = re.search(r"\b(0?[1-9]|1[0-2])\s*[-/.]\s*(20\d{2})\b", t)
        if mm:
            m, y = int(mm.group(1)), int(mm.group(2))
    if y is None:
        mm = re.search(r"\b(0?[1-9]|1[0-2])\s*[-/.]\s*(\d{2})\b", t)
        if mm:
            m, y = int(mm.group(1)), 2000 + int(mm.group(2))
    if y is None:
        mm = re.search(r"\b([a-zçğıöşü]{3,5})[a-zçğıöşü]*\.?\s*[-/,. ]?\s*(20\d{2}|\d{2})\b", t)
        if mm and mm.group(1)[:3] in _MONTHS or (mm and mm.group(1) in _MONTHS):
            key = mm.group(1) if mm.group(1) in _MONTHS else mm.group(1)[:3]
            m = _MONTHS[key]
            yy = mm.group(2)
            y = int(yy) if len(yy) == 4 else 2000 + int(yy)
    if y is None or m is None or not (2000 <= y <= 2100):
        return None, None
    return f"{y:04d}-{m:02d}", (y, m) < (today.year, today.month)


# ---------------------------------------------------------------- checking what the AI returned
def _iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _clean_text(v, limit=80):
    if v is None:
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    if not s or s.lower() in {"null", "none", "unknown", "unreadable", "n/a", "not visible", "not readable", "-"}:
        return None
    return s[:limit]


def validate_items(raw_items, today=None):
    items = []
    for r in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(r, dict):
            continue
        box = r.get("box")
        try:
            x0, y0, x1, y1 = [min(1.0, max(0.0, float(v))) for v in box]
        except (TypeError, ValueError):
            continue
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        if (x1 - x0) < 0.02 or (y1 - y0) < 0.02:
            continue
        name = _clean_text(r.get("name"))
        conf = str(r.get("confidence", "low")).lower()
        conf = conf if conf in CONF_ORDER else "low"
        if name is None:
            conf = "low"                               # nothing readable means nothing is trusted
        expiry = _clean_text(r.get("expiry"), 40)
        parsed, expired = parse_expiry(expiry, today)
        items.append({
            "box": [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)],
            "name": name,
            "active_ingredient": _clean_text(r.get("active_ingredient")),
            "strength": _clean_text(r.get("strength"), 40),
            "expiry": expiry,
            "expiry_parsed": parsed,
            "is_expired": expired,
            "kind": str(r.get("kind", "other")).lower()[:12],
            "confidence": conf,
            "notes": _clean_text(r.get("notes"), 200) or "",
        })
    # drop near-duplicate outlines, keeping the better read
    items.sort(key=lambda i: (-CONF_ORDER[i["confidence"]], i["name"] is None))
    kept = []
    for it in items:
        if all(_iou(it["box"], k["box"]) <= 0.6 for k in kept):
            kept.append(it)
    kept = kept[:MAX_ITEMS]
    # reading order: top to bottom in rows, then left to right
    kept.sort(key=lambda i: (round(((i["box"][1] + i["box"][3]) / 2) / 0.15), (i["box"][0] + i["box"][2]) / 2))
    for n, it in enumerate(kept, 1):
        it["id"] = n
        it["needs_closeup"] = it["name"] is None or it["confidence"] == "low"
    return kept


def to_cabinet_entry(item):
    """The same shape the one-at-a-time scanner returns, so 'Check my cabinet' accepts it."""
    return {
        "drug_name": item["name"] or "Unknown",
        "active_ingredient": item["active_ingredient"],
        "dosage_strength": item["strength"],
        "expiration_date": item["expiry"],
        "expiration_parsed": item["expiry_parsed"],
        "is_expired": item["is_expired"],
        "extraction_confidence": item["confidence"],
        "confidence_notes": item["notes"] or ("Read from a whole-shelf photo" if item["confidence"] != "high" else ""),
    }


# ---------------------------------------------------------------- the AI call
def _call_claude(jpeg_bytes):
    from extraction import client, MODEL      # the same client your letter reading uses
    b64 = base64.b64encode(jpeg_bytes).decode()
    resp = client.messages.create(
        model=MODEL, max_tokens=4000,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
            {"type": "text", "text": PROMPT + language_instruction()}]}])
    return resp.content[0].text


def _parse_json(text):
    text = (text or "").strip()
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b == -1:
        raise ValueError("The photo could not be read. Please try again.")
    return json.loads(text[a:b + 1])


def find_packages(jpeg_bytes, call_model=None):
    """Returns (raw package list, image notes). Swap this one function for your own detector later."""
    data = _parse_json((call_model or _call_claude)(jpeg_bytes))
    return data.get("packages", []), str(data.get("image_notes") or "")


def scan_cabinet(image_bytes, call_model=None, today=None):
    jpeg, w, h = prepare_image(image_bytes)
    raw, notes = find_packages(jpeg, call_model)
    items = validate_items(raw, today)
    for it in items:
        it["entry"] = to_cabinet_entry(it)
    return {"items": items, "count": len(items), "image": {"width": w, "height": h}, "notes": notes[:200]}
