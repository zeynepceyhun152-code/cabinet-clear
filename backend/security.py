"""
security.py - protects the live app.

  1. Sign-in tokens: login hands the page a signed token. History can only be read or saved with a valid
     token, and only for that user. (Before, anyone who knew a username could read its history.)
  2. Speed limits per visitor, so nobody can hammer the server or guess passwords.
  3. A daily cap on AI calls, so a bot cannot run up your Claude bill.
  4. Size limits on uploads and requests.

Limits can be changed without editing code, with environment variables in Render (see LIMITS below).
IP limits are speed bumps: they can be dodged. The daily cap, and the spend limit you set in the Anthropic
console, are the real protection for your bill.
"""
import base64
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi.responses import JSONResponse

# ---------------------------------------------------------------- settings
def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Limits:
    ai_per_10min = _int("AI_LIMIT_PER_10MIN", 40)             # letter reading, label reading, explanations...
    clarity_per_10min = _int("CLARITY_LIMIT_PER_10MIN", 60)   # the photo-clarity model
    other_per_10min = _int("OTHER_LIMIT_PER_10MIN", 150)      # everything else that changes something
    register_per_hour = _int("REGISTER_LIMIT_PER_HOUR", 10)
    login_failures_per_15min = _int("LOGIN_FAILURES_PER_15MIN", 10)
    daily_ai_calls = _int("DAILY_AI_CALLS", 600)              # across ALL visitors
    max_upload_bytes = _int("MAX_UPLOAD_MB", 10) * 1024 * 1024 + 512 * 1024
    max_json_bytes = _int("MAX_JSON_KB", 300) * 1024
    token_ttl_seconds = _int("TOKEN_DAYS", 7) * 24 * 3600


LIMITS = Limits

AI_PATHS = {"/extract-letter", "/scan-medicine", "/scan-cabinet", "/parse-med-list", "/explain", "/score-urgency"}
UPLOAD_PATHS = {"/extract-letter", "/scan-medicine", "/scan-cabinet", "/check-clarity"}
CLARITY_PATH = "/check-clarity"
PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

_origins_env = os.environ.get("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in _origins_env.split(",") if o.strip()] or [
    "https://cabinet-clear-for-sunny-hacks.vercel.app",
    "https://cabinet-clear-with-a-better-frontend.onrender.com",
    "https://cabinet-clear.onrender.com",
    "http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:8000", "http://127.0.0.1:8000",
]
# preview deployments of your Vercel project (cabinet-clear-something.vercel.app)
ORIGIN_REGEX = os.environ.get("ALLOWED_ORIGIN_REGEX", r"^https://cabinet-clear[a-z0-9-]*\.vercel\.app$")

MSG_SIGN_IN = "Please sign in first to view history."
MSG_EXPIRED = "Your session has expired. Please sign in again."
MSG_OWN_ONLY = "You can only see your own history."
MSG_TOO_MANY = "Too many requests. Please wait a few minutes and try again."
MSG_DAILY = "The service has reached its daily limit. Please try again tomorrow."
MSG_TOO_LARGE = "That file is too large."
MSG_LOGIN_LOCK = "Too many failed sign-in attempts. Please wait 15 minutes."
USERNAME_RULE = "Username must be 3 to 32 characters: letters, numbers, dot, dash or underscore."
PASSWORD_RULE = "Password must be 8 to 72 characters."

# ---------------------------------------------------------------- tokens
_secret = (os.environ.get("AUTH_SECRET") or "").encode()
if not _secret:
    _secret = secrets.token_bytes(32)
    print("Note: AUTH_SECRET is not set, so sign-in tokens reset every time the server restarts.")


def set_secret(value):
    global _secret
    _secret = value.encode() if isinstance(value, str) else value


def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue_token(username, now=None):
    payload = {"u": str(username).strip().lower(), "exp": int((now if now is not None else time.time()) + LIMITS.token_ttl_seconds)}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def read_token(token, now=None):
    """Returns (username, None) for a good token, or (None, reason) where reason is 'missing', 'invalid' or 'expired'."""
    if not token:
        return None, "missing"
    try:
        body, sig = token.split(".", 1)
        want = _b64(hmac.new(_secret, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, want):
            return None, "invalid"
        payload = json.loads(_unb64(body))
        if payload["exp"] < (now if now is not None else time.time()):
            return None, "expired"
        return payload["u"], None
    except Exception:
        return None, "invalid"


def user_from_request(request):
    """(username, None) when the request carries a good token, else (None, message to show the user)."""
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    user, why = read_token(token)
    if user:
        return user, None
    return None, (MSG_EXPIRED if why == "expired" else MSG_SIGN_IN)


def valid_username(name):
    return bool(re.fullmatch(r"[A-Za-z0-9._-]{3,32}", name or ""))


def valid_password(pw):
    return bool(pw) and 8 <= len(pw) and len(pw.encode("utf-8")) <= 72


# ---------------------------------------------------------------- limits
class SlidingWindow:
    """Counts events per key inside a time window. Thread safe. Forgets old keys."""

    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_prune = time.time()

    def _trim(self, dq, window, now):
        while dq and dq[0] <= now - window:
            dq.popleft()

    def check(self, key, limit, window, now=None, record=True):
        """(allowed, seconds_to_wait). Records the event when allowed and record=True."""
        now = now if now is not None else time.time()
        with self._lock:
            dq = self._hits[key]
            self._trim(dq, window, now)
            if len(dq) >= limit:
                return False, max(1, math.ceil(dq[0] + window - now))
            if record:
                dq.append(now)
            if now - self._last_prune > 600:
                for k in [k for k, v in self._hits.items() if not v or v[-1] <= now - 3600]:
                    del self._hits[k]
                self._last_prune = now
            return True, 0

    def record(self, key, now=None):
        with self._lock:
            self._hits[key].append(now if now is not None else time.time())

    def count(self, key, window, now=None):
        now = now if now is not None else time.time()
        with self._lock:
            dq = self._hits[key]
            self._trim(dq, window, now)
            return len(dq)


class DailyBudget:
    def __init__(self):
        self._day = None
        self._used = 0
        self._lock = threading.Lock()

    def take(self, cap, today=None):
        today = today or time.strftime("%Y-%m-%d", time.gmtime())
        with self._lock:
            if today != self._day:
                self._day, self._used = today, 0
            if self._used >= cap:
                return False
            self._used += 1
            return True

    def used(self):
        return self._used


window = SlidingWindow()
budget = DailyBudget()


def client_ip(request):
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _origin_ok(origin):
    return bool(origin) and (origin in ALLOWED_ORIGINS or bool(re.match(ORIGIN_REGEX, origin)))


def _blocked(request, status, message, retry_after=None):
    headers = {}
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    origin = request.headers.get("origin")
    if _origin_ok(origin):     # so the browser can show our message instead of a vague network error
        headers["Access-Control-Allow-Origin"] = origin
        headers["Vary"] = "Origin"
    return JSONResponse(status_code=status, content={"success": False, "error": message}, headers=headers)


def install(app):
    @app.middleware("http")
    async def guard(request, call_next):
        if request.method == "OPTIONS":                     # the browser's permission check: always let it through
            return await call_next(request)
        path = request.url.path
        method = request.method
        ip = client_ip(request)

        # 1. size
        if method in PROTECTED_METHODS:
            try:
                size = int(request.headers.get("content-length", "0"))
            except ValueError:
                size = 0
            cap = LIMITS.max_upload_bytes if path in UPLOAD_PATHS else LIMITS.max_json_bytes
            if size > cap:
                return _blocked(request, 413, MSG_TOO_LARGE)

        # 2. password guessing
        if (path == "/auth/login" and method == "POST") or (path == "/account" and method == "DELETE"):
            if window.count(f"loginfail:{ip}", 900) >= LIMITS.login_failures_per_15min:
                return _blocked(request, 429, MSG_LOGIN_LOCK, 900)
        if path == "/auth/register" and method == "POST":
            ok, wait = window.check(f"register:{ip}", LIMITS.register_per_hour, 3600)
            if not ok:
                return _blocked(request, 429, MSG_TOO_MANY, wait)

        # 3. AI calls: per visitor, then for the whole service per day
        if path in AI_PATHS and method == "POST":
            ok, wait = window.check(f"ai:{ip}", LIMITS.ai_per_10min, 600)
            if not ok:
                return _blocked(request, 429, MSG_TOO_MANY, wait)
            if not budget.take(LIMITS.daily_ai_calls):
                return _blocked(request, 503, MSG_DAILY, 3600)
        elif path == CLARITY_PATH and method == "POST":
            ok, wait = window.check(f"clarity:{ip}", LIMITS.clarity_per_10min, 600)
            if not ok:
                return _blocked(request, 429, MSG_TOO_MANY, wait)
        elif method in PROTECTED_METHODS or path.startswith("/history/"):
            if path not in ("/auth/login", "/auth/register"):
                ok, wait = window.check(f"other:{ip}", LIMITS.other_per_10min, 600)
                if not ok:
                    return _blocked(request, 429, MSG_TOO_MANY, wait)

        response = await call_next(request)
        if (path == "/auth/login" and method == "POST" and response.status_code == 401) or \
           (path == "/account" and method == "DELETE" and response.status_code == 403):
            window.record(f"loginfail:{ip}")
        return response
