"""
test_privacy.py - tests for encryption, account deletion and upload clean-up. No API key or internet needed.

Run from the backend folder:  python3 test_privacy.py
Add TEST_DATABASE_URL="postgresql://..." to also test the permanent database (it fills it with test data).
"""
import base64
import importlib
import os
import sqlite3
import sys
import tempfile

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
sys.path.insert(0, os.getcwd())
import crypto_store as cs

failures = []


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)


K1, K2 = cs.generate_key(), cs.generate_key()
os.environ.pop("DATA_KEY", None)

# ---------------------------------------------------------------- the encryption itself
check("without a key, text is stored unchanged and 'enabled' is false", cs.encrypt("hello", "a|b") == "hello" and not cs.enabled())
os.environ["DATA_KEY"] = K1
check("with a key, 'enabled' is true", cs.enabled())
e = cs.encrypt("Astım şğİı 💊 Prednisolone 20mg", "alice|letter")
check("encrypted text starts with enc1: and hides the content", e.startswith("enc1:") and "Prednisolone" not in e and "Ast" not in e)
check("it opens again exactly", cs.decrypt(e, "alice|letter") == "Astım şğİı 💊 Prednisolone 20mg")
check("encrypting the same text twice gives different results (fresh random value each time)", cs.encrypt("x", "a|b") != cs.encrypt("x", "a|b"))
big = "x" * 400_000
check("a 400 KB text round-trips", cs.decrypt(cs.encrypt(big, "a|b"), "a|b") == big)
check("empty text round-trips", cs.decrypt(cs.encrypt("", "a|b"), "a|b") == "")
def fails(fn):
    try:
        fn(); return False
    except cs.DecryptError:
        return True
check("a record copied into another person's row will NOT open", fails(lambda: cs.decrypt(e, "bob|letter")))
check("a record moved into another field will NOT open", fails(lambda: cs.decrypt(e, "alice|cabinet")))
tampered = e[:-4] + ("AAAA" if not e.endswith("AAAA") else "BBBB")
check("a tampered record will NOT open", fails(lambda: cs.decrypt(tampered, "alice|letter")))
check("garbage after the prefix is refused cleanly", fails(lambda: cs.decrypt("enc1:!!!notbase64", "a|b")))
os.environ["DATA_KEY"] = K2
check("a different key will NOT open it", fails(lambda: cs.decrypt(e, "alice|letter")))
os.environ["DATA_KEY"] = f"{K2},{K1}"
check("rotation: new key first, old key kept: old data still opens", cs.decrypt(e, "alice|letter") == "Astım şğİı 💊 Prednisolone 20mg")
e2 = cs.encrypt("new", "a|b")
os.environ["DATA_KEY"] = K2
check("rotation: new data is written with the first key", cs.decrypt(e2, "a|b") == "new")
os.environ["DATA_KEY"] = "short,also-bad"
check("invalid keys are ignored (so encryption stays off, not broken)", not cs.enabled() and cs.encrypt("t", "a|b") == "t")
os.environ["DATA_KEY"] = K1
check("an old unencrypted value is returned as it is", cs.decrypt("plain old text", "a|b") == "plain old text")

# ---------------------------------------------------------------- the database
def fresh_db(url=None):
    if url:
        os.environ["DATABASE_URL"] = url
    else:
        os.environ.pop("DATABASE_URL", None)
    import database
    d = importlib.reload(database)
    if not url:
        d.DB_PATH = os.path.join(tempfile.mkdtemp(), "p.db")
        d.init_db()
    return d


def raw_rows(d):
    if d.storage_kind() == "sqlite":
        c = sqlite3.connect(d.DB_PATH); rows = c.execute("SELECT username, diagnosis, letter_payload, cabinet_payload FROM history").fetchall(); c.close(); return rows
    with d._conn() as c:
        cur = c.cursor(); cur.execute("SELECT username, diagnosis, letter_payload, cabinet_payload FROM history"); return cur.fetchall()


def db_suite(name, d, tag):
    n = lambda s: f"{s}_{tag}"
    os.environ["DATA_KEY"] = K1
    d.register_user(n("alice"), "alice-pass-1"); d.register_user(n("bob"), "bob-pass-123")
    d.save_history_record(n("alice"), "Astım atağı", {"medications": [{"name": "Prednizolon", "dosage": "20mg"}]}, {"summary": {"keep": 1}})
    rows = [r for r in raw_rows(d) if r[0] == n("alice")]
    blob = " ".join(str(x) for x in rows[0][1:])
    check(f"{name}: what is stored is scrambled (no medicine names, no diagnosis)", all(str(x).startswith("enc1:") for x in rows[0][1:]) and "Prednizolon" not in blob and "Astım" not in blob)
    h = d.fetch_user_history(n("alice"))
    check(f"{name}: but the owner reads it back normally", h[0]["diagnosis"] == "Astım atağı" and h[0]["letter_data"]["medications"][0]["name"] == "Prednizolon")

    # old records written before a key existed
    os.environ.pop("DATA_KEY", None)
    d.save_history_record(n("alice"), "Old plain record", {"old": True}, {})
    check(f"{name}: with no key, new records are plain (as before)", any(r[1] == "Old plain record" for r in raw_rows(d)))
    os.environ["DATA_KEY"] = K1
    check(f"{name}: with a key set, an old plain record still reads fine", any(x["diagnosis"] == "Old plain record" for x in d.fetch_user_history(n("alice"))))
    d.init_db()                                              # what happens at the next server start
    check(f"{name}: at start-up, old plain records get encrypted", all(str(x).startswith("enc1:") for r in raw_rows(d) for x in r[1:]))
    check(f"{name}: and they still read back", any(x["diagnosis"] == "Old plain record" for x in d.fetch_user_history(n("alice"))))

    # tampering and wrong keys never crash the app
    os.environ["DATA_KEY"] = K2
    check(f"{name}: with the wrong key, history is hidden instead of crashing", d.fetch_user_history(n("alice")) == [])
    os.environ["DATA_KEY"] = f"{K2},{K1}"
    check(f"{name}: with the old key kept, it reads again", len(d.fetch_user_history(n("alice"))) == 2)
    os.environ["DATA_KEY"] = K1

    # a record moved from alice's row into bob's must not open for bob
    a = raw_rows(d)[0]
    if name == "SQLite":
        c = sqlite3.connect(d.DB_PATH); c.execute("INSERT INTO history (username, timestamp, diagnosis, letter_payload, cabinet_payload) VALUES (?,?,?,?,?)", (n("bob"), "2026-01-01", a[1], a[2], a[3])); c.commit(); c.close()
    else:
        with d._conn() as c:
            c.cursor().execute("INSERT INTO history (username, timestamp, diagnosis, letter_payload, cabinet_payload) VALUES (%s,%s,%s,%s,%s)", (n("bob"), "2026-01-01", a[1], a[2], a[3]))
    check(f"{name}: a record copied into another user's row does not open there", d.fetch_user_history(n("bob")) == [])

    # deleting an account
    r = d.delete_user(n("alice").upper())
    check(f"{name}: delete removes the account and its records and says how many", r["account"] == 1 and r["history"] == 2)
    check(f"{name}: the deleted account can no longer sign in", d.authenticate_user(n("alice"), "alice-pass-1") is False)
    check(f"{name}: its history is gone", d.fetch_user_history(n("alice")) == [] and all(r[0] != n("alice") for r in raw_rows(d)))
    try:
        d.save_history_record(n("alice"), "x", {}, {}); saved = True
    except ValueError:
        saved = False
    check(f"{name}: saving into a deleted account is refused (no orphan records)", not saved)
    check(f"{name}: the other user is untouched", d.authenticate_user(n("bob"), "bob-pass-123") is True)
    check(f"{name}: deleting something that does not exist is harmless", d.delete_user(n("nobody")) == {"history": 0, "account": 0})
    check(f"{name}: the name can be used again", d.register_user(n("alice"), "fresh-pass-12") is True)


tag = os.urandom(3).hex()
db_suite("SQLite", fresh_db(), tag)
url = os.environ.get("TEST_DATABASE_URL", "").strip()
if url:
    db_suite("Postgres", fresh_db(url), os.urandom(3).hex())
else:
    print("(Postgres tests skipped: set TEST_DATABASE_URL to run them)")
os.environ.pop("DATABASE_URL", None); os.environ.pop("DATA_KEY", None)
print("\nALL PASSED" if not failures else "\nFAILED: " + ", ".join(failures))
sys.exit(1 if failures else 0)
