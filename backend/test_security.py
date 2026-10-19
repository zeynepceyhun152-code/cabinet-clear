"""
test_security.py - tests for the security changes, run against your real app.py. No API key or internet needed.

Run from the backend folder:  python3 test_security.py
(It uses a temporary database, so your real accounts are not touched.)
"""
import os
import sys
import tempfile
import time
import types

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
sys.path.insert(0, os.getcwd())

import database
database.DB_PATH = os.path.join(tempfile.mkdtemp(), "test.db")
database.init_db()

import security
security.set_secret("test-secret")
import app as appmod
from fastapi.testclient import TestClient

c = TestClient(appmod.app)
failures = []
VERCEL = "https://cabinet-clear-for-sunny-hacks.vercel.app"


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)
    if not ok:
        failures.append(label)


def fresh():
    security.window = security.SlidingWindow()
    security.budget = security.DailyBudget()


def ip(n):
    return {"X-Forwarded-For": f"10.0.0.{n}"}


# ---------------------------------------------------------------- tokens
t = security.issue_token("Zeynep")
check("a token reads back as the lowercase user", security.read_token(t) == ("zeynep", None))
check("a changed token is rejected", security.read_token(t[:-3] + "abc")[0] is None and security.read_token("x.y")[0] is None)
check("a token from another secret is rejected", security.read_token(t.replace(t.split(".")[1], "AAAA"))[1] == "invalid")
check("an old token says expired", security.read_token(security.issue_token("a", now=time.time() - 10 * 24 * 3600))[1] == "expired")
check("no token says missing", security.read_token("")[1] == "missing")
check("username rules", security.valid_username("zeynep_c.1") and not security.valid_username("ab") and not security.valid_username("bad name") and not security.valid_username("x" * 33))
check("password rules", security.valid_password("12345678") and not security.valid_password("short") and not security.valid_password("é" * 40))

# ---------------------------------------------------------------- limiter
w = security.SlidingWindow()
check("limiter allows up to the limit", all(w.check("k", 3, 60, now=100 + i)[0] for i in range(3)))
ok, wait = w.check("k", 3, 60, now=103)
check("limiter blocks the next one and says how long to wait", not ok and 55 <= wait <= 60)
check("limiter allows again after the window", w.check("k", 3, 60, now=161)[0])
check("limiter keys are separate", w.check("other", 3, 60, now=103)[0])
b = security.DailyBudget()
check("daily budget runs out and resets next day", b.take(2, "d1") and b.take(2, "d1") and not b.take(2, "d1") and b.take(2, "d2"))

# ---------------------------------------------------------------- sign-in and history
fresh()
r = c.post("/auth/register", json={"username": "ab", "password": "longenough1"}, headers=ip(1))
check("register rejects a short username", r.status_code == 400 and "Username must be" in r.json()["error"])
r = c.post("/auth/register", json={"username": "alice", "password": "short"}, headers=ip(1))
check("register rejects a short password", r.status_code == 400 and "Password must be" in r.json()["error"])
check("register works", c.post("/auth/register", json={"username": "alice", "password": "alice-pass-1"}, headers=ip(1)).json()["success"])
check("register works for a second user", c.post("/auth/register", json={"username": "bob", "password": "bob-pass-123"}, headers=ip(1)).json()["success"])
check("duplicate username is refused", c.post("/auth/register", json={"username": "ALICE", "password": "alice-pass-1"}, headers=ip(1)).status_code == 400)
check("wrong password is refused", c.post("/auth/login", json={"username": "alice", "password": "nope-nope-1"}, headers=ip(2)).status_code == 401)
r = c.post("/auth/login", json={"username": "alice", "password": "alice-pass-1"}, headers=ip(2)).json()
check("login returns a token", r["success"] and r["username"] == "alice" and security.read_token(r["token"])[0] == "alice")
A = {"Authorization": "Bearer " + r["token"], **ip(2)}
rb = c.post("/auth/login", json={"username": "bob", "password": "bob-pass-123"}, headers=ip(3)).json()
B = {"Authorization": "Bearer " + rb["token"], **ip(3)}

rec = {"diagnosis": "Asthma", "letter_data": {"medications": [{"name": "Albuterol"}]}, "cabinet_data": {}}
check("saving history without a token is refused", c.post("/history/save", json=rec, headers=ip(4)).status_code == 401)
check("saving history with a token works", c.post("/history/save", json=rec, headers=A).json()["success"])
check("reading history without a token is refused", c.get("/history/get/alice", headers=ip(4)).status_code == 401)
got = c.get("/history/get/alice", headers=A).json()
check("alice can read her own history", got["success"] and got["data"][0]["diagnosis"] == "Asthma")
check("username in the address is not case sensitive", c.get("/history/get/Alice", headers=A).json()["success"])
r = c.get("/history/get/alice", headers=B)
check("bob CANNOT read alice's history", r.status_code == 403 and r.json()["error"] == security.MSG_OWN_ONLY)
check("bob's history is empty", c.get("/history/get/bob", headers=B).json()["data"] == [])
rec2 = dict(rec, username="alice", diagnosis="Written by bob")
c.post("/history/save", json=rec2, headers=B)
check("bob cannot write into alice's history by naming her", all(x["diagnosis"] != "Written by bob" for x in c.get("/history/get/alice", headers=A).json()["data"]))
check("a made-up token is refused", c.get("/history/get/alice", headers={"Authorization": "Bearer nonsense.token", **ip(5)}).status_code == 401)
old = security.issue_token("alice", now=time.time() - 30 * 24 * 3600)
r = c.get("/history/get/alice", headers={"Authorization": "Bearer " + old, **ip(5)})
check("an expired token gets a clear message", r.status_code == 401 and r.json()["error"] == security.MSG_EXPIRED)

# ---------------------------------------------------------------- password guessing
fresh()
codes = [c.post("/auth/login", json={"username": "alice", "password": f"wrong-{i}-pass"}, headers=ip(9)).status_code for i in range(security.LIMITS.login_failures_per_15min + 2)]
check("10 wrong passwords are allowed, then locked out (429)", codes[:10] == [401] * 10 and codes[10] == 429)
check("another visitor can still sign in", c.post("/auth/login", json={"username": "alice", "password": "alice-pass-1"}, headers=ip(10)).json()["success"])

# ---------------------------------------------------------------- AI limits
fresh()
calls = []
appmod.extract_from_text = lambda text: calls.append(text) or {"medications": [{"name": "Lisinopril"}]}
old_limit = security.LIMITS.ai_per_10min
security.LIMITS.ai_per_10min = 3
H = {"Origin": VERCEL, **ip(20)}
rs = [c.post("/parse-med-list", json={"text": "Lisinopril 10 mg"}, headers=H) for _ in range(4)]
check("3 AI calls pass, the 4th is stopped (429)", [r.status_code for r in rs] == [200, 200, 200, 429])
check("the stopped request never reached the AI", len(calls) == 3)
check("the 429 carries our message and a wait time", rs[3].json()["error"] == security.MSG_TOO_MANY and int(rs[3].headers["retry-after"]) > 0)
check("the 429 can be read by your page (CORS header present)", rs[3].headers.get("access-control-allow-origin") == VERCEL)
check("a different visitor is not affected", c.post("/parse-med-list", json={"text": "x"}, headers={"Origin": VERCEL, **ip(21)}).status_code == 200)
security.LIMITS.ai_per_10min = old_limit

fresh()
old_cap = security.LIMITS.daily_ai_calls
security.LIMITS.daily_ai_calls = 2
rs = [c.post("/parse-med-list", json={"text": "x"}, headers=ip(30 + i)) for i in range(3)]
check("daily cap: 2 calls pass, the 3rd gets 503 even from a new visitor", [r.status_code for r in rs] == [200, 200, 503])
check("the 503 says to try tomorrow", rs[2].json()["error"] == security.MSG_DAILY)
security.LIMITS.daily_ai_calls = old_cap

fresh()
check("calculations that do not use the AI are not counted against the daily cap",
      all(c.post("/reconcile", json={"before": [], "after": []}, headers=ip(40)).status_code == 200 for _ in range(5)) and security.budget.used() == 0)

# ---------------------------------------------------------------- size limits
fresh()
r = c.post("/parse-med-list", content=b"x" * (security.LIMITS.max_json_bytes + 10), headers={"Content-Type": "application/json", **ip(50)})
check("an oversized JSON request is refused (413)", r.status_code == 413)
r = c.post("/extract-letter", content=b"x" * (security.LIMITS.max_upload_bytes + 10), headers={"Content-Type": "multipart/form-data; boundary=x", **ip(51)})
check("an oversized upload is refused (413)", r.status_code == 413)
import extraction
try:
    extraction.extract_from_text("a" * (extraction.MAX_LETTER_CHARS + 1)); too_long = False
except ValueError as e:
    too_long = "too long" in str(e)
check("a huge pasted letter is refused before it reaches the AI", too_long)

# ---------------------------------------------------------------- browser rules (CORS)
r = c.get("/", headers={"Origin": VERCEL})
check("your Vercel page is allowed", r.headers.get("access-control-allow-origin") == VERCEL)
check("a Vercel preview address of your project is allowed", c.get("/", headers={"Origin": "https://cabinet-clear-git-main-zeynep.vercel.app"}).headers.get("access-control-allow-origin"))
check("another website is NOT allowed", c.get("/", headers={"Origin": "https://evil.example.com"}).headers.get("access-control-allow-origin") is None)
check("a look-alike address is NOT allowed", c.get("/", headers={"Origin": "https://cabinet-clear.vercel.app.evil.com"}).headers.get("access-control-allow-origin") is None)
r = c.options("/history/get/alice", headers={"Origin": VERCEL, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization,x-lang"})
check("the browser's permission check allows the Authorization and X-Lang headers", r.status_code == 200 and "authorization" in r.headers.get("access-control-allow-headers", "").lower())
fresh(); security.LIMITS.ai_per_10min = 1
c.post("/parse-med-list", json={"text": "x"}, headers=ip(60))
check("permission checks (OPTIONS) are never counted or blocked", all(c.options("/parse-med-list", headers={"Origin": VERCEL, "Access-Control-Request-Method": "POST", **ip(60)}).status_code == 200 for _ in range(5)))
security.LIMITS.ai_per_10min = old_limit

# ---------------------------------------------------------------- the rest still works
fresh()
check("the status page works", c.get("/").json() == {"status": "Cabinet Clear API is running"})
check("language header still works alongside", c.post("/reconcile", json={"before": [], "after": []}, headers={"X-Lang": "tr", **ip(70)}).status_code == 200)
check("the PDF download still works", c.post("/generate-pdf", json={"discharge_data": {"diagnosis_summary": "x"}, "cross_ref_result": {"summary": {}}, "interactions": []}, headers=ip(71)).status_code == 200)

print("\nALL PASSED" if not failures else "\nFAILED: " + ", ".join(failures))
sys.exit(1 if failures else 0)
