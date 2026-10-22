# Blind test of the medication comparison

**Why.** The first test of the comparison feature (50 medicines in 35 cases) was written by the developer, so it mostly shows that
the rules pass the cases their author imagined. This folder holds a second test: cases written by **other people who had not seen
the app**.

**How it works**
1. People fill in `TEMPLATE.txt`: made-up patients, a medicine list before a hospital stay, the new list, and what they think changed.
   No real patient information is used.
2. Each file is saved here (`pharmacist1.txt`, `nurse1.txt`, ...). Names are not needed, only a role.
3. `python3 eval_blind.py` runs every case through the same steps a user's lists go through (typed list, then the AI parser, then
   the comparison) and scores each medicine against what the person expected.
4. The report (`blind_results.md`) lists **every** disagreement, including the ones where the app was wrong.

**Rules of an honest run**
- The code is frozen (a Git tag) before the final cases are run.
- The final cases are run once. The result is published as it came out.
- If the test finds mistakes, they are fixed *afterwards*, and the fixes are checked on **new** cases. The first result stays in the record.

**How answers are judged:** *correct* (same answer), *safe* (the app said "ask a pharmacist" when a real change existed),
*extra caution* (the app said "ask a pharmacist" when the person said unchanged), *false alarm*, *wrong change type*, and
*missed a real change* (the dangerous one).
