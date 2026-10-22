"""
test_explain.py - tests for explain.py. No API key or internet needed (the model is faked).

Run:  python3 test_explain.py

What this checks:
  1. The two ratings map to the right style rules.
  2. The plain fallback explanation always passes the faithfulness checker.
  3. A sensible reworded explanation passes, and the checker accepts it.
  4. Deliberately damaged explanations (invented medicine, changed dose, dropped warning sign...)
     are caught.
  5. generate_explanation falls back safely on bad, broken or failing model output.

These are synthetic tests written together with the code. They show the safety checks do what
they were designed to do. They do not show how well a real model writes. Run eval_explain.py
(needs your API key) to measure that.
"""
import copy
import json
import sys

from explain import (style_profile, check_faithfulness, fallback_explanation,
                     generate_explanation, readability)

from sample_letters import SAMPLES

PROFILES = [(5, 1), (3, 3), (1, 5)]  # overwhelmed, middle, calm and confident
failures = []


def check(label, ok):
    if not ok:
        failures.append(label)
    return ok


# ---------------------------------------------------------------- 1. style rules
STYLE_CASES = [
    ((5, 1), "calm_short", 12), ((4, 5), "calm_short", 12), ((5, 5), "calm_short", 12),
    ((3, 3), "standard", 18), ((3, 5), "standard", 18), ((2, 3), "standard", 18), ((1, 1), "standard", 18),
    ((2, 4), "detailed", 25), ((1, 5), "detailed", 25),
    (("x", None), "standard", 18), ((9, 9), "calm_short", 12), ((0, 0), "standard", 18),
]
style_ok = 0
for (s, u), mode, words in STYLE_CASES:
    p = style_profile(s, u)
    style_ok += check(f"style {s},{u}", p["mode"] == mode and p["max_sentence_words"] == words)
print(f"1. style rules: {style_ok}/{len(STYLE_CASES)}")

# ---------------------------------------------------------------- 2. fallback always passes
fb_ok = fb_total = 0
for name, data in SAMPLES.items():
    for s, u in PROFILES:
        fb_total += 1
        fb_ok += check(f"fallback {name} {s},{u}", check_faithfulness(fallback_explanation(data, style_profile(s, u)), data) == [])
print(f"2. fallback passes its own checker: {fb_ok}/{fb_total}")

# ---------------------------------------------------------------- 3. a reworded explanation is accepted
good = {
    "opening": "You are doing the right thing by reading this. Here is what to know.",
    "what_happened": "Jordan had surgery to take out an inflamed appendix. It went well.",
    "do_now": ["Take the antibiotic twice daily for 7 days.", "See the surgeon in 2 weeks (June 27)."],
    "medicines": [
        {"name": "Ibuprofen", "what_for": "Eases pain.", "how_to_take": "400mg every 6 hours if you need it."},
        {"name": "Acetaminophen", "what_for": "Eases pain.", "how_to_take": "500mg every 6 hours if you need it."},
        {"name": "Amoxicillin-Clavulanate", "what_for": "An antibiotic.", "how_to_take": "875mg twice daily for 7 days (last dose June 20)."}],
    "warning_signs": [
        {"original": "Fever above 101.5F (38.6C)", "plain": "A high fever, above 101.5F (38.6C)."},
        {"original": "Redness, swelling, or discharge from incision sites", "plain": "The cuts look red, swollen or leak fluid."},
        {"original": "Severe or worsening abdominal pain", "plain": "Belly pain that is very bad or getting worse."},
        {"original": "Persistent vomiting or inability to keep fluids down", "plain": "You keep throwing up or cannot keep drinks down."}],
    "follow_up": [{"appointment": "Surgical follow-up", "when": "in 2 weeks (June 27)", "why": "The surgeon will check the cuts."}],
    "good_to_know": ["No heavy lifting (more than 10 lbs) for 2 weeks."],
}
check("good reworded explanation accepted", check_faithfulness(good, SAMPLES["appendectomy"]) == [])
print("3. reworded explanation accepted:", check_faithfulness(good, SAMPLES["appendectomy"]) == [])


# ---------------------------------------------------------------- 4. damaged explanations are caught
def m_invent_med(e, d):
    e["medicines"].append({"name": "Oxycodone", "what_for": "pain", "how_to_take": "as needed"}); return e

def m_drop_med(e, d):
    if len(e["medicines"]) < 2: return None
    e["medicines"].pop(); return e

def m_change_dose(e, d):
    import re
    for m in e["medicines"]:
        if "mg" in m["how_to_take"] or "IU" in m["how_to_take"]:
            before = m["how_to_take"]
            m["how_to_take"] = re.sub(r"\d+(?:\.\d+)?", lambda x: str(int(float(x.group())) + 7), before, count=1)
            assert m["how_to_take"] != before
            return e
    return None

def m_drop_warning(e, d):
    e["warning_signs"].pop(); return e

def m_alter_warning(e, d):
    e["warning_signs"][0]["original"] = "Feeling a little tired"; return e

def m_extra_warning(e, d):
    e["warning_signs"].append({"original": "A mild headache", "plain": "A mild headache"}); return e

def m_new_number(e, d):
    e["do_now"].append("Rest for 14 days."); return e

def m_drop_followup(e, d):
    e["follow_up"].pop(); return e

def m_instruction(e, d):
    e["do_now"].append("You can stop taking the medicine when you feel better."); return e

def m_drop_duration(e, d):
    for m in e["medicines"]:
        dur = next((x for x in d["medications"] if x["name"] == m["name"] and x.get("duration")), None)
        if dur:
            m["how_to_take"] = m["how_to_take"].split(",")[0]
            for tok in __import__("re").findall(r"\d+(?:\.\d+)?", dur["duration"]):
                m["how_to_take"] = m["how_to_take"].replace(tok, "")
            return e
    return None

MUTATIONS = [m_invent_med, m_drop_med, m_change_dose, m_drop_warning, m_alter_warning,
             m_extra_warning, m_new_number, m_drop_followup, m_instruction, m_drop_duration]
caught = applied = 0
missed = []
for name, data in SAMPLES.items():
    for mut in MUTATIONS:
        e = mut(copy.deepcopy(fallback_explanation(data, style_profile(3, 3))), data)
        if e is None:
            continue
        applied += 1
        if check_faithfulness(e, data):
            caught += 1
        else:
            missed.append(f"{name}/{mut.__name__}")
check("all damaged versions caught", not missed)
print(f"4. damaged explanations caught: {caught}/{applied}" + (f"  MISSED: {missed}" if missed else ""))

# ---------------------------------------------------------------- 5. generate_explanation paths
data = SAMPLES["appendectomy"]
r1 = generate_explanation(data, 3, 3, call_model=lambda p: json.dumps(good))
r2 = generate_explanation(data, 3, 3, call_model=lambda p: "```json\n" + json.dumps(good) + "\n```")
bad = copy.deepcopy(good); bad["medicines"][2]["how_to_take"] = "575mg twice daily for 7 days (last dose June 20)."
r3 = generate_explanation(data, 3, 3, call_model=lambda p: json.dumps(bad))
r4 = generate_explanation(data, 3, 3, call_model=lambda p: "Sorry, I cannot help with that.")
def boom(p): raise RuntimeError("network down")
r5 = generate_explanation(data, 3, 3, call_model=boom)
low = dict(data, extraction_confidence="low", confidence_notes="blurry photo")
r6 = generate_explanation(low, 5, 1, call_model=lambda p: json.dumps(good))
paths = [("good JSON used", not r1["fallback"]), ("code-fenced JSON parsed", not r2["fallback"]),
         ("changed dose -> fallback", r3["fallback"] and r3["problems"]), ("garbage -> fallback", r4["fallback"]),
         ("exception -> fallback", r5["fallback"]), ("low confidence adds notice", bool(r6["notice"]) and not r1["notice"])]
for label, ok in paths:
    check("path: " + label, bool(ok))
paths.append(("resources always included", all("resources" in r and r["resources"]["groups"] for r in (r1, r3, r4, r5))))
check("path: resources always included", paths[-1][1])
print(f"5. model-output paths: {sum(bool(ok) for _, ok in paths)}/{len(paths)}")

# readability helper (shown for information)
avg, grade = readability(fallback_explanation(data, style_profile(3, 3)))
print(f"   readability helper works: {avg:.1f} words/sentence, grade {grade:.1f}")

print("\nALL PASSED" if not failures else "\nFAILED: " + ", ".join(failures))
sys.exit(1 if failures else 0)
