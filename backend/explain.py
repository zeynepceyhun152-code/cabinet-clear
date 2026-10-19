"""
explain.py - adapt a discharge explanation to how overwhelmed the reader is and how well
they understood the doctor.

How it stays safe:
  1. Plain code (style_profile) turns the two ratings into fixed style rules.
  2. The model only writes WITHIN those rules, using the extracted letter data.
  3. Plain code (check_faithfulness) then checks the result against the letter:
       - no invented medicines, no dropped medicines
       - no numbers that are not in the letter (doses, days, hours)
       - every dose and duration number from the letter is still there
       - every warning sign and every follow-up appointment is still there, copied exactly
       - no "stop / skip / double" style instructions the letter did not contain
  4. If ANY check fails, or the model output is unusable, the reader gets a plain
     deterministic explanation built straight from the letter data (fallback).

Limit: the checker verifies structure, numbers and completeness. It cannot prove that every
reworded sentence means exactly what the letter means. The reader always sees the original
warning-sign text next to the simplified version for that reason.
"""
import json
import re

from reconcile import canonical
from resources import find_resources
from lang_ctx import get_lang

# ---------------------------------------------------------------- style rules
def _clamp(v, default=3):
    try:
        v = int(v)
    except (TypeError, ValueError):
        return default
    return max(1, min(5, v))


def style_profile(stress, understanding):
    """stress: 1 (calm) to 5 (very overwhelmed). understanding: 1 (not at all) to 5 (completely)."""
    s, u = _clamp(stress), _clamp(understanding)
    overwhelmed = s >= 4
    comfortable = s <= 2 and u >= 4
    mode = "calm_short" if overwhelmed else "detailed" if comfortable else "standard"
    return {
        "mode": mode,
        "stress": s,
        "understanding": u,
        "max_sentence_words": 12 if overwhelmed else 25 if comfortable else 18,
        "max_do_now": 3 if overwhelmed else 6 if comfortable else 4,
        "include_reasons": mode == "detailed",
        "define_terms": u <= 3,
        "tone": ("calm and reassuring, one step at a time" if s >= 3
                 else "friendly and clear"),
        "level": ("very simple (about 5th grade)" if overwhelmed or u <= 2
                  else "clear (about 10th grade)" if comfortable
                  else "plain (about 8th grade)"),
        "offer_learning": u <= 3,
    }


# ---------------------------------------------------------------- prompt
_SCHEMA = """{
  "opening": "one or two sentences",
  "what_happened": "what happened, in plain language",
  "do_now": ["next step taken from the letter"],
  "medicines": [{"name": "exactly as in the letter", "what_for": "why it is used, or say the letter does not say", "how_to_take": "dose, how often, how long, exactly as in the letter"}],
  "warning_signs": [{"original": "copied exactly from the letter", "plain": "same meaning, simpler words"}],
  "follow_up": [{"appointment": "copied exactly from the letter", "when": "copied exactly from the letter", "why": "plain reason, or empty"}],
  "good_to_know": ["short items from activity restrictions or diet"]
}"""


def build_prompt(data, p):
    reasons = ("Briefly say why each medicine is used, using only what the letter says."
               if p["include_reasons"] else "Keep each medicine to one short line.")
    terms = ("If you must use a medical word, explain it in brackets right after it."
             if p["define_terms"] else "Medical words are fine if kept short.")
    good = ("Leave good_to_know as an empty list." if p["mode"] == "calm_short"
            else "good_to_know: short items from activity restrictions or diet, only if present.")
    lang_line = ""
    if get_lang() == "tr":
        lang_line = ("- Language: write ALL text in Turkish (Türkçe), in clear, formal wording. Do not translate "
                     "medicine names. Copy the fields called original, appointment, when and name exactly as "
                     "they appear in the letter data, even if they are in Turkish. Do not add emergency phone "
                     "numbers that are not in the letter.\n")
    return (
        "You are helping a family member understand a hospital discharge letter.\n\n"
        "Reader style (follow exactly):\n"
        + lang_line +
        f"- Tone: {p['tone']}\n"
        f"- Reading level: {p['level']}\n"
        f"- At most {p['max_sentence_words']} words per sentence.\n"
        f"- do_now: at most {p['max_do_now']} items, most urgent first, taken only from the letter.\n"
        f"- {reasons}\n- {terms}\n- {good}\n\n"
        "Hard rules (never break):\n"
        "1. Use ONLY the letter data below. Do not add medical facts, advice, doses, times or reasons "
        "that are not there. If the letter does not say why a medicine is used, say the letter does not say "
        "and suggest asking the pharmacist.\n"
        "2. Keep every medicine, dose, frequency, duration and number exactly as written.\n"
        "3. Include EVERY warning sign and EVERY follow-up appointment. Copy the fields called "
        "original, appointment, when and name exactly from the letter. Only plain, why, what_for and "
        "other text may be reworded.\n"
        "4. Never tell the reader to stop, skip, change or add a medicine.\n"
        "5. If extraction_confidence is not high, say what is unclear instead of guessing.\n"
        "6. Do not say how the patient feels or is doing unless the letter says so. Show calm through your "
        "wording, not by adding reassurance or opinions that are not in the letter.\n"
        "7. Do not turn vague words such as repeated, persistent, severe, frequent or a few into specific "
        "numbers or counts. Keep them as vague as the letter does.\n\n"
        "Return ONLY a JSON object with exactly this structure, no markdown:\n"
        + _SCHEMA + "\n\nLetter data:\n" + json.dumps(data, ensure_ascii=False)
    )


# ---------------------------------------------------------------- faithfulness check
_NUM = re.compile(r"\d+(?:\.\d+)?")
ALLOWED_EXTRA_NUMBERS = {"911", "112"}
_BANNED = [r"\bstop taking\b", r"\bskip (?:a|your|the) dose\b", r"\bdouble (?:the|your) dose\b",
           r"\bdon'?t need to (?:call|see)\b", r"\bsafe to (?:stop|skip|ignore)\b",
           # Turkish
           r"ilac[ıi] b[ıi]rak", r"ilac[ıi] kesin", r"dozu atla", r"dozu iki kat", r"doktoru aramanıza gerek yok",
           r"b[ıi]rakmanız güvenli"]


def _numbers(text):
    return set(_NUM.findall(str(text)))


def _norm(s):
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", str(s).lower())).strip()


def _all_text(exp):
    parts = [exp.get("opening", ""), exp.get("what_happened", "")]
    parts += [x for x in exp.get("do_now", [])]
    for m in exp.get("medicines", []):
        parts += [m.get("name", ""), m.get("what_for", ""), m.get("how_to_take", "")]
    for w in exp.get("warning_signs", []):
        parts += [w.get("original", ""), w.get("plain", "")]
    for f in exp.get("follow_up", []):
        parts += [f.get("appointment", ""), f.get("when", ""), f.get("why", "")]
    parts += list(exp.get("good_to_know", []) or [])
    return [str(p) for p in parts if p]


def check_faithfulness(exp, data):
    """Return a list of problems. An empty list means the explanation passed every check."""
    if not isinstance(exp, dict):
        return ["explanation is not an object"]
    shape = {"opening": str, "what_happened": str, "do_now": list, "medicines": list,
             "warning_signs": list, "follow_up": list}
    problems = [f"missing or wrong type: {k}" for k, t in shape.items() if not isinstance(exp.get(k), t)]
    if problems:
        return problems
    if not all(isinstance(x, str) for x in exp["do_now"]):
        return ["do_now must be a list of text"]
    if not all(isinstance(m, dict) for m in exp["medicines"]) or \
       not all(isinstance(w, dict) for w in exp["warning_signs"]) or \
       not all(isinstance(f, dict) for f in exp["follow_up"]):
        return ["list items must be objects"]

    src_meds = data.get("medications") or []
    src_text = json.dumps(data, ensure_ascii=False)

    # medicines: none invented, none dropped, numbers per medicine
    src_by_base = {}
    for m in src_meds:
        src_by_base.setdefault(canonical(m.get("name"))[0], []).append(m)
    seen = set()
    for m in exp["medicines"]:
        base = canonical(m.get("name"))[0]
        if base not in src_by_base:
            problems.append(f"invented medicine: {m.get('name')}")
            continue
        seen.add(base)
        out_nums = _numbers(f"{m.get('what_for', '')} {m.get('how_to_take', '')}")
        for sm in src_by_base[base]:
            allowed = _numbers(" ".join(str(sm.get(k) or "") for k in ("name", "dosage", "frequency", "duration", "purpose")))
            must = _numbers(f"{sm.get('dosage') or ''} {sm.get('duration') or ''}")
            if out_nums <= allowed and must <= out_nums:
                break
        else:
            problems.append(f"dose, duration or number mismatch for {m.get('name')}")
    for base in src_by_base:
        if base not in seen:
            problems.append(f"dropped medicine: {src_by_base[base][0].get('name')}")

    # warning signs: every one present, copied exactly
    src_signs = sorted(_norm(s) for s in (data.get("warning_signs") or []))
    out_signs = sorted(_norm(w.get("original", "")) for w in exp["warning_signs"])
    for s in src_signs:
        if s not in out_signs:
            problems.append(f"dropped or altered warning sign: {s}")
    if len(out_signs) > len(src_signs):
        problems.append("extra warning signs that are not in the letter")

    # follow-ups: every one present, copied exactly
    src_fu = sorted((_norm(f.get("type", "")), _norm(f.get("timeframe", ""))) for f in (data.get("follow_up_appointments") or []))
    out_fu = sorted((_norm(f.get("appointment", "")), _norm(f.get("when", ""))) for f in exp["follow_up"])
    for f in src_fu:
        if f not in out_fu:
            problems.append(f"dropped or altered follow-up: {f[0]}")
    if len(out_fu) > len(src_fu):
        problems.append("extra follow-ups that are not in the letter")

    # numbers anywhere must come from the letter
    extra = _numbers(" ".join(_all_text(exp))) - _numbers(src_text) - ALLOWED_EXTRA_NUMBERS
    if extra:
        problems.append("numbers not in the letter: " + ", ".join(sorted(extra)))

    # instructions the letter did not contain
    out_joined = " ".join(_all_text(exp)).lower()
    for pat in _BANNED:
        if re.search(pat, out_joined) and not re.search(pat, src_text.lower()):
            problems.append("gives an instruction that is not in the letter")
            break
    return problems


# ---------------------------------------------------------------- fallback
def fallback_explanation(data, p):
    """Plain, deterministic explanation straight from the letter data. Never fails."""
    short = p["mode"] == "calm_short"
    meds = []
    for m in data.get("medications") or []:
        how = ", ".join(str(x) for x in (m.get("dosage"), m.get("frequency"), m.get("duration")) if x)
        meds.append({
            "name": m.get("name") or "Unknown medicine",
            "what_for": m.get("purpose") or "Your letter does not say what this is for. Ask your pharmacist.",
            "how_to_take": how or "Your letter does not say. Ask your pharmacist.",
        })
    fups = [{"appointment": f.get("type", ""), "when": f.get("timeframe", ""),
             "why": "" if short else (f.get("reason") or "")} for f in (data.get("follow_up_appointments") or [])]
    do_now = [f"{f['appointment']}: {f['when']}" for f in fups][: p["max_do_now"]]
    return {
        "opening": "Here is what your letter says, one part at a time.",
        "what_happened": data.get("diagnosis_summary") or "Your letter did not include a clear summary.",
        "do_now": do_now,
        "medicines": meds,
        "warning_signs": [{"original": w, "plain": w} for w in (data.get("warning_signs") or [])],
        "follow_up": fups,
        "good_to_know": [] if short else list(data.get("activity_restrictions") or []),
    }


# ---------------------------------------------------------------- model call + main
def _parse_json(text):
    text = (text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


def _call_claude(prompt):
    from extraction import client, MODEL  # same client your letter reading already uses
    resp = client.messages.create(model=MODEL, max_tokens=2000,
                                  messages=[{"role": "user", "content": prompt}])
    return resp.content[0].text


def generate_explanation(data, stress, understanding, call_model=None):
    p = style_profile(stress, understanding)
    exp, problems = None, []
    try:
        raw = (call_model or _call_claude)(build_prompt(data, p))
        exp = _parse_json(raw)
        problems = check_faithfulness(exp, data)
    except Exception as e:
        exp, problems = None, [f"model output unusable: {e}"]
    fallback = exp is None or bool(problems)
    if fallback:
        exp = fallback_explanation(data, p)
    notice = None
    if (data.get("extraction_confidence") or "high") != "high":
        notes = data.get("confidence_notes") or "some parts were hard to read"
        notice = f"Some of your letter was hard to read ({notes}). Please check this against the original and ask your care team."
    return {"explanation": exp, "profile": p, "fallback": fallback, "problems": problems, "notice": notice,
            "resources": find_resources(data)}


# ---------------------------------------------------------------- readability (for evaluation)
def _syllables(word):
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    n = len(re.findall(r"[aeiouy]+", w))
    if w.endswith("e") and not w.endswith("le") and n > 1:
        n -= 1
    return max(1, n)


def sentences(strings):
    out = []
    for s in strings:
        out += [x for x in re.split(r"[.!?]+", s) if x.strip()]
    return out


def readability(exp):
    """Return (average words per sentence, Flesch-Kincaid grade) over the explanation text."""
    sents = sentences(_all_text(exp))
    words = re.findall(r"[A-Za-z']+", " ".join(sents))
    if not sents or not words:
        return 0.0, 0.0
    syll = sum(_syllables(w) for w in words)
    avg = len(words) / len(sents)
    return avg, 0.39 * avg + 11.8 * syll / len(words) - 15.59
