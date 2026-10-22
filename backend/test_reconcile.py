"""
test_reconcile.py - evaluates reconcile.compare_med_lists on synthetic medication histories
with known answers, against a naive exact-string baseline.

Run:  python test_reconcile.py
Every medication has an "id" used only here to score predictions.
IMPORTANT: these cases are synthetic. The numbers describe behaviour on this set, not on
real patients. Add your own blind cases (written before you look at the output) to make
the result meaningful.
"""
import sys
from reconcile import (compare_med_lists, naive_compare, ADDED, STOPPED, DOSE_CHANGED,
                       FREQ_CHANGED, BOTH_CHANGED, UNCHANGED, NEEDS_REVIEW)


def med(i, name, dosage, frequency):
    return {"id": i, "name": name, "dosage": dosage, "frequency": frequency}


CASES = [
    # (name, before, after, {id: expected_status})
    ("identical lists",
     [med("a", "Lisinopril", "10 mg", "once daily"), med("b", "Metformin", "500 mg", "twice daily")],
     [med("a", "Lisinopril", "10 mg", "once daily"), med("b", "Metformin", "500 mg", "twice daily")],
     {"a": UNCHANGED, "b": UNCHANGED}),
    ("brand vs generic",
     [med("a", "Tylenol", "500 mg", "every 6 hours as needed")],
     [med("a", "Acetaminophen", "500 mg", "every 6 hours as needed")],
     {"a": UNCHANGED}),
    ("dose formatting + q6h prn",
     [med("a", "Ibuprofen", "400mg", "every 6 hours as needed")],
     [med("a", "Ibuprofen", "400 mg", "q6h PRN")],
     {"a": UNCHANGED}),
    ("mcg vs mg",
     [med("a", "Levothyroxine", "0.1 mg", "once daily")],
     [med("a", "Levothyroxine", "100 mcg", "once daily")],
     {"a": UNCHANGED}),
    ("twice daily vs every 12 hours",
     [med("a", "Metoprolol", "25 mg", "twice daily")],
     [med("a", "Metoprolol", "25 mg", "every 12 hours")],
     {"a": UNCHANGED}),
    ("BID vs twice daily",
     [med("a", "Metformin", "500 mg", "BID with meals")],
     [med("a", "Metformin", "500 mg", "twice daily with meals")],
     {"a": UNCHANGED}),
    ("dose increase",
     [med("a", "Lisinopril", "10 mg", "once daily")],
     [med("a", "Lisinopril", "20 mg", "once daily")],
     {"a": DOSE_CHANGED}),
    ("frequency change",
     [med("a", "Metoprolol", "25 mg", "twice daily")],
     [med("a", "Metoprolol", "25 mg", "once daily")],
     {"a": FREQ_CHANGED}),
    ("dose and frequency change",
     [med("a", "Furosemide", "20 mg", "once daily")],
     [med("a", "Furosemide", "40 mg", "twice daily")],
     {"a": BOTH_CHANGED}),
    ("drug added",
     [med("a", "Metformin", "500 mg", "twice daily")],
     [med("a", "Metformin", "500 mg", "twice daily"), med("b", "Atorvastatin", "20 mg", "once daily")],
     {"a": UNCHANGED, "b": ADDED}),
    ("drug stopped",
     [med("a", "Warfarin", "5 mg", "once daily"), med("b", "Aspirin", "81 mg", "once daily")],
     [med("b", "Aspirin", "81 mg", "daily")],
     {"a": STOPPED, "b": UNCHANGED}),
    ("amoxicillin vs amoxicillin-clavulanate (shared ingredient)",
     [med("a", "Amoxicillin", "500 mg", "three times daily")],
     [med("b", "Amoxicillin-Clavulanate", "875 mg", "twice daily")],
     {"a": NEEDS_REVIEW, "b": NEEDS_REVIEW}),
    ("look-alike names metformin vs metoprolol",
     [med("a", "Metformin", "500 mg", "twice daily")],
     [med("b", "Metoprolol", "25 mg", "twice daily")],
     {"a": STOPPED, "b": ADDED}),
    ("OCR typo in name",
     [med("a", "Ibuprofen", "400 mg", "every 6 hours")],
     [med("a", "Ibuprofin", "400 mg", "every 6 hours")],
     {"a": NEEDS_REVIEW}),
    ("dose missing on one list",
     [med("a", "Lisinopril", "10 mg", "once daily")],
     [med("a", "Lisinopril", "", "once daily")],
     {"a": NEEDS_REVIEW}),
    ("as-needed becomes scheduled",
     [med("a", "Acetaminophen", "500 mg", "every 6 hours as needed")],
     [med("a", "Acetaminophen", "500 mg", "every 6 hours")],
     {"a": FREQ_CHANGED}),
    ("range vs fixed interval",
     [med("a", "Ibuprofen", "200 mg", "every 6-8 hours as needed")],
     [med("a", "Ibuprofen", "200 mg", "every 6 hours as needed")],
     {"a": FREQ_CHANGED}),
    ("incomparable units (puffs vs mcg)",
     [med("a", "Albuterol", "2 puffs", "every 4-6 hours as needed")],
     [med("a", "Albuterol", "90 mcg", "every 4-6 hours as needed")],
     {"a": NEEDS_REVIEW}),
    ("tartrate vs succinate",
     [med("a", "Metoprolol tartrate", "25 mg", "twice daily")],
     [med("a", "Metoprolol succinate", "50 mg", "once daily")],
     {"a": NEEDS_REVIEW}),
    ("salt named on one side only",
     [med("a", "Metoprolol", "25 mg", "twice daily")],
     [med("a", "Metoprolol tartrate", "25 mg", "twice daily")],
     {"a": UNCHANGED}),
    ("same drug listed twice",
     [med("a", "Ibuprofen", "200 mg", "every 6 hours as needed"), med("b", "Ibuprofen", "400 mg", "every 8 hours as needed")],
     [med("c", "Ibuprofen", "400 mg", "every 8 hours as needed")],
     {"a": NEEDS_REVIEW, "b": NEEDS_REVIEW, "c": NEEDS_REVIEW}),
    ("Augmentin vs amoxicillin-clavulanate",
     [med("a", "Augmentin", "875 mg", "twice daily")],
     [med("a", "Amoxicillin-Clavulanate", "875 mg", "every 12 hours")],
     {"a": UNCHANGED}),
    ("vitamin D3 vs vitamin D drops",
     [med("a", "Vitamin D3", "400 IU", "daily")],
     [med("a", "Vitamin D drops", "400 IU", "once daily")],
     {"a": UNCHANGED}),
    ("unreadable frequency",
     [med("a", "Prednisolone", "20 mg", "once daily for 5 days")],
     [med("a", "Prednisolone", "20 mg", "per instructions")],
     {"a": NEEDS_REVIEW}),
    ("empty lists", [], [], {}),
    # Regression cases added AFTER probing the first version found these bugs.
    ("regression: weekly vs daily",
     [med("a", "Alendronate", "70 mg", "once weekly")],
     [med("a", "Alendronate", "70 mg", "once daily")],
     {"a": FREQ_CHANGED}),
    ("regression: 1 tablet vs 2 tablets, same strength",
     [med("a", "Prednisone", "5 mg", "1 tablet by mouth twice daily")],
     [med("a", "Prednisone", "5 mg", "2 tablets by mouth twice daily")],
     {"a": DOSE_CHANGED}),
    ("regression: taper",
     [med("a", "Prednisone", "20 mg", "once daily")],
     [med("a", "Prednisone", "40 mg x3 days then 20 mg x3 days", "once daily")],
     {"a": NEEDS_REVIEW}),
    ("regression: lisinopril vs lisinopril-HCTZ",
     [med("a", "Lisinopril", "10 mg", "once daily")],
     [med("b", "Lisinopril-HCTZ", "10/12.5 mg", "once daily")],
     {"a": NEEDS_REVIEW, "b": NEEDS_REVIEW}),
    ("regression: metformin vs metformin ER",
     [med("a", "Metformin", "500 mg", "twice daily")],
     [med("a", "Metformin ER", "500 mg", "twice daily")],
     {"a": NEEDS_REVIEW}),
    # Built from the sample letters; the "before" lists are invented for the test.
    ("sample: asthma letter",
     [med("alb", "Albuterol inhaler", "2 puffs", "every 4-6 hours as needed"), med("flu", "Fluticasone inhaler", "1 puff", "once daily")],
     [med("alb", "Albuterol inhaler", "2 puffs", "every 4-6 hours as needed"), med("pre", "Prednisolone", "20 mg", "once daily for 5 days"), med("flu", "Fluticasone inhaler", "1 puff", "twice daily")],
     {"alb": UNCHANGED, "pre": ADDED, "flu": FREQ_CHANGED}),
    ("sample: heart failure letter",
     [med("fur", "Furosemide", "20 mg", "once daily in the morning"), med("met", "Metformin", "500 mg", "twice daily with meals"),
      med("lis", "Lisinopril", "10 mg", "once daily"), med("mpr", "Metoprolol", "25 mg", "twice daily")],
     [med("fur", "Furosemide", "40 mg", "once daily in the morning"), med("met", "Metformin", "500 mg", "twice daily with meals"),
      med("lis", "Lisinopril", "10 mg", "once daily"), med("mpr", "Metoprolol", "25 mg", "twice daily")],
     {"fur": DOSE_CHANGED, "met": UNCHANGED, "lis": UNCHANGED, "mpr": UNCHANGED}),
    ("sample: appendectomy letter",
     [med("apap", "Tylenol", "500 mg", "every 6 hours as needed")],
     [med("ibu", "Ibuprofen", "400 mg", "every 6 hours as needed"), med("apap", "Acetaminophen", "500 mg", "every 6 hours as needed"),
      med("amc", "Amoxicillin-Clavulanate", "875 mg", "twice daily for 7 days")],
     {"apap": UNCHANGED, "ibu": ADDED, "amc": ADDED}),
    ("sample: newborn letter",
     [],
     [med("vd", "Vitamin D drops", "400 IU", "once daily")],
     {"vd": ADDED}),
    ("sample: fracture letter",
     [med("ibu", "Motrin", "200 mg", "every 6-8 hours as needed"), med("apap", "Acetaminophen", "325 mg", "every 6 hours as needed")],
     [med("apap", "Acetaminophen", "325 mg", "every 6 hours as needed"), med("ibu", "Ibuprofen", "200 mg", "every 6-8 hours as needed")],
     {"ibu": UNCHANGED, "apap": UNCHANGED}),
]


def predictions(result):
    pred = {}
    for f in result["findings"]:
        for i in f.get("ids", []):
            pred[i] = f["status"]
    return pred


def evaluate(fn):
    items = ok_items = ok_cases = 0
    misses = []
    for name, before, after, expected in CASES:
        pred = predictions(fn(before, after))
        case_ok = True
        for i, exp in expected.items():
            items += 1
            got = pred.get(i)
            if got == exp:
                ok_items += 1
            else:
                case_ok = False
                misses.append((name, i, exp, got))
        ok_cases += case_ok
    return items, ok_items, ok_cases, misses


if __name__ == "__main__":
    n_items = sum(len(c[3]) for c in CASES)
    print(f"{len(CASES)} synthetic cases, {n_items} medication-level answers\n")
    rows = {}
    for label, fn in (("naive exact-string baseline", naive_compare), ("reconcile.py", compare_med_lists)):
        items, ok_items, ok_cases, misses = evaluate(fn)
        rows[label] = (items, ok_items, ok_cases, misses)
        print(f"{label:30s} medications correct: {ok_items}/{items} ({100*ok_items/items:.1f}%)   "
              f"cases fully correct: {ok_cases}/{len(CASES)}")
    print("\nreconcile.py misses:")
    for name, i, exp, got in rows["reconcile.py"][3] or [("none", "", "", "")]:
        print(f"  {name} [{i}] expected {exp}, got {got}")
    print("\nbaseline misses:")
    for name, i, exp, got in rows["naive exact-string baseline"][3]:
        print(f"  {name} [{i}] expected {exp}, got {got}")
    sys.exit(0 if not rows["reconcile.py"][3] else 1)
