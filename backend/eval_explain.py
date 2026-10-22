"""
eval_explain.py - measure the adaptive explanations on the five sample letters.

Run from the backend folder (needs your API key in .env):
    python3 eval_explain.py

For each letter and each of three reader profiles it reports:
  - how often the model's explanation passed every faithfulness check (vs. fell back to the plain version)
  - average words per sentence and reading grade level, per profile

It costs about 5 letter reads + 15 explanation calls. Use --offline to test the script itself
without the API (the numbers are then meaningless).
"""
import glob
import json
import os
import sys
from collections import defaultdict

from explain import generate_explanation, readability, fallback_explanation, style_profile

PROFILES = {"overwhelmed (5,1)": (5, 1), "middle (3,3)": (3, 3), "calm and confident (1,5)": (1, 5)}


def load_letters(offline):
    if offline:
        from sample_letters import SAMPLES
        return dict(SAMPLES)
    from extraction import extract_from_text
    out = {}
    for path in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "sample_data", "**", "*.txt"), recursive=True)):
        with open(path) as f:
            out[os.path.basename(path)] = extract_from_text(f.read())
    return out


def main():
    offline = "--offline" in sys.argv
    letters = load_letters(offline)
    if not letters:
        print("No sample letters found in ../sample_data")
        return
    stats = defaultdict(lambda: {"n": 0, "fallback": 0, "words": [], "grade": []})
    problems = []
    for name, data in letters.items():
        for label, (s, u) in PROFILES.items():
            call = (lambda p, d=data, s=s, u=u: json.dumps(fallback_explanation(d, style_profile(s, u)))) if offline else None
            r = generate_explanation(data, s, u, call_model=call)
            st = stats[label]
            st["n"] += 1
            st["fallback"] += r["fallback"]
            avg, grade = readability(r["explanation"])
            st["words"].append(avg)
            st["grade"].append(grade)
            if r["problems"]:
                problems.append((name, label, r["problems"]))
    print(f"{'profile':28s} {'runs':>4s} {'model passed':>13s} {'words/sentence':>15s} {'grade level':>12s}")
    for label, st in stats.items():
        passed = st["n"] - st["fallback"]
        print(f"{label:28s} {st['n']:>4d} {passed:>6d}/{st['n']:<6d} {sum(st['words'])/st['n']:>15.1f} {sum(st['grade'])/st['n']:>12.1f}")
    if problems:
        print("\nWhy the checker rejected the model's version:")
        for name, label, pr in problems:
            print(f"  {name} / {label}: {'; '.join(pr)}")
    if offline:
        print("\n(offline run: the 'model' was the plain fallback, so these numbers only prove the script works)")


if __name__ == "__main__":
    main()
