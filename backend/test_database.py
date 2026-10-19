"""
test_database.py - tests for accounts and history storage.

Run from the backend folder:  python3 test_database.py
It always tests the temporary SQLite file (in a throwaway folder). To also test Postgres, set TEST_DATABASE_URL
to a database you do not mind filling with test data, for example:
    TEST_DATABASE_URL="postgresql://user:pass@host/db?sslmode=require" python3 test_database.py
"""
import importlib
import os
import sys
import tempfile
import threading

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
sys.path.insert(0, os.getcwd())
failures = []


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)


def load(url=None):
    """A fresh copy of database.py using the given DATABASE_URL (or none)."""
    if url:
        os.environ["DATABASE_URL"] = url
    else:
        os.environ.pop("DATABASE_URL", None)
    import database
    database = importlib.reload(database)
    if not url:
        database.DB_PATH = os.path.join(tempfile.mkdtemp(), "t.db")
        database.init_db()
    return database


def run_suite(name, d, expect_kind, unique):
    u = lambda s: f"{s}_{unique}"
    print(f"\n--- {name} ---")
    check(f"{name}: storage is {expect_kind}", d.storage_kind() == expect_kind)
    check(f"{name}: new account", d.register_user(u("Alice"), "alice-pass-1") is True)
    check(f"{name}: same name again is refused (any capitalisation)", d.register_user(u("ALICE"), "other-pass-1") is False)
    check(f"{name}: right password works, any capitalisation of the name", d.authenticate_user(u("aLiCe"), "alice-pass-1") is True)
    check(f"{name}: wrong password refused", d.authenticate_user(u("alice"), "wrong-pass-1") is False)
    check(f"{name}: unknown user refused", d.authenticate_user(u("nobody"), "x") is False)
    check(f"{name}: a password longer than bcrypt allows is refused, not a crash", d.authenticate_user(u("alice"), "é" * 80) is False)
    check(f"{name}: a login that tries SQL tricks is just refused", d.authenticate_user("x' OR '1'='1' --", "x") is False)
    tricky = u("bob'; DROP TABLE users; --")
    check(f"{name}: a username full of SQL is stored as plain text", d.register_user(tricky, "bob-pass-123") is True and d.authenticate_user(tricky, "bob-pass-123") is True)
    check(f"{name}: the users table is still there afterwards", d.authenticate_user(u("alice"), "alice-pass-1") is True)

    d.save_history_record(u("alice"), "Asthma", {"medications": [{"name": "Albuterol"}]}, {"summary": {"keep": 1}})
    d.save_history_record(u("ALICE"), "Astım şğİıÇÖÜ 💊", {"x": "ü"}, {})
    h = d.fetch_user_history(u("alice"))
    check(f"{name}: both records saved under one user", len(h) == 2)
    check(f"{name}: newest first", h[0]["diagnosis"].startswith("Astım"))
    check(f"{name}: Turkish letters and emoji survive", h[0]["diagnosis"] == "Astım şğİıÇÖÜ 💊" and h[0]["letter_data"] == {"x": "ü"})
    check(f"{name}: records keep their structure", h[1]["letter_data"]["medications"][0]["name"] == "Albuterol" and h[1]["cabinet_data"]["summary"]["keep"] == 1)
    check(f"{name}: a different user's history is empty", d.fetch_user_history(u("bob")) == [])
    big = {"blob": "x" * 250_000}
    d.save_history_record(u("alice"), "Big", big, {})
    check(f"{name}: a 250 KB record is saved and read back", d.fetch_user_history(u("alice"))[0]["letter_data"] == big)

    # two people try to take the same name at the same moment: exactly one wins
    results = []
    race = u("racer")
    ts = [threading.Thread(target=lambda: results.append(d.register_user(race, "race-pass-1"))) for _ in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    check(f"{name}: 6 simultaneous sign-ups for one name: exactly one wins", results.count(True) == 1 and results.count(False) == 5)

    # "restart": load the module again and read the same data
    return d


tmpname = os.urandom(3).hex()
d = load()
run_suite("SQLite", d, "sqlite", tmpname)
path = d.DB_PATH
d2 = importlib.reload(d)
d2.DB_PATH = path
d2.init_db()
check("SQLite: data is still there after the module is reloaded (same file)", d2.authenticate_user(f"alice_{tmpname}", "alice-pass-1") is True)

url = os.environ.get("TEST_DATABASE_URL", "").strip()
if url:
    uniq = os.urandom(3).hex()
    d = load(url)
    run_suite("Postgres", d, "postgres", uniq)
    # "restart": a brand new load of the module must find the same accounts
    d = load(url)
    check("Postgres: accounts and history survive a restart", d.storage_kind() == "postgres" and d.authenticate_user(f"alice_{uniq}", "alice-pass-1") and len(d.fetch_user_history(f"alice_{uniq}")) == 3)
    # bad address: the server must still start, using the temporary file
    d = load("postgresql://nobody:wrong@127.0.0.1:1/none?sslmode=disable")
    d.DB_PATH = os.path.join(tempfile.mkdtemp(), "fb.db"); d.init_db()
    check("Postgres unreachable: falls back to SQLite instead of crashing", d.storage_kind() == "sqlite" and d.last_error)
    d = load("not a url")
    d.DB_PATH = os.path.join(tempfile.mkdtemp(), "fb2.db"); d.init_db()
    check("a malformed DATABASE_URL also falls back", d.storage_kind() == "sqlite")
else:
    print("\n(Postgres tests skipped: set TEST_DATABASE_URL to run them)")
os.environ.pop("DATABASE_URL", None)
print("\nALL PASSED" if not failures else "\nFAILED: " + ", ".join(failures))
sys.exit(1 if failures else 0)
