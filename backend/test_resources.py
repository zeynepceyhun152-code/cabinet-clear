"""
test_resources.py - checks on the "learn more" reading list. No internet needed.

Run:  python3 test_resources.py

These tests check the matching rules and the list's hygiene (secure links, approved sites only,
no duplicates). They do NOT check that pages still open. Run check_links.py for that.
"""
import sys
from urllib.parse import urlparse

from resources import find_resources, all_links, ALLOWED_DOMAINS, TOPICS
from sample_letters import SAMPLES

failures = []


def check(label, ok):
    if not ok:
        failures.append(label)
    return ok


def topics_for(data):
    return [g["id"] for g in find_resources(data)["groups"] if g["id"] != "medicine_safety"]


EXPECTED = {"asthma": ["asthma"], "appendectomy": ["appendectomy"], "heart_failure": ["heart_failure", "type2_diabetes"],
            "newborn": ["newborn"], "fracture": ["fracture"]}
ok = 0
for name, want in EXPECTED.items():
    got = topics_for(SAMPLES[name])
    ok += check(f"topics {name}: {got}", got == want)
print(f"1. sample letters get the right topics: {ok}/{len(EXPECTED)}")

none = {"diagnosis_summary": "A routine visit.", "medications": [], "warning_signs": [], "follow_up_appointments": []}
check("no-topic letter still gets medicine safety", [g["id"] for g in find_resources(none)["groups"]] == ["medicine_safety"])
check("empty data does not crash", bool(find_resources({})["groups"]) and bool(find_resources(None)["groups"]))
cap = {"diagnosis_summary": "asthma, appendicitis, heart failure, diabetes, newborn, fracture"}
check("topic cap respected", len(topics_for(cap)) == 3)
check("'broadcast' does not match cast", "fracture" not in topics_for({"diagnosis_summary": "heard a broadcast"}))
print("2. edge cases: ok" if not failures else "2. edge cases: FAILED")

links = all_links()
urls = [l["url"] for l in links]
check("all https", all(u.startswith("https://") for u in urls))
check("only approved sites", all(urlparse(u).netloc in ALLOWED_DOMAINS for u in urls))
check("no duplicate urls", len(urls) == len(set(urls)))
check("no tracking or preview parameters", all("?" not in u for u in urls))
check("every link has title, org, kind, checked", all(all(l.get(k) for k in ("title", "org", "kind", "url", "checked")) for l in links))
check("every topic has at least one link", all(t["links"] for t in TOPICS))
print(f"3. list hygiene: {len(links)} links, {len(set(urlparse(u).netloc for u in urls))} sites")

print("\nALL PASSED" if not failures else "\nFAILED: " + ", ".join(failures))
sys.exit(1 if failures else 0)
