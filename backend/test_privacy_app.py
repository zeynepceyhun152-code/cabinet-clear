"""
test_privacy_app.py - privacy tests run through your real app.py (account deletion, encryption at rest, upload clean-up).

Run from the backend folder:  python3 test_privacy_app.py     (temporary database; your real accounts are not touched)
"""
import glob
import io
import os
import sqlite3
import sys
import tempfile

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.pop("DATABASE_URL", None)
sys.path.insert(0, os.getcwd())
import crypto_store
import database
database.DB_PATH = os.path.join(tempfile.mkdtemp(), "pa.db")
database.init_db()
import security
security.set_secret("privacy-secret")
import app as appmod
from fastapi.testclient import TestClient

c = TestClient(appmod.app)
failures = []
V = "https://cabinet-clear-for-sunny-hacks.vercel.app"


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)


def fresh():
    security.window = security.SlidingWindow(); security.budget = security.DailyBudget()


def ip(n):
    return {"X-Forwarded-For": f"10.9.0.{n}"}


# ---------------------------------------------------------------- /health and encryption at rest
os.environ.pop("DATA_KEY", None)
check("/health says encryption is off when no key is set", c.get("/health").json()["encrypted"] is False)
os.environ["DATA_KEY"] = crypto_store.generate_key()
check("/health says encryption is on when a key is set", c.get("/health").json()["encrypted"] is True)

fresh()
for u, p in (("alice", "alice-pass-1"), ("bob", "bob-pass-123")):
    c.post("/auth/register", json={"username": u, "password": p}, headers=ip(1))
A = {"Authorization": "Bearer " + c.post("/auth/login", json={"username": "alice", "password": "alice-pass-1"}, headers=ip(2)).json()["token"], **ip(2)}
B = {"Authorization": "Bearer " + c.post("/auth/login", json={"username": "bob", "password": "bob-pass-123"}, headers=ip(3)).json()["token"], **ip(3)}
c.post("/history/save", json={"diagnosis": "Astım atağı", "letter_data": {"medications": [{"name": "Prednizolon"}]}, "cabinet_data": {}}, headers=A)
raw = sqlite3.connect(database.DB_PATH).execute("SELECT diagnosis, letter_payload, cabinet_payload FROM history").fetchall()
check("history saved through the app is scrambled in the database", len(raw) == 1 and all(x.startswith("enc1:") for x in raw[0]) and "Prednizolon" not in " ".join(raw[0]))
got = c.get("/history/get/alice", headers=A).json()["data"]
check("and the owner still reads it through the app", got[0]["diagnosis"] == "Astım atağı" and got[0]["letter_data"]["medications"][0]["name"] == "Prednizolon")

# ---------------------------------------------------------------- deleting an account
check("delete without a sign-in token is refused", c.request("DELETE", "/account", json={"password": "x"}, headers=ip(4)).status_code == 401)
r = c.request("DELETE", "/account", json={"password": "wrong-pass-1"}, headers=A)
check("delete with the wrong password is refused (403) and nothing is deleted", r.status_code == 403 and r.json()["error"] == "Incorrect password." and database.authenticate_user("alice", "alice-pass-1"))
check("the token decides WHOSE account: bob's token cannot delete alice's", c.request("DELETE", "/account", json={"password": "alice-pass-1"}, headers=B).status_code == 403 and database.authenticate_user("alice", "alice-pass-1"))
r = c.request("DELETE", "/account", json={"password": "alice-pass-1"}, headers=A)
check("delete with the right password works and says what was removed", r.status_code == 200 and r.json()["success"] and r.json()["deleted"] == {"history": 1, "account": 1})
check("the account can no longer sign in", c.post("/auth/login", json={"username": "alice", "password": "alice-pass-1"}, headers=ip(5)).status_code == 401)
check("its saved history is gone from the database", sqlite3.connect(database.DB_PATH).execute("SELECT count(*) FROM history").fetchone()[0] == 0)
check("the old token shows an empty history", c.get("/history/get/alice", headers=A).json()["data"] == [])
r = c.post("/history/save", json={"diagnosis": "x", "letter_data": {}, "cabinet_data": {}}, headers=A)
check("the old token can no longer save (no orphan records)", r.status_code == 401 and r.json()["error"] == security.MSG_EXPIRED)
check("bob's data is untouched", database.authenticate_user("bob", "bob-pass-123") is True)

fresh()
codes = [c.request("DELETE", "/account", json={"password": f"wrong-{i}-pass"}, headers={**B, "X-Forwarded-For": "10.9.9.9"}).status_code for i in range(security.LIMITS.login_failures_per_15min + 1)]
check("guessing the password through the delete button is locked out after 10 tries (429)", codes[:10] == [403] * 10 and codes[10] == 429)
check("the browser's permission check for DELETE from your Vercel page is allowed",
      c.options("/account", headers={"Origin": V, "Access-Control-Request-Method": "DELETE", "Access-Control-Request-Headers": "authorization,content-type,x-lang"}).status_code == 200)

# ---------------------------------------------------------------- uploaded letters and photos are always deleted
fresh()
tmpdir = tempfile.gettempdir()
def leftovers():
    return set(glob.glob(os.path.join(tmpdir, "tmp*.pdf")) + glob.glob(os.path.join(tmpdir, "tmp*.png")) + glob.glob(os.path.join(tmpdir, "tmp*.jpg")) + glob.glob(os.path.join(tmpdir, "tmp*.bin")))
def boom(*a, **k):
    raise RuntimeError("the AI is down")
appmod.extract_from_file = boom
appmod.extract_medicine_from_image = boom
before = leftovers()
r1 = c.post("/extract-letter", files={"file": ("letter.pdf", b"%PDF-1.4 fake medical letter", "application/pdf")}, headers=ip(20))
r2 = c.post("/scan-medicine", files={"file": ("label.png", b"\x89PNG fake", "image/png")}, headers=ip(21))
check("when reading a letter goes wrong, the server reports it", r1.status_code == 500 and r1.json()["success"] is False)
check("when reading a label goes wrong, the server reports it", r2.status_code == 500 and r2.json()["success"] is False)
check("a letter that could not be read leaves NO copy of the letter on the server's disk", leftovers() == before)
appmod.extract_from_file = lambda p, m: {"ok": True}
c.post("/extract-letter", files={"file": ("letter.pdf", b"%PDF-1.4 fake", "application/pdf")}, headers=ip(22))
check("a successful read also leaves nothing behind", leftovers() == before)
check("file names from visitors are not trusted", appmod._safe_suffix("x.PDF") == ".pdf" and appmod._safe_suffix("a.b/../../etc") == ".bin" and appmod._safe_suffix("../../x.sh") == ".bin" and appmod._safe_suffix(None) == ".bin")

print("\nALL PASSED" if not failures else "\nFAILED: " + ", ".join(failures))
sys.exit(1 if failures else 0)
