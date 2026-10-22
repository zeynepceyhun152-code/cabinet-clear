"""
test_eval_blind.py - tests for the blind-test scorer. No API key or internet needed.
Run from the backend folder:  python3 test_eval_blind.py
"""
import os
import sys
import tempfile

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
sys.path.insert(0, os.getcwd())
import eval_blind as eb
from reconcile import compare_med_lists, canonical

failures = []


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)


# ---------------------------------------------------------------- the words people use
words = {"new": "added", "New medicine": "added", "started": "added", "stopped": "stopped", "discontinued": "stopped", "no longer taking": "stopped",
         "dose changed": "dose_changed", "different dosage": "dose_changed", "frequency changed": "frequency_changed", "schedule changed": "frequency_changed",
         "how often changed": "frequency_changed", "dose and frequency changed": "dose_and_frequency_changed", "dose and schedule changed": "dose_and_frequency_changed",
         "unchanged": "unchanged", "same": "unchanged", "no change": "unchanged", "ask pharmacist": "needs_review", "not sure": "needs_review", "unsure": "needs_review"}
bad = {w: eb.norm_status(w) for w, want in words.items() if eb.norm_status(w) != want}
check(f"people's wording is understood ({len(words) - len(bad)}/{len(words)})", not bad)
if bad:
    print("     got:", bad)
check("nonsense wording is refused (not silently guessed)", eb.norm_status("banana") is None and eb.norm_status("") is None)

# ---------------------------------------------------------------- reading a messy file
tmp = tempfile.mkdtemp()
messy = """AUTHOR: Pharmacist
# a comment
CASE 1
Before:
 1. Lisinopril 10 mg once daily
 2) Metformin 500mg BID
• Tylenol 500 mg PRN
after:
* Lisinopril 20 mg once daily
- Atorvastatin 40 mg at night
Expected:
- Lisinopril : Dose changed
- Metformin - stopped
- Atorvastatin = New
- Tylenol: stopped
NOTES: made up

CASE 2
BEFORE:
- Amoxicillin 500 mg three times daily
AFTER:
- Amoxicillin-clavulanate 875 mg twice daily
EXPECTED:
- Amoxicillin: ask pharmacist

CASE 3
BEFORE:
- Aspirin 81 mg daily
EXPECTED:
- Aspirin: unchanged

CASE 4
BEFORE:
- Aspirin 81 mg daily
AFTER:
- Aspirin 81 mg daily
EXPECTED:
- Aspirin: flibbertigibbet
"""
p = os.path.join(tmp, "pharm.txt"); open(p, "w").write(messy)
cases, problems = eb.parse_case_file(p)
check("two good cases are read from a messy file", len(cases) == 2 and cases[0]["author"] == "Pharmacist")
check("bullets, numbers and odd separators are all handled", cases[0]["before"] == ["Lisinopril 10 mg once daily", "Metformin 500mg BID", "Tylenol 500 mg PRN"] and
      cases[0]["expected"] == [("Lisinopril", "dose_changed"), ("Metformin", "stopped"), ("Atorvastatin", "added"), ("Tylenol", "stopped")])
check("a case with no AFTER section is reported, not silently scored", any("case 3" in x and "AFTER" in x for x in problems))
blank = os.path.join(tmp, "blank.txt"); open(blank, "w").write("AUTHOR: x\nCASE 1\nBEFORE:\n- Aspirin 81 mg daily\nAFTER:\n- none\nEXPECTED:\n- Aspirin: stopped\n\nCASE 2\nBEFORE:\n-\nAFTER:\n-\nEXPECTED:\n-\n")
bc, bp = eb.parse_case_file(blank)
check("'none' is a valid AFTER list, and an unused blank template case is ignored without complaint", len(bc) == 1 and bc[0]["after"] == [] and bp == [])
half = os.path.join(tmp, "half.txt"); open(half, "w").write("CASE 1\nBEFORE:\n- Aspirin 81 mg daily\nAFTER:\n-\nEXPECTED:\n- Aspirin: stopped\n")
hc, hp = eb.parse_case_file(half)
check("an empty AFTER list without the word 'none' is flagged", hc == [] and any("AFTER list is empty" in x for x in hp))
check("an unreadable EXPECTED word is reported", any("flibbertigibbet" in x for x in problems))
check("the problems list names the file and case", all("pharm.txt case" in x for x in problems))

# ---------------------------------------------------------------- the offline practice parser
sp = eb.simple_parse(["Lisinopril 10 mg once daily", "Metformin ER 500 mg BID", "Albuterol 90 mcg/actuation 2 puffs every 4 hours as needed", "Tylenol"])
check("practice parser splits name, strength and schedule", sp[0] == {"name": "Lisinopril", "dosage": "10 mg", "frequency": "once daily"} and sp[1]["name"] == "Metformin ER" and sp[1]["dosage"] == "500 mg" and sp[1]["frequency"] == "BID")
check("practice parser keeps a bare name", sp[3] == {"name": "Tylenol", "dosage": None, "frequency": None})

# ---------------------------------------------------------------- how each answer is judged
table = [("dose_changed", "dose_changed", "exact"), ("unchanged", "unchanged", "exact"), ("dose_changed", "needs_review", "flagged_for_pharmacist"),
         ("unchanged", "needs_review", "extra_caution"), ("dose_changed", "unchanged", "missed_change"), ("added", None, "missed_change"),
         ("unchanged", "dose_changed", "false_alarm"), ("unchanged", "stopped", "false_alarm"), ("dose_changed", "frequency_changed", "wrong_change_type"),
         ("added", "stopped", "wrong_change_type"), ("needs_review", "unchanged", "overconfident"), ("needs_review", "dose_changed", "overconfident"),
         ("needs_review", "needs_review", "exact"), ("unchanged", None, "not_found")]
wrong = [(e, g, want, eb.classify(e, g)) for e, g, want in table if eb.classify(e, g) != want]
check(f"every kind of answer is judged correctly ({len(table) - len(wrong)}/{len(table)})", not wrong)
if wrong:
    print("     wrong:", wrong)
check("missing a real change is the one called MISSED (the dangerous mistake)", eb.classify("stopped", "unchanged") == "missed_change")

# ---------------------------------------------------------------- finding the right medicine, brand or generic
f = [{"drug": "Acetaminophen", "status": "unchanged", "before": [{"name": "Tylenol"}], "after": [{"name": "Acetaminophen"}]},
     {"drug": "Metformin ER", "status": "needs_review", "before": [{"name": "Metformin"}], "after": [{"name": "Metformin ER"}]}]
check("a brand name written by a person finds the generic result", eb.find_finding("Tylenol", f, canonical)["drug"] == "Acetaminophen")
check("'Metformin' finds 'Metformin ER'", eb.find_finding("Metformin", f, canonical)["drug"] == "Metformin ER")
check("a medicine that is not in the results is not found", eb.find_finding("Warfarin", f, canonical) is None)

# ---------------------------------------------------------------- numbers, with a made-up comparer whose answers are known
case = {"id": "x-1", "author": "Nurse", "before": ["a"], "after": ["b"],
        "expected": [("A", "unchanged"), ("B", "added"), ("C", "stopped"), ("D", "dose_changed"), ("E", "unchanged"), ("F", "dose_changed")]}
fake = lambda b, a: {"findings": [{"drug": "A", "status": "unchanged"}, {"drug": "B", "status": "added"}, {"drug": "C", "status": "unchanged"},
                                  {"drug": "D", "status": "needs_review"}, {"drug": "E", "status": "dose_changed"}, {"drug": "F", "status": "dose_changed"}]}
for x in fake(0, 0)["findings"]:
    x.setdefault("before", []); x.setdefault("after", [])
rows = eb.score_case(case, lambda lines: [], fake, lambda s: str(s).lower())
m = eb.metrics(rows)
check("counts: 3 exact, 1 missed, 1 safe flag, 1 false alarm", (m["exact"], m["missed"], m["flagged"], m["false_alarm"]) == (3, 1, 1, 1))
check("exact rate is 3 of 6", abs(m["exact_rate"] - 0.5) < 1e-9)
check("change detection: 3 of 4 real changes noticed (a flag counts, a miss does not)", abs(m["change_detection"] - 0.75) < 1e-9 and m["n_changes"] == 4)
check("false alarm rate: 1 of 2 unchanged", abs(m["false_alarm_rate"] - 0.5) < 1e-9)
perfect = [{"case": f"c{i}", "author": "x", "drug": "d", "expected": "added", "got": "added", "outcome": "exact", "before": [], "after": []} for i in range(8)]
check("a perfect run has a perfect 95% range", eb.bootstrap(perfect, "exact_rate") == (1.0, 1.0))

# ---------------------------------------------------------------- the whole command, offline
d = os.path.join(tmp, "cases"); os.makedirs(d)
open(os.path.join(d, "TEMPLATE.txt"), "w").write(open("blind_cases/TEMPLATE.txt").read())
open(os.path.join(d, "nurse.txt"), "w").write("AUTHOR: Nurse\nCASE 1\nBEFORE:\n- Lisinopril 10 mg once daily\n- Metformin 500 mg twice daily\nAFTER:\n- Lisinopril 20 mg once daily\n- Atorvastatin 40 mg at bedtime\nEXPECTED:\n- Lisinopril: dose changed\n- Metformin: stopped\n- Atorvastatin: new\n")
out = os.path.join(tmp, "res.md")
before_files = sorted(os.listdir(d))
sys.argv = ["eval_blind.py", "--dir", d, "--parser", "simple", "--out", out]
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    code = eb.main()
text = open(out).read()
check("the command runs and writes a report", code == 0 and os.path.exists(out))
check("the template file is not counted as a test case", "Cases: **1**" in text)
check("the report shows what was scored", "Medicines scored: **3**" in text and "practice run" in text)
check("the report has the headline table and the 95% range", "Exact answer correct" in text and "95% range" in text)
check("with only one case the report says there are too few cases for a range (no false certainty)", "too few cases for a range" in text)
check("a practice run says so clearly and never claims outsiders wrote the cases", "PRACTICE RUN" in text and "had not seen the app" not in text)
check("the case files were not changed", sorted(os.listdir(d)) == before_files)
sys.argv = ["eval_blind.py", "--dir", os.path.join(tmp, "empty"), "--parser", "simple"]
os.makedirs(os.path.join(tmp, "empty"))
with contextlib.redirect_stdout(io.StringIO()):
    check("an empty folder gives a clear message, not a crash", eb.main() == 1)

print("\nALL PASSED" if not failures else "\nFAILED: " + ", ".join(failures))
sys.exit(1 if failures else 0)
