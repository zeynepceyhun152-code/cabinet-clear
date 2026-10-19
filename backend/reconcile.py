"""
reconcile.py - compare a "before" medication list with an "after" (discharge) list.

Design goals (same philosophy as crossreference.py):
  * Deterministic and auditable. No LLM decides what changed.
  * Conservative. If something is ambiguous, the answer is "needs_review",
    never a confident guess.
  * Every finding carries the source text that supports it, plus a question
    the family can take to a doctor or pharmacist.

Each medication is a dict like the ones extraction.py already returns:
    {"name": "...", "dosage": "...", "frequency": "...", "duration": "...", "purpose": "..."}
Optional keys: "source_text" (exact text from the document) and "id" (used by tests).

Public API:
    compare_med_lists(before, after) -> dict
    naive_compare(before, after)     -> dict   (exact-string baseline, for evaluation)
"""
import math
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher

# Statuses
ADDED = "added"
STOPPED = "stopped"
DOSE_CHANGED = "dose_changed"
FREQ_CHANGED = "frequency_changed"
BOTH_CHANGED = "dose_and_frequency_changed"
UNCHANGED = "unchanged"
NEEDS_REVIEW = "needs_review"

FUZZY_THRESHOLD = 0.85  # name similarity that triggers "please confirm", never an auto-match

# ---------------------------------------------------------------- names
# Curated on purpose. Do NOT merge the big FDA sample here: it contains junk mappings.
BRAND_TO_GENERIC = {
    "tylenol": "acetaminophen", "paracetamol": "acetaminophen", "calpol": "acetaminophen",
    "advil": "ibuprofen", "motrin": "ibuprofen", "nurofen": "ibuprofen",
    "aleve": "naproxen", "benadryl": "diphenhydramine", "claritin": "loratadine",
    "zyrtec": "cetirizine", "pepcid": "famotidine", "prilosec": "omeprazole",
    "ventolin": "albuterol", "proair": "albuterol", "proventil": "albuterol",
    "flovent": "fluticasone", "zithromax": "azithromycin",
    "augmentin": "amoxicillin clavulanate", "amoxil": "amoxicillin",
    "lasix": "furosemide", "glucophage": "metformin", "zestril": "lisinopril",
    "prinivil": "lisinopril", "coumadin": "warfarin", "synthroid": "levothyroxine",
    "lopressor": "metoprolol tartrate", "toprol": "metoprolol succinate",
}
PHRASES = {
    "clavulanic acid": "clavulanate",
    "vitamin d3": "vitamin d", "vitamin d2": "vitamin d", "cholecalciferol": "vitamin d",
}
SALTS = {
    "tartrate", "succinate", "hydrochloride", "hcl", "sodium", "potassium", "sulfate",
    "maleate", "besylate", "mesylate", "acetate", "citrate", "phosphate", "bromide",
    "propionate",
}
SALT_ALIASES = {"hcl": "hydrochloride"}
FORM_WORDS = {
    "tablet", "tablets", "tab", "tabs", "capsule", "capsules", "cap", "caps",
    "inhaler", "drops", "drop", "solution", "suspension", "syrup", "oral",
    "liquid", "cream", "ointment", "chewable",
}
EXT_RELEASE = {"er", "xl", "xr", "sr", "cr", "la", "extended", "release"}


def canonical(name):
    """Return (base, salts, extended_release) for a medication name."""
    s = (name or "").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    for k, v in PHRASES.items():
        s = s.replace(k, v)
    s = re.sub(r"[/,\-_+&]", " ", s)
    toks = [t for t in s.split() if not re.search(r"\d", t) and t not in FORM_WORDS]
    er = any(t in EXT_RELEASE for t in toks)
    toks = [t for t in toks if t not in EXT_RELEASE]

    phrase = " ".join(toks)
    if phrase in BRAND_TO_GENERIC:
        toks = BRAND_TO_GENERIC[phrase].split()
    elif toks and toks[0] in BRAND_TO_GENERIC:
        toks = BRAND_TO_GENERIC[toks[0]].split() + toks[1:]

    salts = frozenset(SALT_ALIASES.get(t, t) for t in toks if t in SALTS)
    base_toks = sorted(t for t in toks if t not in SALTS)
    return " ".join(base_toks), salts, er


# ---------------------------------------------------------------- doses
_CONC_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|mcg|ug|g)\s*/\s*(\d+(?:\.\d+)?)?\s*ml")
_DOSE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mcg|ug|mg|g|ml|iu|units?|puffs?|drops?|tablets?|tabs?|capsules?|caps?)\b"
)
_MASS = {"mg": 1.0, "mcg": 0.001, "ug": 0.001, "g": 1000.0}
_COUNT = {"puff": "puff", "puffs": "puff", "drop": "drop", "drops": "drop",
          "tablet": "tablet", "tablets": "tablet", "tab": "tablet", "tabs": "tablet",
          "capsule": "capsule", "capsules": "capsule", "cap": "capsule", "caps": "capsule",
          "unit": "unit", "units": "unit", "iu": "IU", "ml": "ml"}


def _dose_from_text(text):
    t = (text or "").lower()
    m = _CONC_RE.search(t)
    if m:
        denom = float(m.group(3)) if m.group(3) else 1.0
        return ("mg/ml", float(m.group(1)) * _MASS[m.group(2)] / denom)
    m = _DOSE_RE.search(t)
    if not m:
        return None
    val, unit = float(m.group(1)), m.group(2)
    if unit in _MASS:
        return ("mg", val * _MASS[unit])
    return (_COUNT[unit], val)


def parse_dose(med):
    """Dose from the dosage field, falling back to the frequency / source text."""
    for field in ("dosage", "frequency", "source_text"):
        d = _dose_from_text(med.get(field))
        if d:
            return d
    return None


_COUNT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:tablets?|tabs?|capsules?|caps?)\b")


def _pill_count(med):
    """Number of tablets/capsules per dose if stated in the frequency or source text."""
    text = " ".join(str(med.get(f) or "") for f in ("frequency", "source_text")).lower()
    m = _COUNT_RE.search(text)
    return float(m.group(1)) if m else None


def _is_multi_step(med):
    """Tapers or several doses in one entry cannot be compared safely as a single dose."""
    text = " ".join(str(med.get(f) or "") for f in ("dosage", "frequency", "source_text")).lower()
    return bool(re.search(r"\bthen\b|taper|\bfollowed by\b", text)) or len(_DOSE_RE.findall(str(med.get("dosage") or "").lower())) > 1


# ---------------------------------------------------------------- frequency
def parse_frequency(med):
    """Return {"lo","hi","prn"} doses per day, or None if no schedule or PRN info is found."""
    text = " ".join(str(med.get(f) or "") for f in ("frequency", "source_text")).lower()
    if not text.strip():
        return None
    prn = bool(re.search(r"\bprn\b|as needed|when needed|if needed", text))
    lo = hi = None

    m = re.search(r"every\s+(\d+(?:\.\d+)?)\s*(?:-|to|\u2013)\s*(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b", text)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        lo, hi = 24 / max(a, b), 24 / min(a, b)
    else:
        m = (re.search(r"every\s+(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b", text)
             or re.search(r"\bq\s*(\d+(?:\.\d+)?)\s*h\b", text))
        if m:
            lo = hi = 24 / float(m.group(1))
        elif re.search(r"every other day|\bqod\b", text):
            lo = hi = 0.5
        elif re.search(r"weekly|once a week|every week|once per week", text):
            lo = hi = 1 / 7
        elif re.search(r"four times|\bqid\b|\b4\s*(?:x|times)", text):
            lo = hi = 4.0
        elif re.search(r"three times|\btid\b|\b3\s*(?:x|times)", text):
            lo = hi = 3.0
        elif re.search(r"twice|\bbid\b|two times|\b2\s*(?:x|times)", text):
            lo = hi = 2.0
        elif re.search(r"once|daily|\bqd\b|every day|each day|every morning|bedtime|nightly|\b1\s*x", text):
            lo = hi = 1.0
    if lo is None and not prn:
        return None
    return {"lo": lo, "hi": hi, "prn": prn}


# ---------------------------------------------------------------- helpers
def _same(x, y):
    return math.isclose(x, y, rel_tol=1e-6, abs_tol=1e-9)


def _fmt_dose(d):
    return f"{d[1]:g} {d[0]}"


def _fmt_freq(f):
    if f["lo"] is None:
        return "as needed"
    per_day = f"{f['lo']:g}" if _same(f["lo"], f["hi"]) else f"{f['lo']:g}-{f['hi']:g}"
    return f"{per_day}x/day" + (", as needed" if f["prn"] else "")


def _evidence(med):
    if med.get("source_text"):
        return med["source_text"]
    parts = [med.get("name") or "", med.get("dosage") or "", med.get("frequency") or ""]
    return " - ".join(p for p in parts if p).strip()


def _brief(med):
    return {k: med.get(k) for k in ("name", "dosage", "frequency", "duration")}


def _ids(*meds):
    return [m.get("id") for m in meds if m is not None and m.get("id") is not None]


def _finding(status, before, after, details=None, question=None):
    meds = [m for m in (before or []) + (after or [])]
    name = (after[0] if after else before[0]).get("name") or "Unknown medication"
    return {
        "drug": name,
        "status": status,
        "before": [_brief(m) for m in (before or [])],
        "after": [_brief(m) for m in (after or [])],
        "evidence": {"before": [_evidence(m) for m in (before or [])],
                     "after": [_evidence(m) for m in (after or [])]},
        "details": details or [],
        "question": question,
        "ids": _ids(*meds),
    }


# ---------------------------------------------------------------- pair comparison
def _compare_pair(b, a, kb, ka):
    review, details = [], []
    if kb[1] and ka[1] and kb[1] != ka[1]:
        review.append(f"different form/salt ({', '.join(sorted(kb[1]))} vs {', '.join(sorted(ka[1]))})")
    if kb[2] != ka[2]:
        review.append("immediate-release vs extended-release may differ")

    db, da = parse_dose(b), parse_dose(a)
    dose_changed = False
    if _is_multi_step(b) or _is_multi_step(a):
        review.append("tapering or multi-step dosing: compare the full instructions")
        db = da = None
    cb, ca = _pill_count(b), _pill_count(a)
    if db is not None and da is not None and db[0] in ("mg", "IU", "unit", "mg/ml"):
        if (cb is None) != (ca is None) and (cb or ca) != 1:
            review.append("number of tablets per dose is stated on only one list")
            db = da = None
        else:
            db, da = (db[0], db[1] * (cb or 1)), (da[0], da[1] * (ca or 1))
    if db is None or da is None:
        if not any("tapering" in r or "tablets per dose" in r for r in review):
            review.append("dose missing or unreadable on one list")
    elif db[0] != da[0]:
        review.append(f"doses use different units ({_fmt_dose(db)} vs {_fmt_dose(da)})")
    elif not _same(db[1], da[1]):
        dose_changed = True
        details.append(f"dose {_fmt_dose(db)} -> {_fmt_dose(da)}")

    fb, fa = parse_frequency(b), parse_frequency(a)
    freq_changed = False
    if fb is None or fa is None:
        review.append("how often to take it is missing or unreadable on one list")
    elif (fb["lo"] is None) != (fa["lo"] is None):
        review.append("one list gives a schedule and the other only says 'as needed'")
    else:
        same_sched = (fb["lo"] is None) or (_same(fb["lo"], fa["lo"]) and _same(fb["hi"], fa["hi"]))
        if not same_sched or fb["prn"] != fa["prn"]:
            freq_changed = True
            details.append(f"frequency {_fmt_freq(fb)} -> {_fmt_freq(fa)}")

    name = a.get("name") or b.get("name")
    if review:
        return _finding(NEEDS_REVIEW, [b], [a], details + review,
                        f"Please ask a pharmacist to confirm {name}: {'; '.join(review)}.")
    if dose_changed and freq_changed:
        return _finding(BOTH_CHANGED, [b], [a], details,
                        f"The dose and schedule for {name} both changed. What is the reason?")
    if dose_changed:
        return _finding(DOSE_CHANGED, [b], [a], details,
                        f"The dose of {name} changed. What is the reason, and should the old supply still be used?")
    if freq_changed:
        return _finding(FREQ_CHANGED, [b], [a], details,
                        f"How often to take {name} changed. What is the reason?")
    return _finding(UNCHANGED, [b], [a])


# ---------------------------------------------------------------- main API
def compare_med_lists(before, after, fuzzy_threshold=FUZZY_THRESHOLD):
    before, after = list(before or []), list(after or [])
    kb = [canonical(m.get("name")) for m in before]
    ka = [canonical(m.get("name")) for m in after]
    findings, used_b, used_a = [], set(), set()

    # 0. entries with no readable name
    for lst, keys, used, side in ((before, kb, used_b, "before"), (after, ka, used_a, "after")):
        for i, k in enumerate(keys):
            if not k[0]:
                used.add(i)
                m = lst[i]
                findings.append(_finding(
                    NEEDS_REVIEW, [m] if side == "before" else [], [m] if side == "after" else [],
                    ["medication name missing or unreadable"],
                    "A medication name could not be read. Please check the original document."))

    # 1. same base name in both lists
    b_idx, a_idx = defaultdict(list), defaultdict(list)
    for i, k in enumerate(kb):
        if i not in used_b:
            b_idx[k[0]].append(i)
    for i, k in enumerate(ka):
        if i not in used_a:
            a_idx[k[0]].append(i)
    for base in sorted(set(b_idx) & set(a_idx)):
        bs, as_ = b_idx[base], a_idx[base]
        if len(bs) == 1 and len(as_) == 1:
            findings.append(_compare_pair(before[bs[0]], after[as_[0]], kb[bs[0]], ka[as_[0]]))
        else:
            findings.append(_finding(
                NEEDS_REVIEW, [before[i] for i in bs], [after[i] for i in as_],
                [f"{base} appears more than once on a list"],
                f"{base.title()} appears more than once. Please ask a pharmacist which entries apply."))
        used_b.update(bs)
        used_a.update(as_)

    # 2a. one drug contains the other's ingredient (e.g. lisinopril vs lisinopril-HCTZ): ask
    for i in range(len(before)):
        for j in range(len(after)):
            if i in used_b or j in used_a:
                continue
            tb, ta = set(kb[i][0].split()), set(ka[j][0].split())
            if tb and ta and (tb < ta or ta < tb):
                used_b.add(i)
                used_a.add(j)
                nb, na = before[i].get("name"), after[j].get("name")
                findings.append(_finding(
                    NEEDS_REVIEW, [before[i]], [after[j]],
                    [f"'{nb}' and '{na}' share an ingredient"],
                    f"'{na}' shares an ingredient with '{nb}'. Is one replacing the other, and should they never be taken together?"))

    # 2b. look-alike names: ask, never auto-match
    cands = []
    for i in range(len(before)):
        for j in range(len(after)):
            if i in used_b or j in used_a:
                continue
            r = SequenceMatcher(None, kb[i][0], ka[j][0]).ratio()
            if r >= fuzzy_threshold:
                cands.append((r, i, j))
    for r, i, j in sorted(cands, reverse=True):
        if i in used_b or j in used_a:
            continue
        used_b.add(i)
        used_a.add(j)
        nb, na = before[i].get("name"), after[j].get("name")
        findings.append(_finding(
            NEEDS_REVIEW, [before[i]], [after[j]],
            [f"'{nb}' and '{na}' look similar but are not identical"],
            f"Is '{nb}' the same medicine as '{na}'? Please confirm with a pharmacist."))

    # 3. what is left was removed or added
    for i, m in enumerate(before):
        if i not in used_b:
            findings.append(_finding(
                STOPPED, [m], [], ["on the earlier list, not on the new list"],
                f"{m.get('name')} is not on the new list. Was it stopped on purpose, and what should be done with the supply at home?"))
    for j, m in enumerate(after):
        if j not in used_a:
            findings.append(_finding(
                ADDED, [], [m], ["new on the discharge list"],
                f"{m.get('name')} is new. What is it for, and for how long should it be taken?"))

    order = {NEEDS_REVIEW: 0, STOPPED: 1, ADDED: 2, BOTH_CHANGED: 3, DOSE_CHANGED: 4, FREQ_CHANGED: 5, UNCHANGED: 6}
    findings.sort(key=lambda f: (order[f["status"]], f["drug"].lower()))
    counts = Counter(f["status"] for f in findings)
    return {
        "summary": {s: counts.get(s, 0) for s in order},
        "findings": findings,
        "questions_for_clinician": [f["question"] for f in findings if f["question"]],
        "important_note": ("This compares what the documents say. It does not decide which treatment is "
                           "correct. Confirm every change with your doctor or pharmacist."),
    }


# ---------------------------------------------------------------- baseline
def naive_compare(before, after):
    """Exact-string baseline: what you get with no normalisation at all."""
    norm = lambda s: (s or "").strip().lower()
    bm = {norm(m.get("name")): m for m in before}
    am = {norm(m.get("name")): m for m in after}
    findings = []
    for n, m in bm.items():
        if n not in am:
            findings.append({"status": STOPPED, "ids": _ids(m)})
    for n, m in am.items():
        if n not in bm:
            findings.append({"status": ADDED, "ids": _ids(m)})
            continue
        b = bm[n]
        d = norm(b.get("dosage")) != norm(m.get("dosage"))
        f = norm(b.get("frequency")) != norm(m.get("frequency"))
        status = BOTH_CHANGED if d and f else DOSE_CHANGED if d else FREQ_CHANGED if f else UNCHANGED
        findings.append({"status": status, "ids": _ids(b, m)})
    return {"findings": findings}
