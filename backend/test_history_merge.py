"""
test_history_merge.py - one check = one history entry (letter read, changes compared, cabinet checked).
Run from the backend folder:  python3 test_history_merge.py     (temporary database; add TEST_DATABASE_URL to also test PostgreSQL)
"""
import importlib
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
sys.path.insert(0, os.getcwd())
import crypto_store
failures = []


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)


def fresh(url=None):
    if url:
        os.environ["DATABASE_URL"] = url
    else:
        os.environ.pop("DATABASE_URL", None)
    import database
    d = importlib.reload(database)
    if not url:
        d.DB_PATH = os.path.join(tempfile.mkdtemp(), "h.db"); d.init_db()
    return d


def suite(name, d, tag):
    u = lambda s: f"{s}_{tag}"
    os.environ["DATA_KEY"] = crypto_store.generate_key()
    d.register_user(u("maya"), "maya-pass-12"); d.register_user(u("zed"), "zed-pass-123")
    letter = {"diagnosis_summary": "Acute asthma exacerbation", "medications": [{"name": "Albuterol"}, {"name": "Prednisolone"}], "warning_signs": ["a", "b"]}
    d.save_history_record(u("maya"), "Acute asthma exacerbation", letter, {})
    h = d.fetch_user_history(u("maya"))
    check(f"{name}: reading the letter saves an entry right away", len(h) == 1 and h[0]["cabinet_data"] == {})
    changes = {"findings": [{"drug": "Zyrtec", "status": "stopped"}]}
    d.save_history_record(u("maya"), "Acute asthma exacerbation", letter, {"changes": changes})
    h = d.fetch_user_history(u("maya"))
    check(f"{name}: comparing changes updates that SAME entry (still 1)", len(h) == 1 and h[0]["cabinet_data"]["changes"] == changes)
    letter2 = dict(letter, urgency=[{"sign": "a", "level": "immediate"}])           # the page adds extra fields later
    crossref = {"summary": {"keep": 2}, "keep": [{"drug_name": "Albuterol"}]}
    d.save_history_record(u("maya"), "Acute asthma exacerbation", letter2, crossref)
    h = d.fetch_user_history(u("maya"))
    check(f"{name}: the cabinet check also lands in the same entry (still 1)", len(h) == 1)
    check(f"{name}: and the entry keeps the changes AND the cabinet result", h[0]["cabinet_data"]["changes"] == changes and h[0]["cabinet_data"]["summary"] == {"keep": 2})
    check(f"{name}: the newer version of the letter replaces the old one", h[0]["letter_data"].get("urgency") is not None)
    other = {"diagnosis_summary": "Heart failure", "medications": [{"name": "Furosemide"}]}
    d.save_history_record(u("maya"), "Heart failure", other, {})
    h = d.fetch_user_history(u("maya"))
    check(f"{name}: a DIFFERENT letter is a new entry (now 2), newest first", len(h) == 2 and h[0]["diagnosis"] == "Heart failure")
    d.save_history_record(u("maya"), "Acute asthma exacerbation", letter, {"changes": changes})
    check(f"{name}: an older letter saved again does not overwrite the newer entry (it is not the latest, so a new entry)", len(d.fetch_user_history(u("maya"))) == 3)
    d.save_history_record(u("zed"), "Acute asthma exacerbation", letter, {})
    check(f"{name}: another person's identical letter is theirs alone", len(d.fetch_user_history(u("zed"))) == 1 and len(d.fetch_user_history(u("maya"))) == 3)
    # a check from yesterday must not be merged into today's
    old = (datetime.now() - timedelta(hours=7)).isoformat()
    if name == "SQLite":
        c = sqlite3.connect(d.DB_PATH); c.execute("UPDATE history SET timestamp = ? WHERE username = ?", (old, u("zed"))); c.commit(); c.close()
    else:
        with d._conn() as c:
            c.cursor().execute("UPDATE history SET timestamp = %s WHERE username = %s", (old, u("zed")))
    d.save_history_record(u("zed"), "Acute asthma exacerbation", letter, {})
    check(f"{name}: the same letter 7 hours later is a new check, not a merge", len(d.fetch_user_history(u("zed"))) == 2)
    # still encrypted
    if name == "SQLite":
        rows = sqlite3.connect(d.DB_PATH).execute("SELECT diagnosis, letter_payload, cabinet_payload FROM history").fetchall()
    else:
        with d._conn() as c:
            cur = c.cursor(); cur.execute("SELECT diagnosis, letter_payload, cabinet_payload FROM history"); rows = cur.fetchall()
    check(f"{name}: merged entries are still encrypted in the database", all(str(x).startswith("enc1:") for r in rows for x in r))
    d.delete_user(u("zed"))
    try:
        d.save_history_record(u("zed"), "x", letter, {}); ok = False
    except ValueError:
        ok = True
    check(f"{name}: a deleted account still cannot save", ok)
    os.environ.pop("DATA_KEY", None)
    d.register_user(u("plain"), "plain-pass-12")
    d.save_history_record(u("plain"), "Asthma", letter, {}); d.save_history_record(u("plain"), "Asthma", letter, {"x": 1})
    check(f"{name}: merging also works with encryption turned off", len(d.fetch_user_history(u("plain"))) == 1)


suite("SQLite", fresh(), os.urandom(3).hex())
url = os.environ.get("TEST_DATABASE_URL", "").strip()
if url:
    suite("Postgres", fresh(url), os.urandom(3).hex())
else:
    print("(Postgres tests skipped: set TEST_DATABASE_URL to run them)")
os.environ.pop("DATABASE_URL", None); os.environ.pop("DATA_KEY", None)
print("\nALL PASSED" if not failures else "\nFAILED: " + ", ".join(failures))
sys.exit(1 if failures else 0)
