from datetime import datetime
import json
from thefuzz import fuzz
import json
import os

# Load FDA drug database
_db_path = os.path.join(os.path.dirname(__file__), "drug_db.json")
try:
    with open(_db_path) as f:
        FDA_DRUG_DB = json.load(f)
    print(f"Loaded {len(FDA_DRUG_DB)} FDA drug mappings")
except:
    FDA_DRUG_DB = {}
    print("Warning: FDA drug database not found, using fallback only")

# One reviewed name list shared with reconcile.py (see drug_names.py)
from drug_names import SINGLE_BRANDS as _SB, SYNONYMS as _SY, SALT_BRANDS as _SALT, is_recognized as _is_known
_SHARED_SINGLE = {**_SB, **{k: v for k, v in _SY.items() if k != v}, **{k: v.split()[0] for k, v in _SALT.items()}, "toprol xl": "metoprolol"}

BRAND_TO_GENERIC = {
    "tylenol": "acetaminophen",
    "advil": "ibuprofen",
    "motrin": "ibuprofen",
    "aleve": "naproxen",
    "benadryl": "diphenhydramine",
    "claritin": "loratadine",
    "zyrtec": "cetirizine",
    "pepcid": "famotidine",
    "prilosec": "omeprazole",
    "ventolin": "albuterol",
    "proair": "albuterol",
    "zithromax": "azithromycin",
    "augmentin": "amoxicillin-clavulanate",
    "amoxil": "amoxicillin",
    "paracetamol": "acetaminophen",
    "calpol": "acetaminophen",
    "nurofen": "ibuprofen",
    "iburamin": "ibuprofen",
    "zinco": "zinc",
    "oladin": "olopatadine",
    **_SHARED_SINGLE,  # the FDA label sample is no longer merged in: it held non-medicines (sunscreens, soaps, 'allergy relief')
}

CRITICAL_WARNINGS = {
    "acetaminophen": "Do not exceed recommended dose. Check other medications for hidden acetaminophen content.",
    "ibuprofen": "Take with food. Avoid if stomach ulcer history.",
    "albuterol": "Monitor heart rate. Shake inhaler before use.",
    "amoxicillin": "Complete the full course even if feeling better.",
    "amoxicillin-clavulanate": "Complete the full course even if feeling better.",
    "prednisolone": "Do not stop suddenly. Take with food.",
    "zinc": "Take with food to avoid nausea.",
}

def normalize(name: str) -> str:
    return name.lower().strip().replace("-", " ").replace("_", " ")

def canonicalize(name: str) -> str:
    clean = name.lower().strip()
    if clean in BRAND_TO_GENERIC:
        return BRAND_TO_GENERIC[clean]
    known_generics = set(BRAND_TO_GENERIC.values())
    if clean in known_generics or _is_known(clean):
        return clean          # already a real medicine name: never "correct" it into a different drug
    # typo tolerance (for example a misread label): take the CLOSEST known name, not the first one found
    best_ratio, best = 0, None
    for candidate, answer in list(BRAND_TO_GENERIC.items()) + [(g, g) for g in known_generics]:
        r = fuzz.ratio(clean, candidate)
        if r >= 85 and r > best_ratio:
            best_ratio, best = r, answer
    return best if best else clean

def names_match(name_a: str, name_b: str) -> bool:
    a = canonicalize(normalize(name_a))
    b = canonicalize(normalize(name_b))
    if a == b:
        return True
    # Two DIFFERENT medicines this app knows are never the same, however alike they look or sound
    # (prednisone / prednisolone, citalopram / escitalopram, amoxicillin / ampicillin).
    if _is_known(a) and _is_known(b):
        return False
    return a in b or b in a or fuzz.ratio(a, b) >= 85

def cross_reference(discharge_data: dict, cabinet_meds: list) -> dict:
    prescribed = discharge_data.get("medications", [])

    keep = []
    dispose = []
    unclear = []

    for med in cabinet_meds:
        confidence = med.get("extraction_confidence", "high")
        is_expired = med.get("is_expired")
        drug_name = med.get("drug_name", "Unknown")
        exp_date = med.get("expiration_date", "Unknown")
        confidence_notes = med.get("confidence_notes", "")

        if confidence == "low":
            unclear.append({
                "drug_name": drug_name,
                "reason": "Could not read label clearly",
                "details": confidence_notes,
                "action": "Please retake a clearer photo, or check the label manually."
            })
            continue

        if is_expired is None:
            unclear.append({
                "drug_name": drug_name,
                "reason": "Expiration date not found on label",
                "details": confidence_notes,
                "action": "Check the box or packaging for an expiration date before using."
            })
            continue

        if is_expired:
            matched = next((p for p in prescribed if names_match(p["name"], drug_name)), None)
            dispose.append({
                "drug_name": drug_name,
                "expiration_date": exp_date,
                "matches_prescription": bool(matched),
                "action": "This medication is expired and should be safely disposed of.",
                "warning": f"Your discharge letter prescribes {matched['name']} — please get a new supply from your pharmacist." if matched else None
            })
            continue

        matched_prescription = next(
            (p for p in prescribed if names_match(p["name"], drug_name)), None
        )

        generic = canonicalize(normalize(drug_name))
        clinical_warning = CRITICAL_WARNINGS.get(generic)

        if matched_prescription:
            keep.append({
                "drug_name": drug_name,
                "expiration_date": exp_date,
                "prescribed_dosage": matched_prescription.get("dosage", "see letter"),
                "prescribed_frequency": matched_prescription.get("frequency", "see letter"),
                "action": "✅ Keep — this matches your discharge letter. Take as directed.",
                "purpose": matched_prescription.get("purpose", ""),
                "clinical_warning": clinical_warning
            })
        else:
            keep.append({
                "drug_name": drug_name,
                "expiration_date": exp_date,
                "prescribed_dosage": med.get("dosage_strength", "unknown"),
                "prescribed_frequency": None,
                "action": "Not in your current discharge letter — keep only if prescribed for another ongoing condition.",
                "purpose": None,
                "clinical_warning": clinical_warning
            })

    missing = []
    for prescription in prescribed:
        found = any(names_match(prescription["name"], m.get("drug_name", "")) for m in cabinet_meds)
        if not found:
            missing.append({
                "drug_name": prescription["name"],
                "dosage": prescription.get("dosage", ""),
                "frequency": prescription.get("frequency", ""),
                "action": "⚠️ Not found in your cabinet — you may need to pick this up from the pharmacy.",
                "purpose": prescription.get("purpose", "")
            })

    return {
        "summary": {
            "total_cabinet_meds": len(cabinet_meds),
            "keep": len(keep),
            "dispose": len(dispose),
            "unclear": len(unclear),
            "missing_from_cabinet": len(missing)
        },
        "keep": keep,
        "dispose": dispose,
        "unclear": unclear,
        "missing_from_cabinet": missing,
        "important_note": "This tool organizes information only. It does not replace medical advice. Always confirm medication decisions with your doctor or pharmacist."
    }
