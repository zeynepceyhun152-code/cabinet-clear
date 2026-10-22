"""
eval_blind.py - scores the medication comparison on test cases written by OTHER people.

Why: the original 50-medicine test was written by the developer, so it mostly shows the rules pass the cases their
author imagined. This script runs cases that outsiders wrote without seeing the app, through the same steps a user's
lists go through (typed list -> parsed -> compared), and reports every mistake.

Usage (from the backend folder):
    python3 eval_blind.py                  # real run: uses the AI parser, like the app does (needs your API key in .env)
    python3 eval_blind.py --parser simple  # offline practice run with a basic parser (for checking the script only)
    python3 eval_blind.py --dir blind_cases --out blind_results.md

Rules of an honest run: freeze the code first (git tag), run it ONCE on the final cases, and publish the result as it is.
"""
import argparse
import glob
import os
import random
import re
import subprocess
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STATUSES = {"added", "stopped", "dose_changed", "frequency_changed", "dose_and_frequency_changed", "unchanged", "needs_review"}


# ---------------------------------------------------------------- reading the files people send back
def norm_status(text):
    """Turns the words a person wrote ('dose changed', 'new', 'ask pharmacist'...) into the app's status names."""
    t = re.sub(r"[^a-z ]", " ", str(text).lower())
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return None
    if any(w in t for w in ("pharmac", "unsure", "review", "not sure", "unclear", "ask")):
        return "needs_review"
    has_dose = "dose" in t or "dosage" in t or "strength" in t
    has_freq = any(w in t for w in ("frequen", "schedule", "how often", "timing"))
    if has_dose and has_freq:
        return "dose_and_frequency_changed"
    if has_dose:
        return "dose_changed"
    if has_freq:
        return "frequency_changed"
    if any(w in t for w in ("new", "start", "add")):
        return "added"
    if any(w in t for w in ("stop", "discontinu", "remov", "no longer")):
        return "stopped"
    if any(w in t for w in ("same", "unchang", "no change", "continue", "identical")):
        return "unchanged"
    return None


def _items(lines):
    out = []
    for ln in lines:
        s = ln.strip()
        s = re.sub(r"^(?:[-*•–]|\d+[.)])\s*", "", s)
        if s:
            out.append(s)
    return out


def parse_case_file(path):
    """Returns (cases, problems). Each case: {id, author, before:[text], after:[text], expected:[(name, status)]}."""
    text = open(path, encoding="utf-8").read()
    author = None
    m = re.search(r"^\s*AUTHOR\s*:\s*(.+)$", text, re.M | re.I)
    if m:
        author = m.group(1).strip()
    cases, problems = [], []
    blocks = re.split(r"^\s*CASE\s+(\S+)\s*$", text, flags=re.M | re.I)
    for i in range(1, len(blocks), 2):
        cid, body = blocks[i], blocks[i + 1]
        label = f"{os.path.basename(path)} case {cid}"
        sec = {"before": [], "after": [], "expected": []}
        seen = set()
        cur = None
        for ln in body.split("\n"):
            head = re.match(r"^\s*(BEFORE|AFTER|EXPECTED|NOTES?)\s*:?\s*(.*)$", ln, re.I)
            if head:
                name = head.group(1).lower()
                cur = {"before": "before", "after": "after", "expected": "expected"}.get(name)
                if cur:
                    seen.add(cur)
                if cur and head.group(2).strip():
                    sec[cur].append(head.group(2))
                continue
            if ln.strip().startswith("#") or ln.strip().startswith("=") or ln.strip().startswith("---"):
                continue
            if cur:
                sec[cur].append(ln)
        before, after = _items(sec["before"]), _items(sec["after"])
        if not before and not after and not _items(sec["expected"]):
            continue                                       # an unused, blank case from the template: not a problem
        missing = [n.upper() for n in ("before", "after", "expected") if n not in seen]
        if missing:
            problems.append(f"{label}: is missing the {' and '.join(missing)} section"); continue
        none_words = {"none", "nothing", "n/a", "na", "no medicines", "no medications", "no meds"}
        before = [x for x in before if x.lower().strip(". ") not in none_words]
        after = [x for x in after if x.lower().strip(". ") not in none_words]
        raw_b, raw_a = _items(sec["before"]), _items(sec["after"])
        if (not raw_b) or (not raw_a):
            problems.append(f"{label}: the {'BEFORE' if not raw_b else 'AFTER'} list is empty (write 'none' if there were no medicines)"); continue
        expected = []
        bad = False
        for e in _items(sec["expected"]):
            parts = re.split(r"\s*[:=]\s*|\s+[-–]\s+", e, maxsplit=1)
            if len(parts) != 2 or norm_status(parts[1]) is None:
                problems.append(f"{label}: could not read the EXPECTED line '{e}'")
                bad = True
                continue
            expected.append((parts[0].strip(), norm_status(parts[1])))
        if not expected:
            problems.append(f"{label}: has no EXPECTED lines"); continue
        if bad:
            continue
        cases.append({"id": f"{os.path.splitext(os.path.basename(path))[0]}-{cid}", "author": author or os.path.splitext(os.path.basename(path))[0],
                      "before": before, "after": after, "expected": expected})
    return cases, problems


# ---------------------------------------------------------------- turning typed lines into medicines
_UNIT = r"(?:mg|mcg|µg|g|ml|mL|iu|IU|units?|puffs?|tablets?|tabs?|caps?|capsules?|drops?|%)"


def simple_parse(lines):
    """A basic offline parser, only for practice runs. The real run uses the same AI parser as the app."""
    meds = []
    for ln in lines:
        m = re.search(r"\d", ln)
        if not m:
            meds.append({"name": ln.strip(), "dosage": None, "frequency": None}); continue
        name = ln[:m.start()].strip(" -,:")
        rest = ln[m.start():]
        d = re.match(r"(\d+(?:\.\d+)?\s*" + _UNIT + r"(?:\s*/\s*\d+(?:\.\d+)?\s*" + _UNIT + r")?)", rest, re.I)
        dosage = d.group(1) if d else None
        freq = rest[d.end():].strip(" ,;-") if d else rest
        meds.append({"name": name or ln.strip(), "dosage": dosage, "frequency": freq or None})
    return meds


def ai_parse(lines):
    from dotenv import load_dotenv
    load_dotenv()
    from extraction import extract_from_text
    data = extract_from_text("\n".join(lines))
    return data.get("medications", []) or []


# ---------------------------------------------------------------- scoring
def _canon_set(finding, canonical):
    names = [finding.get("drug")] + [m.get("name") for m in finding.get("before", []) + finding.get("after", [])]
    return {canonical(n) for n in names if n}


def find_finding(expected_name, findings, canonical):
    key = canonical(expected_name)
    for f in findings:
        if key in _canon_set(f, canonical):
            return f
    for f in findings:                      # a person may write 'Metformin' where the list says 'Metformin ER'
        if any(key and (key in c or c in key) for c in _canon_set(f, canonical) if c):
            return f
    return None


def classify(expected, got):
    """expected and got are status names; got is None when the app reported nothing about that medicine."""
    if got is None:
        return "not_found" if expected == "unchanged" else "missed_change"
    if got == expected:
        return "exact"
    if expected == "needs_review":
        return "overconfident"                       # a person said 'ask a pharmacist', the app sounded sure
    if expected == "unchanged":
        return "extra_caution" if got == "needs_review" else "false_alarm"
    if got == "needs_review":
        return "flagged_for_pharmacist"             # a real change, and the app said to check it: safe
    if got == "unchanged":
        return "missed_change"                       # the dangerous mistake
    return "wrong_change_type"                       # saw a change, named it differently


def score_case(case, parser, compare, canonical):
    before = parser(case["before"])
    after = parser(case["after"])
    result = compare(before, after)
    findings = result.get("findings", [])
    rows = []
    for name, exp in case["expected"]:
        f = find_finding(name, findings, canonical)
        got = f["status"] if f else None
        rows.append({"case": case["id"], "author": case["author"], "drug": name, "expected": exp, "got": got, "outcome": classify(exp, got),
                     "before": case["before"], "after": case["after"]})
    return rows


def metrics(rows):
    n = len(rows)
    c = lambda *o: sum(1 for r in rows if r["outcome"] in o)
    changes = [r for r in rows if r["expected"] not in ("unchanged",)]
    detected = [r for r in changes if r["outcome"] in ("exact", "flagged_for_pharmacist", "wrong_change_type", "overconfident")]
    unchanged = [r for r in rows if r["expected"] == "unchanged"]
    return {
        "n": n, "exact": c("exact"), "flagged": c("flagged_for_pharmacist"), "extra_caution": c("extra_caution"),
        "missed": c("missed_change"), "false_alarm": c("false_alarm"), "wrong_type": c("wrong_change_type"),
        "overconfident": c("overconfident"), "not_found": c("not_found"),
        "exact_rate": c("exact") / n if n else float("nan"),
        "change_detection": len(detected) / len(changes) if changes else float("nan"), "n_changes": len(changes),
        "false_alarm_rate": c("false_alarm") / len(unchanged) if unchanged else float("nan"), "n_unchanged": len(unchanged),
    }


def bootstrap(rows, key, n_boot=2000, seed=0):
    """95% range by re-sampling whole cases (a medicine in the same case is not independent of its neighbours)."""
    by_case = {}
    for r in rows:
        by_case.setdefault(r["case"], []).append(r)
    cases = list(by_case.values())
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot if cases else 0):
        sample = [r for _ in cases for r in cases[rng.randrange(len(cases))]]
        v = metrics(sample)[key]
        if v == v:
            vals.append(v)
    vals.sort()
    return (vals[int(0.025 * (len(vals) - 1))], vals[int(0.975 * (len(vals) - 1))]) if vals else (float("nan"), float("nan"))


def pct(x):
    return "n/a" if x != x else f"{100 * x:.0f}%"


WORDS = {"exact": "correct", "flagged_for_pharmacist": "safe: told the person to ask a pharmacist", "extra_caution": "extra caution (said ask a pharmacist)",
         "missed_change": "MISSED a real change", "false_alarm": "false alarm", "wrong_change_type": "saw a change but named it differently",
         "overconfident": "sounded sure where a person said to ask a pharmacist", "not_found": "medicine not found in the results"}


def report(rows, parser_name, problems):
    m = metrics(rows)
    authors = sorted({r["author"] for r in rows})
    cases = sorted({r["case"] for r in rows})
    commit = ""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))).stdout.strip()
    except Exception:
        pass
    lo1, hi1 = bootstrap(rows, "exact_rate")
    lo2, hi2 = bootstrap(rows, "change_detection")
    few = len(cases) < 5
    rng1 = "too few cases for a range" if few else f"{pct(lo1)} to {pct(hi1)}"
    rng2 = "too few cases for a range" if few else f"{pct(lo2)} to {pct(hi2)}"
    out = [f"# Medication comparison: test on cases written by other people", "",
           f"- Cases: **{len(cases)}**, written by **{len(authors)}** {'person' if len(authors) == 1 else 'people'} ({', '.join(authors)})",
           f"- Medicines scored: **{m['n']}** ({m['n_changes']} with a real change, {m['n_unchanged']} unchanged)",
           f"- Parser: {'the same AI parser the app uses' if parser_name == 'claude' else 'a basic offline parser (practice run, not a real result)'}",
           f"- Date: {date.today().isoformat()}" + (f" | code version: `{commit}`" if commit else ""), "",
           "| Measure | Result | 95% range |", "|---|---|---|",
           f"| Exact answer correct | {m['exact']} of {m['n']} ({pct(m['exact_rate'])}) | {rng1} |",
           f"| Real changes noticed (including 'ask a pharmacist') | {pct(m['change_detection'])} of {m['n_changes']} | {rng2} |",
           f"| Real changes MISSED (said unchanged or not found) | {m['missed']} | |",
           f"| False alarms (said changed, person said unchanged) | {m['false_alarm']} | |",
           f"| Said 'ask a pharmacist' when a change was clear | {m['flagged']} | |",
           f"| Named the change type differently | {m['wrong_type']} | |", ""]
    bad = [r for r in rows if r["outcome"] not in ("exact",)]
    out.append(f"## Every disagreement ({len(bad)})" if bad else "## Every disagreement (none)")
    for r in bad:
        out += ["", f"- **{r['drug']}** ({r['case']}): person expected *{r['expected'].replace('_', ' ')}*, app said *{(r['got'] or 'nothing').replace('_', ' ')}* — {WORDS[r['outcome']]}",
                f"  - Before: {'; '.join(r['before'])}", f"  - After: {'; '.join(r['after'])}"]
    if problems:
        out += ["", "## Files that could not be fully read"] + [f"- {p}" for p in problems]
    if parser_name == "claude":
        out += ["", "_Cases were written by people who had not seen the app. The results above are reported as they came out, without changing the rules to fit them._"]
    else:
        out += ["", "**PRACTICE RUN. This used a basic offline parser, so it is not a result to publish. Run it without `--parser simple` on the final cases.**"]
    return "\n".join(out), m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="blind_cases")
    ap.add_argument("--parser", choices=["claude", "simple"], default="claude")
    ap.add_argument("--out", default="blind_results.md")
    a = ap.parse_args()
    files = [f for f in sorted(glob.glob(os.path.join(a.dir, "*.txt"))) if not os.path.basename(f).upper().startswith(("TEMPLATE", "EXAMPLE", "README"))]
    if not files:
        print(f"No case files found in {a.dir}/ (files named TEMPLATE or EXAMPLE are skipped). Put the files people send back in that folder.")
        return 1
    from reconcile import compare_med_lists, canonical
    cases, problems = [], []
    for f in files:
        c, p = parse_case_file(f)
        cases += c; problems += p
    if not cases:
        print("No readable cases.\n" + "\n".join(problems)); return 1
    parser = ai_parse if a.parser == "claude" else simple_parse
    rows = []
    for case in cases:
        rows += score_case(case, parser, compare_med_lists, canonical)
    text, m = report(rows, a.parser, problems)
    open(a.out, "w", encoding="utf-8").write(text + "\n")
    print(text)
    print(f"\nSaved to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
