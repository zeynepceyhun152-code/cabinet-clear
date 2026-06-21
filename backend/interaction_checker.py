import requests
import json
from thefuzz import fuzz

# Static fallback for most critical interactions
CRITICAL_INTERACTIONS = {
    ("ibuprofen", "prednisolone"): "Taking ibuprofen with prednisolone significantly increases risk of stomach bleeding. Take with food and inform your doctor.",
    ("ibuprofen", "aspirin"): "Taking ibuprofen with aspirin can reduce aspirin's effectiveness and increase bleeding risk.",
    ("warfarin", "aspirin"): "Aspirin can increase bleeding risk when taken with warfarin. Contact your doctor immediately.",
    ("metformin", "ibuprofen"): "Ibuprofen can reduce kidney function and affect metformin levels. Monitor closely.",
    ("lisinopril", "ibuprofen"): "Ibuprofen can reduce the effectiveness of lisinopril and affect kidney function.",
    ("metoprolol", "ibuprofen"): "Ibuprofen may reduce the blood pressure-lowering effect of metoprolol.",
    ("furosemide", "ibuprofen"): "Ibuprofen can reduce the effectiveness of furosemide and affect kidney function.",
    ("prednisolone", "aspirin"): "Increased risk of stomach bleeding when taken together. Take with food.",
    ("amoxicillin", "warfarin"): "Amoxicillin may increase the blood-thinning effect of warfarin. Monitor closely.",
    ("acetaminophen", "warfarin"): "High doses of acetaminophen can increase bleeding risk with warfarin. Do not exceed recommended dose.",
}

def normalize(name: str) -> str:
    return name.lower().strip()

def get_openfda_interactions(drug_name: str) -> list:
    """Query OpenFDA for drug interactions."""
    try:
        url = f"https://api.fda.gov/drug/label.json?search=openfda.generic_name:{drug_name}&limit=1"
        res = requests.get(url, timeout=5)
        if res.status_code != 200:
            return []
        data = res.json()
        results = data.get("results", [])
        if not results:
            return []
        interactions = results[0].get("drug_interactions", [])
        return interactions[:3] if interactions else []
    except Exception:
        return []

def check_interactions(med_list: list) -> list:
    """
    Check all pairs of medications for interactions.
    med_list: list of drug name strings (generic or brand)
    Returns list of interaction warnings.
    """
    from crossreference import canonicalize
    
    warnings = []
    generics = [canonicalize(normalize(m)) for m in med_list]
    
    # Check static critical interactions first
    for i in range(len(generics)):
        for j in range(i + 1, len(generics)):
            a, b = generics[i], generics[j]
            
            # Check both orderings
            interaction = CRITICAL_INTERACTIONS.get((a, b)) or \
                         CRITICAL_INTERACTIONS.get((b, a))
            
            # Fuzzy match against known pairs
            if not interaction:
                for (k1, k2), msg in CRITICAL_INTERACTIONS.items():
                    if (fuzz.ratio(a, k1) >= 85 and fuzz.ratio(b, k2) >= 85) or \
                       (fuzz.ratio(a, k2) >= 85 and fuzz.ratio(b, k1) >= 85):
                        interaction = msg
                        break
            
            if interaction:
                warnings.append({
                    "drug_a": med_list[i],
                    "drug_b": med_list[j],
                    "severity": "moderate",
                    "message": interaction,
                    "action": "Inform your doctor or pharmacist about this combination."
                })
    
    # Query OpenFDA for additional interactions
    for i, drug in enumerate(med_list[:3]):  # limit API calls
        fda_interactions = get_openfda_interactions(generics[i])
        for interaction_text in fda_interactions:
            # Check if any other med in the list is mentioned
            for other_drug in med_list:
                if other_drug.lower() in interaction_text.lower() and other_drug != drug:
                    warnings.append({
                        "drug_a": drug,
                        "drug_b": other_drug,
                        "severity": "check",
                        "message": interaction_text[:200] + "..." if len(interaction_text) > 200 else interaction_text,
                        "action": "Discuss with your pharmacist."
                    })
    
    # Deduplicate
    seen = set()
    unique_warnings = []
    for w in warnings:
        key = tuple(sorted([w["drug_a"], w["drug_b"]]))
        if key not in seen:
            seen.add(key)
            unique_warnings.append(w)
    
    return unique_warnings
