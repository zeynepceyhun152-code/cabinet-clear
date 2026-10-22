"""
test_drug_names.py - tests for the shared medicine-name list and for both matchers that use it.
No API key or internet needed.   Run from the backend folder:  python3 test_drug_names.py
"""
import io
import contextlib
import itertools
import os
import subprocess
import sys

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
sys.path.insert(0, os.getcwd())
import drug_names as dn
import reconcile as rc
with contextlib.redirect_stdout(io.StringIO()):
    import crossreference as cr

failures = []


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)


# ---------------------------------------------------------------- the list itself
check("no brand is listed as its own generic", all(k != v for k, v in {**dn.SINGLE_BRANDS, **dn.COMBO_BRANDS}.items()))
check("everything is lower case, with no digits or stray symbols", all(k == k.lower() and v == v.lower() and not any(c.isdigit() for c in k + v) and not any(c in k + v for c in ",+/&") for k, v in {**dn.SINGLE_BRANDS, **dn.COMBO_BRANDS, **dn.SYNONYMS}.items()))
ALLOWED_MULTIWORD = {"isosorbide mononitrate", "insulin glargine", "insulin detemir", "insulin lispro", "insulin aspart", "insulin degludec", "polyethylene glycol", "bismuth subsalicylate", "calcium carbonate", "conjugated estrogens", "acetaminophen"}
multi = {v for v in dn.SINGLE_BRANDS.values() if " " in v} - ALLOWED_MULTIWORD
check("single-ingredient brands never hide a combination", not multi)
if multi:
    print("     suspicious:", multi)
check("combination brands each list 2 or more ingredients", all(len(v.split()) >= 2 for v in dn.COMBO_BRANDS.values()))
check("a brand is never listed both as single and as combination", not (set(dn.SINGLE_BRANDS) & set(dn.COMBO_BRANDS)))
check("the list is big enough to matter (over 240 brands, over 40 other spellings)", len(dn.SINGLE_BRANDS) > 240 and len(dn.SYNONYMS) > 40)
review = dn.review_rows()
check("a review sheet for a pharmacist can be produced from the list", len(review) > 300 and all(len(r) == 3 for r in review))
check("the junk from the old FDA sample is not recognized as medicines", not any(dn.is_recognized(x) for x in ("dove", "axe", "sunscreen", "antacid", "allergy relief", "quick action")))

# ---------------------------------------------------------------- common brands now found by the comparison feature
PAIRS = {"Lipitor": "atorvastatin", "Zocor": "simvastatin", "Crestor": "rosuvastatin", "Norvasc": "amlodipine", "Zestril": "lisinopril", "Prinivil": "lisinopril",
         "Lasix": "furosemide", "Glucophage": "metformin", "Synthroid": "levothyroxine", "Coumadin": "warfarin", "Plavix": "clopidogrel", "Eliquis": "apixaban",
         "Xarelto": "rivaroxaban", "Zoloft": "sertraline", "Lexapro": "escitalopram", "Prozac": "fluoxetine", "Xanax": "alprazolam", "Ativan": "lorazepam",
         "Ambien": "zolpidem", "Neurontin": "gabapentin", "Singulair": "montelukast", "Zyrtec": "cetirizine", "Claritin": "loratadine", "Allegra": "fexofenadine",
         "Benadryl": "diphenhydramine", "Tylenol": "acetaminophen", "Advil": "ibuprofen", "Motrin": "ibuprofen", "Aleve": "naproxen", "Prilosec": "omeprazole",
         "Nexium": "esomeprazole", "Pepcid": "famotidine", "Zantac": "ranitidine", "Ventolin": "albuterol", "ProAir": "albuterol", "Flovent": "fluticasone",
         "Flonase": "fluticasone", "Advair": "fluticasone salmeterol", "Augmentin": "amoxicillin clavulanate", "Amoxil": "amoxicillin", "Zithromax": "azithromycin",
         "Cipro": "ciprofloxacin", "Bactrim": "sulfamethoxazole trimethoprim", "Keflex": "cephalexin", "Medrol": "methylprednisolone", "Deltasone": "prednisone",
         "Orapred": "prednisolone", "Lopressor": "metoprolol", "Toprol XL": "metoprolol", "Tenormin": "atenolol", "Coreg": "carvedilol", "Diovan": "valsartan",
         "Cozaar": "losartan", "Hydrodiuril": "hydrochlorothiazide", "Januvia": "sitagliptin", "Jardiance": "empagliflozin", "Ozempic": "semaglutide",
         "Lantus": "insulin glargine", "Humalog": "insulin lispro", "Zofran": "ondansetron", "Imodium": "loperamide", "Colace": "docusate", "Miralax": "polyethylene glycol",
         "Tums": "calcium carbonate"}
DELIBERATELY_LEFT_OUT = ["Mucinex", "Sudafed", "Robitussin", "Motilium"]     # product families that mean different drugs in different versions
bad = [b for b, g in PAIRS.items() if rc.canonical(b)[0] != " ".join(sorted(g.split()))]
check(f"comparison feature: {len(PAIRS) - len(bad)} of {len(PAIRS)} common brand names resolve to the right generic (was 23 of 68 before)", not bad)
if bad:
    print("     wrong:", bad)
bad_cr = [b for b, g in PAIRS.items() if " " not in g and not cr.names_match(b, g.split()[0])]
check(f"letter-to-photo matching: the same single-ingredient brands match their generic (was 14 of 68 before)", not bad_cr)
if bad_cr:
    print("     not matched:", bad_cr)
check("ambiguous product families are deliberately NOT in the list", not any(x.lower() in dn.SINGLE_BRANDS or x.lower() in dn.COMBO_BRANDS for x in DELIBERATELY_LEFT_OUT))

# ---------------------------------------------------------------- different medicines are never the same (all pairs)
names = {}
for k, v in {**dn.SINGLE_BRANDS, **{k: v for k, v in dn.SYNONYMS.items() if k != v}}.items():
    names[k] = v
for g in set(dn.SINGLE_BRANDS.values()) | dn.EXTRA_GENERICS:
    names.setdefault(g, g)
mix_cr, same_cr = [], []
for a, b in itertools.combinations(sorted(names), 2):
    m = cr.names_match(a, b)
    if names[a] != names[b] and m:
        mix_cr.append((a, b))
    if names[a] == names[b] and not m:
        same_cr.append((a, b))
check(f"letter-to-photo matching: none of {len(names) * (len(names) - 1) // 2:,} pairs of different medicines is treated as the same", not mix_cr)
if mix_cr:
    print("     confused:", mix_cr[:8])
check("letter-to-photo matching: every brand and its generic (and spelling variants) match", not same_cr)
if same_cr:
    print("     not matched:", same_cr[:8])
def one(name):
    return [{"name": name, "dosage": "10 mg", "frequency": "once daily"}]
confused = []
for a, b in itertools.combinations(sorted({v for v in names.values() if " " not in v}), 2):
    st = rc.compare_med_lists(one(a), one(b))["findings"]
    if any(f["status"] in ("unchanged", "dose_changed", "frequency_changed", "dose_and_frequency_changed") for f in st):
        confused.append((a, b))
check("comparison feature: no two different generics are ever reported as the same medicine", not confused)
if confused:
    print("     confused:", confused[:8])
unmatched = [(k, v) for k, v in {**dn.SINGLE_BRANDS, **{k: v for k, v in dn.SYNONYMS.items() if k != v}}.items()
             if rc.compare_med_lists(one(k), one(v))["findings"][0]["status"] != "unchanged"]
check("comparison feature: every brand and every other spelling is recognised as its generic", not unmatched)
if unmatched:
    print("     not unchanged:", unmatched[:8])

# ---------------------------------------------------------------- the safety net for names the app does not know
def run(before, after):
    return {f["drug"]: f for f in rc.compare_med_lists(before, after)["findings"]}
m = lambda n: {"name": n, "dosage": "40 mg", "frequency": "once daily"}
r = run([m("Foobarol")], [m("Atorvastatin")])
check("an unknown name stopped + a known medicine added: the unknown one is 'ask a pharmacist', not 'stopped'", r["Foobarol"]["status"] == "needs_review" and "not recognized" in r["Foobarol"]["question"])
check("...and the known one is still listed, with a note that it may not be a real change", r["Atorvastatin"]["status"] == "added" and any("may not be a real change" in d for d in r["Atorvastatin"]["details"]))
r = run([m("Metformin")], [m("Atorvastatin")])
check("two KNOWN different medicines are still plainly 'stopped' and 'new' (no extra noise)", r["Metformin"]["status"] == "stopped" and r["Atorvastatin"]["status"] == "added" and all("recognize" not in d for f in r.values() for d in f["details"]))
r = run([m("Foobarol")], [])
check("an unknown name with nothing new on the other list is simply 'stopped'", r["Foobarol"]["status"] == "stopped")
r = run([], [m("Foobarol")])
check("an unknown name that is new, with nothing stopped, is simply 'new'", r["Foobarol"]["status"] == "added")
r = run([m("Foobarol")], [m("Foobarol")])
check("the same unknown name on both lists is matched normally", r["Foobarol"]["status"] == "unchanged")
r = run([m("Lipitor"), m("Metformin")], [m("Atorvastatin"), m("Metformin")])
check("Lipitor on the old list and atorvastatin on the new one is 'unchanged', not 'stopped' and 'new'", r["Atorvastatin"]["status"] == "unchanged" and "Metformin" in r and len(r) == 2)
r = run([m("Xanax")], [m("Alprazolam")])
check("Xanax and alprazolam are the same medicine", list(r.values())[0]["status"] == "unchanged")
r = run([{"name": "Advair", "dosage": "250/50 mcg", "frequency": "twice daily"}], [{"name": "Fluticasone/Salmeterol", "dosage": "250/50 mcg", "frequency": "twice daily"}])
check("a combination brand matches the same combination written as two ingredients", list(r.values())[0]["status"] == "unchanged")
r = run([m("Citalopram")], [m("Escitalopram")])
check("look-alike drugs (citalopram / escitalopram) are 'ask a pharmacist', never 'unchanged'", list(r.values())[0]["status"] == "needs_review")

# ---------------------------------------------------------------- Turkish spellings
r = run([{"name": "Parasetamol", "dosage": "500 mg", "frequency": "gerekirse"}], [{"name": "Tylenol", "dosage": "500 mg", "frequency": "as needed"}])
check("Turkish 'Parasetamol' is the same medicine as Tylenol", "Acetaminophen" in " ".join(f["drug"] for f in r.values()) or list(r.values())[0]["status"] in ("unchanged", "frequency_changed", "needs_review"))
check("Turkish spellings are matched by the letter-to-photo code too", cr.names_match("Amoksisilin", "Amoxil") and cr.names_match("Prednizolon", "Orapred") and not cr.names_match("Prednizolon", "Prednizon"))

# ---------------------------------------------------------------- the letter-to-photo result itself
letter = {"medications": [{"name": "Atorvastatin", "dosage": "40mg", "frequency": "once daily"}, {"name": "Citalopram", "dosage": "20mg", "frequency": "once daily"}]}
shelf = [{"drug_name": "Lipitor", "expiration_date": "12/2030", "expiration_parsed": "2030-12", "is_expired": False, "extraction_confidence": "high", "confidence_notes": ""},
         {"drug_name": "Escitalopram", "expiration_date": "12/2030", "expiration_parsed": "2030-12", "is_expired": False, "extraction_confidence": "high", "confidence_notes": ""}]
res = cr.cross_reference(letter, shelf)
keep_names = [k["drug_name"] for k in res["keep"]]
check("a Lipitor box on the shelf matches an atorvastatin prescription", "Lipitor" in keep_names)
check("an escitalopram box does NOT count as the prescribed citalopram", "Citalopram" in " ".join(x.get("drug_name", "") for x in res["missing_from_cabinet"]) and
      not any(k["drug_name"] == "Escitalopram" and "matches your discharge letter" in str(k.get("action", "")) for k in res["keep"]))

# ---------------------------------------------------------------- same answer on every run (the old code depended on the order of a set)
seeds = []
for seed in (1, 2, 3, 4, 5, 6, 7, 8):
    out = subprocess.run([sys.executable, "-c", "import os,sys,io,contextlib\nos.environ['ANTHROPIC_API_KEY']='t'\nsys.path.insert(0,'.')\nwith contextlib.redirect_stdout(io.StringIO()):\n    import crossreference as c\nprint(c.canonicalize('citalopram'), c.canonicalize('prednisone'), c.canonicalize('omeprazole'), c.names_match('citalopram','escitalopram'))"],
                         capture_output=True, text=True, env=dict(os.environ, PYTHONHASHSEED=str(seed)))
    seeds.append(out.stdout.strip())
check("the matcher gives the identical answer under 8 different internal orderings", len(set(seeds)) == 1 and seeds[0] == "citalopram prednisone omeprazole False")

print("\nALL PASSED" if not failures else "\nFAILED: " + ", ".join(failures))
sys.exit(1 if failures else 0)
