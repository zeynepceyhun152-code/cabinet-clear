"""
resources.py - trusted places to read more, matched to what a discharge letter is about.

Design rules:
  * The list is curated by hand. Links are NEVER written by an AI, so none can be invented.
  * Only hospital, health-system, professional-society and government pages are included.
  * Matching is plain keyword rules on the extracted letter data.
  * These are general education pages. They are not advice about the reader's own situation.

Each link was checked on 2026-10-17. "checked" says how:
  "page loaded"     - the page was opened and read
  "seen in search"  - the page's real content was returned by a search engine on that date
Web pages move. Run check_links.py before you submit or deploy, and fix any link it reports.
"""
import re

VERIFIED_ON = "2026-10-17"

MEDICINE_SAFETY = {
    "label": "Medicine safety",
    "links": [
        {"title": "Don't be tempted to use expired medicines", "org": "U.S. Food and Drug Administration",
         "kind": "government", "url": "https://www.fda.gov/drugs/safe-disposal-medicines/dont-be-tempted-use-expired-medicines",
         "checked": "seen in search"},
        {"title": "Disposal of unused medicines: what you should know", "org": "U.S. Food and Drug Administration",
         "kind": "government", "url": "https://www.fda.gov/drugs/safe-disposal-medicines/disposal-unused-medicines-what-you-should-know",
         "checked": "seen in search"},
    ],
}

TOPICS = [
    {"id": "asthma", "label": "Asthma", "pattern": r"asthma|wheez",
     "links": [
         {"title": "Asthma in children", "org": "Cleveland Clinic", "kind": "hospital",
          "url": "https://my.clevelandclinic.org/health/diseases/6776-asthma-in-children", "checked": "page loaded"},
         {"title": "Asthma in children", "org": "MedlinePlus (U.S. National Library of Medicine)", "kind": "government",
          "url": "https://medlineplus.gov/ency/article/000990.htm", "checked": "seen in search"},
     ]},
    {"id": "appendectomy", "label": "Appendix surgery", "pattern": r"append(?:ec|ic|ix)",
     "links": [
         {"title": "Appendectomy: what to expect at home", "org": "Kaiser Permanente", "kind": "hospital",
          "url": "https://healthy.kaiserpermanente.org/health-wellness/health-encyclopedia/he.Appendectomy-What-to-Expect-at-Home.ug3573",
          "checked": "seen in search"},
         {"title": "Appendectomy: aftercare", "org": "MedlinePlus (U.S. National Library of Medicine)", "kind": "government",
          "url": "https://medlineplus.gov/ency/presentations/100001_5.htm", "checked": "seen in search"},
     ]},
    {"id": "heart_failure", "label": "Heart failure", "pattern": r"heart failure|\bchf\b|congestive",
     "links": [
         {"title": "Heart failure: symptoms, stages and treatment", "org": "Cleveland Clinic", "kind": "hospital",
          "url": "https://my.clevelandclinic.org/health/diseases/17069-heart-failure-understanding-heart-failure",
          "checked": "page loaded"},
         {"title": "What is heart failure? (fact sheet, PDF)", "org": "American Heart Association", "kind": "professional society",
          "url": "https://www.heart.org/-/media/Files/Health-Topics/Answers-by-Heart/What-Is-Heart-Failure.pdf",
          "checked": "seen in search"},
     ]},
    {"id": "type2_diabetes", "label": "Type 2 diabetes", "pattern": r"\bdiabet",
     "links": [
         {"title": "Type 2 diabetes: symptoms, causes and treatment", "org": "Cleveland Clinic", "kind": "hospital",
          "url": "https://my.clevelandclinic.org/health/diseases/21501-type-2-diabetes", "checked": "seen in search"},
     ]},
    {"id": "newborn", "label": "Newborn care", "pattern": r"newborn|jaundice|neonat",
     "links": [
         {"title": "Jaundice in newborns", "org": "KidsHealth from Nemours (shown by CHOC Children's)", "kind": "hospital",
          "url": "https://kidshealth.org/CHOC/en/parents/jaundice.html", "checked": "seen in search"},
         {"title": "Jaundice in newborns: symptoms, causes and treatment", "org": "Cleveland Clinic", "kind": "hospital",
          "url": "https://my.clevelandclinic.org/health/diseases/22263-jaundice-in-newborns", "checked": "page loaded"},
     ]},
    {"id": "fracture", "label": "Broken bones and casts", "pattern": r"fractur|broken bone|\bbroke\b|\bbroken\b|\bcast\b",
     "links": [
         {"title": "Distal radius fractures (broken wrist)", "org": "OrthoInfo, American Academy of Orthopaedic Surgeons",
          "kind": "professional society",
          "url": "https://orthoinfo.aaos.org/en/diseases--conditions/distal-radius-fractures-broken-wrist/", "checked": "seen in search"},
         {"title": "Caring for your child's cast or splint", "org": "Children's Memorial Hermann Hospital", "kind": "hospital",
          "url": "https://memorialhermann.org/services/conditions/pediatric-fractures-cast-care", "checked": "seen in search"},
     ]},
]

ALLOWED_DOMAINS = {
    "my.clevelandclinic.org", "medlineplus.gov", "healthy.kaiserpermanente.org", "www.heart.org",
    "orthoinfo.aaos.org", "memorialhermann.org", "kidshealth.org", "www.fda.gov",
}


def _letter_text(data):
    parts = [data.get("diagnosis_summary") or ""]
    parts += [m.get("name") or "" for m in (data.get("medications") or [])]
    parts += [str(w) for w in (data.get("warning_signs") or [])]
    parts += [f"{f.get('type', '')} {f.get('reason', '')}" for f in (data.get("follow_up_appointments") or [])]
    parts += [str(a) for a in (data.get("activity_restrictions") or [])]
    return " ".join(parts).lower()


def find_resources(data, max_topics=3):
    """Return the reading list for this letter: matched topics first, then medicine safety."""
    text = _letter_text(data or {})
    groups = []
    for t in TOPICS:
        if re.search(t["pattern"], text):
            groups.append({"id": t["id"], "label": t["label"], "links": [dict(l) for l in t["links"]]})
    groups = groups[:max_topics]
    groups.append({"id": "medicine_safety", "label": MEDICINE_SAFETY["label"],
                   "links": [dict(l) for l in MEDICINE_SAFETY["links"]]})
    return {"groups": groups, "verified_on": VERIFIED_ON,
            "note": "General education pages from hospitals, health systems, professional societies and government. "
                    "They are not advice about your own situation. Ask your care team about that."}


def all_links():
    links = [l for t in TOPICS for l in t["links"]] + MEDICINE_SAFETY["links"]
    return links
