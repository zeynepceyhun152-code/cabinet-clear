import json
from crossreference import cross_reference

# Simulated discharge letter extraction output (as if Gemini returned this)
discharge_data = {
    "diagnosis_summary": "Ethan has a broken bone in his left forearm near the wrist, treated with a cast.",
    "medications": [
        {
            "name": "Acetaminophen",
            "dosage": "325mg",
            "frequency": "every 6 hours as needed",
            "duration": "as needed",
            "purpose": "pain relief"
        },
        {
            "name": "Ibuprofen",
            "dosage": "200mg",
            "frequency": "every 6-8 hours as needed",
            "duration": "as needed",
            "purpose": "pain relief and inflammation"
        }
    ],
    "follow_up_appointments": [
        {"type": "Orthopedic follow-up", "timeframe": "1 week (June 21)", "reason": "repeat X-ray and cast check"}
    ],
    "warning_signs": [
        "Numbness or tingling in fingers",
        "Fingers turning blue or pale",
        "Severe pain not relieved by medication"
    ]
}

# Simulated cabinet scan results (4 medicines, different scenarios)
cabinet_meds = [
    {
        # Scenario 1: matches prescription, not expired
        "drug_name": "Acetaminophen",
        "active_ingredient": "Acetaminophen",
        "dosage_strength": "325mg",
        "expiration_date": "EXP 09/2026",
        "expiration_parsed": "2026-09",
        "is_expired": False,
        "extraction_confidence": "high",
        "confidence_notes": ""
    },
    {
        # Scenario 2: expired AND matches a prescription
        "drug_name": "Ibuprofen",
        "active_ingredient": "Ibuprofen",
        "dosage_strength": "200mg",
        "expiration_date": "EXP 03/2024",
        "expiration_parsed": "2024-03",
        "is_expired": True,
        "extraction_confidence": "high",
        "confidence_notes": ""
    },
    {
        # Scenario 3: not in discharge letter, not expired (old prescription)
        "drug_name": "Amoxicillin",
        "active_ingredient": "Amoxicillin",
        "dosage_strength": "500mg",
        "expiration_date": "EXP 12/2026",
        "expiration_parsed": "2026-12",
        "is_expired": False,
        "extraction_confidence": "high",
        "confidence_notes": ""
    },
    {
        # Scenario 4: unclear label
        "drug_name": "Unknown",
        "active_ingredient": None,
        "dosage_strength": None,
        "expiration_date": None,
        "expiration_parsed": None,
        "is_expired": None,
        "extraction_confidence": "low",
        "confidence_notes": "Label was too blurry to read — expiration date area obscured"
    }
]

result = cross_reference(discharge_data, cabinet_meds)
print(json.dumps(result, indent=2))
