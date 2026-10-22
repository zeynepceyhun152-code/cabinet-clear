"""Extracted data for the five sample letters, in the shape extraction.py returns."""

SAMPLES = {
    "asthma": {
        "diagnosis_summary": "Maya had an asthma flare-up that was treated and has settled.",
        "medications": [
            {"name": "Albuterol inhaler", "dosage": "2 puffs", "frequency": "every 4-6 hours as needed", "duration": None, "purpose": "to help with wheezing or shortness of breath"},
            {"name": "Prednisolone", "dosage": "20mg", "frequency": "once daily", "duration": "for 5 days (last dose June 17)", "purpose": "to calm the airways"},
            {"name": "Fluticasone inhaler", "dosage": "1 puff", "frequency": "twice daily", "duration": "ongoing", "purpose": "daily maintenance"}],
        "follow_up_appointments": [{"type": "Pediatrician visit", "timeframe": "in 1 week (by June 19)", "reason": "to check breathing"},
                                   {"type": "Pulmonology referral", "timeframe": "if symptoms return or worsen", "reason": ""}],
        "warning_signs": ["Difficulty breathing or rapid breathing", "Lips or face turning blue or gray",
                          "Unable to speak in full sentences due to breathlessness", "Albuterol not helping within 15-20 minutes"],
        "activity_restrictions": ["Avoid strenuous exercise for 3-4 days"],
        "extraction_confidence": "high", "confidence_notes": ""},
    "appendectomy": {
        "diagnosis_summary": "Jordan had surgery to remove an inflamed appendix. It went well.",
        "medications": [
            {"name": "Ibuprofen", "dosage": "400mg", "frequency": "every 6 hours as needed", "duration": None, "purpose": "pain relief"},
            {"name": "Acetaminophen", "dosage": "500mg", "frequency": "every 6 hours as needed", "duration": None, "purpose": "pain relief"},
            {"name": "Amoxicillin-Clavulanate", "dosage": "875mg", "frequency": "twice daily", "duration": "for 7 days (last dose June 20)", "purpose": "antibiotic"}],
        "follow_up_appointments": [{"type": "Surgical follow-up", "timeframe": "in 2 weeks (June 27)", "reason": "incision check"}],
        "warning_signs": ["Fever above 101.5F (38.6C)", "Redness, swelling, or discharge from incision sites",
                          "Severe or worsening abdominal pain", "Persistent vomiting or inability to keep fluids down"],
        "activity_restrictions": ["No heavy lifting (>10 lbs) for 2 weeks", "No swimming or bathing until incisions are healed"],
        "extraction_confidence": "high", "confidence_notes": ""},
    "heart_failure": {
        "diagnosis_summary": "Robert's heart failure got worse and is now stable. He also has type 2 diabetes.",
        "medications": [
            {"name": "Furosemide", "dosage": "40mg", "frequency": "once daily in the morning", "duration": None, "purpose": "removes extra fluid"},
            {"name": "Metformin", "dosage": "500mg", "frequency": "twice daily with meals", "duration": None, "purpose": "diabetes"},
            {"name": "Lisinopril", "dosage": "10mg", "frequency": "once daily", "duration": None, "purpose": ""},
            {"name": "Metoprolol", "dosage": "25mg", "frequency": "twice daily", "duration": None, "purpose": ""}],
        "follow_up_appointments": [{"type": "Cardiology follow-up", "timeframe": "within 1 week (by June 18)", "reason": ""},
                                   {"type": "Primary care follow-up", "timeframe": "within 2 weeks (by June 25)", "reason": ""}],
        "warning_signs": ["Weight gain of more than 3 lbs in one day or 5 lbs in one week", "Shortness of breath at rest or when lying flat",
                          "New or worsening swelling in legs, ankles, or abdomen", "Chest pain or irregular heartbeat"],
        "activity_restrictions": ["Low-sodium diet (less than 2000mg sodium per day)", "Limit fluids to 1.5-2 liters per day"],
        "extraction_confidence": "high", "confidence_notes": ""},
    "newborn": {
        "diagnosis_summary": "A healthy newborn going home after an uncomplicated birth.",
        "medications": [{"name": "Vitamin D drops", "dosage": "400 IU", "frequency": "once daily", "duration": "until at least 12 months of age", "purpose": "healthy bones"}],
        "follow_up_appointments": [{"type": "Pediatrician visit", "timeframe": "within 3-5 days (by June 19)", "reason": "weight check"}],
        "warning_signs": ["Yellowing of skin or eyes that worsens or spreads", "Fever (100.4F / 38C or higher)",
                          "Poor feeding or excessive sleepiness", "Fewer than 6 wet diapers per day after day 5",
                          "Difficulty breathing or bluish color around lips"],
        "activity_restrictions": [], "extraction_confidence": "high", "confidence_notes": ""},
    "fracture": {
        "diagnosis_summary": "Ethan broke a bone in his left forearm near the wrist. A cast was put on.",
        "medications": [
            {"name": "Acetaminophen", "dosage": "325mg", "frequency": "every 6 hours as needed", "duration": None, "purpose": "pain relief"},
            {"name": "Ibuprofen", "dosage": "200mg", "frequency": "every 6-8 hours as needed", "duration": None, "purpose": "pain relief"}],
        "follow_up_appointments": [{"type": "Orthopedic follow-up", "timeframe": "in 1 week (June 21)", "reason": "repeat X-ray and cast check"}],
        "warning_signs": ["Numbness, tingling, or loss of feeling in fingers", "Fingers turning blue, pale, or very cold",
                          "Severe pain not relieved by medication", "Cast feels too tight or cracks/breaks"],
        "activity_restrictions": ["Keep cast clean and dry", "No contact sports for 6 weeks"],
        "extraction_confidence": "high", "confidence_notes": ""},
}
