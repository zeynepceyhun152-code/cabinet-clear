"""
database.py - accounts and saved history.

Two places the data can live:
  * Postgres (permanent): used when the environment variable DATABASE_URL is set (for example a free Neon
    database). Accounts and history survive restarts and new deploys.
  * SQLite file (temporary on Render's free plan): used when DATABASE_URL is not set, or if the Postgres
    database cannot be reached when the server starts. It works, but the file is wiped when Render restarts.

The functions and their names are unchanged, so the rest of the app does not change.
Passwords are stored as bcrypt hashes in both places.
"""
import json
import os
import sqlite3
import ssl
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from urllib.parse import parse_qs, unquote, urlparse

import bcrypt

import crypto_store

DB_PATH = os.path.join(os.path.dirname(__file__), "cabinet_clear.db")   # the temporary SQLite file
_use_pg = False
last_error = None


# ---------------------------------------------------------------- connecting
def _pg_settings():
    url = urlparse(os.environ.get("DATABASE_URL", "").strip())
    if url.scheme not in ("postgres", "postgresql") or not url.hostname:
        raise ValueError("DATABASE_URL must look like postgresql://user:password@host/database")
    q = parse_qs(url.query)
    mode = (q.get("sslmode", ["require"])[0] or "require").lower()
    ctx = None
    if mode != "disable":
        ctx = ssl.create_default_context()
        if mode in ("allow", "prefer", "require") and url.hostname in ("localhost", "127.0.0.1"):
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
    return {"user": unquote(url.username or ""), "password": unquote(url.password or ""), "host": url.hostname,
            "port": url.port or 5432, "database": (url.path or "/").lstrip("/") or "postgres", "ssl_context": ctx}


def _pg_connect(attempts=2):
    import pg8000.dbapi as pg           # pure Python driver: nothing to compile on Render
    cfg = _pg_settings()
    for i in range(attempts):
        try:
            return pg.connect(timeout=10, **cfg)
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(1.5)             # free databases can take a moment to wake up


@contextmanager
def _conn():
    c = _pg_connect() if _use_pg else sqlite3.connect(DB_PATH)
    try:
        yield c
        c.commit()
    except Exception:
        try:
            c.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            c.close()
        except Exception:
            pass


def _sql(text):
    return text.replace("?", "%s") if _use_pg else text


def _is_duplicate(err):
    if isinstance(err, sqlite3.IntegrityError):
        return True
    first = err.args[0] if getattr(err, "args", None) else None
    return isinstance(first, dict) and first.get("C") == "23505"      # Postgres: unique violation


def _enc(value, user, field):
    return crypto_store.encrypt(value, f"{user}|{field}")


def _dec(value, user, field):
    return crypto_store.decrypt(value, f"{user}|{field}")


def encryption_enabled():
    return crypto_store.enabled()


def _ensure_encrypted(value, user, field):
    return value if crypto_store.is_encrypted(value) else _enc(value or "", user, field)


def _encrypt_old_rows():
    """When a key is set for the first time, encrypt history saved before it existed."""
    if not crypto_store.enabled():
        return 0
    changed = 0
    with _conn() as c:
        cur = c.cursor()
        cur.execute("SELECT id, username, diagnosis, letter_payload, cabinet_payload FROM history")
        rows = cur.fetchall()
        for rid, user, dg, lp, cp in rows:
            if crypto_store.is_encrypted(dg) and crypto_store.is_encrypted(lp) and crypto_store.is_encrypted(cp):
                continue
            c.cursor().execute(_sql("UPDATE history SET diagnosis = ?, letter_payload = ?, cabinet_payload = ? WHERE id = ?"),
                               (_ensure_encrypted(dg, user, "diagnosis"), _ensure_encrypted(lp, user, "letter"),
                                _ensure_encrypted(cp, user, "cabinet"), rid))
            changed += 1
    return changed


# ---------------------------------------------------------------- setup
def init_db():
    """Create the tables. Chooses Postgres when DATABASE_URL is set and reachable, otherwise SQLite."""
    global _use_pg, last_error
    last_error = None
    _use_pg = False
    if os.environ.get("DATABASE_URL", "").strip():
        try:
            _use_pg = True
            with _conn() as c:
                cur = c.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)")
                cur.execute("CREATE TABLE IF NOT EXISTS history (id BIGSERIAL PRIMARY KEY, username TEXT NOT NULL "
                            "REFERENCES users(username) ON DELETE CASCADE, timestamp TEXT NOT NULL, diagnosis TEXT, "
                            "letter_payload TEXT, cabinet_payload TEXT)")
                cur.execute("CREATE INDEX IF NOT EXISTS history_user_time ON history (username, timestamp DESC)")
            _safe_encrypt_old_rows()
            return
        except Exception as e:
            _use_pg = False
            last_error = str(e)[:200]
            print(f"WARNING: could not use DATABASE_URL ({last_error}). Using the temporary SQLite file instead; "
                  "accounts will be lost when the server restarts.")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)")
    cur.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, "
                "timestamp TEXT NOT NULL, diagnosis TEXT, letter_payload TEXT, cabinet_payload TEXT, "
                "FOREIGN KEY(username) REFERENCES users(username))")
    conn.commit()
    conn.close()
    _safe_encrypt_old_rows()


def _safe_encrypt_old_rows():
    try:
        n = _encrypt_old_rows()
        if n:
            print(f"Encrypted {n} saved history record(s) that were stored before a key was set.")
    except Exception as e:
        print("WARNING: could not encrypt older history records:", str(e)[:150])


def storage_kind():
    return "postgres" if _use_pg else "sqlite"


# ---------------------------------------------------------------- accounts
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def register_user(username: str, password: str) -> bool:
    try:
        with _conn() as c:
            c.cursor().execute(_sql("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)"),
                               (username.lower().strip(), hash_password(password), datetime.now().isoformat()))
        return True
    except Exception as e:
        if _is_duplicate(e):
            return False
        raise


def authenticate_user(username: str, password: str) -> bool:
    with _conn() as c:
        cur = c.cursor()
        cur.execute(_sql("SELECT password_hash FROM users WHERE username = ?"), (username.lower().strip(),))
        row = cur.fetchone()
    if row is None:
        return False
    try:
        return bcrypt.checkpw(password.encode(), row[0].encode())
    except ValueError:                  # for example a password longer than bcrypt allows
        return False


# ---------------------------------------------------------------- history
SAME_CHECK_HOURS = 6


def _fingerprint(letter):
    """What identifies a letter: its summary and its medicine names (they stay the same while the page adds extra fields)."""
    if not isinstance(letter, dict):
        return None
    meds = letter.get("medications") or []
    names = sorted(str((m or {}).get("name", "")).strip().lower() for m in meds if isinstance(m, dict))
    return (str(letter.get("diagnosis_summary", "")).strip().lower(), tuple(names))


def save_history_record(username: str, diagnosis: str, letter: dict, cabinet: dict):
    user = username.lower().strip()
    now = datetime.now()
    with _conn() as c:
        cur = c.cursor()
        cur.execute(_sql("SELECT 1 FROM users WHERE username = ?"), (user,))
        if cur.fetchone() is None:
            raise ValueError("Account not found")          # for example, an account that was deleted
        # The same letter saved again a little later is the SAME check. Update that entry, keeping what it holds.
        cur.execute(_sql("SELECT id, timestamp, letter_payload, cabinet_payload FROM history WHERE username = ? ORDER BY id DESC LIMIT 1"), (user,))
        last = cur.fetchone()
        if last is not None:
            try:
                recent = (now - datetime.fromisoformat(last[1])) < timedelta(hours=SAME_CHECK_HOURS)
                same = recent and _fingerprint(json.loads(_dec(last[2], user, "letter"))) == _fingerprint(letter)
                old_cabinet = json.loads(_dec(last[3], user, "cabinet")) if same else {}
            except (crypto_store.DecryptError, ValueError, TypeError):
                same, old_cabinet = False, {}
            if same:
                merged = {**(old_cabinet if isinstance(old_cabinet, dict) else {}), **(cabinet if isinstance(cabinet, dict) else {})}
                cur.execute(_sql("UPDATE history SET timestamp = ?, diagnosis = ?, letter_payload = ?, cabinet_payload = ? WHERE id = ?"),
                            (now.isoformat(), _enc(diagnosis or "", user, "diagnosis"), _enc(json.dumps(letter), user, "letter"),
                             _enc(json.dumps(merged), user, "cabinet"), last[0]))
                return
        cur.execute(
            _sql("INSERT INTO history (username, timestamp, diagnosis, letter_payload, cabinet_payload) VALUES (?, ?, ?, ?, ?)"),
            (user, now.isoformat(), _enc(diagnosis or "", user, "diagnosis"),
             _enc(json.dumps(letter), user, "letter"), _enc(json.dumps(cabinet), user, "cabinet")))


def fetch_user_history(username: str) -> list:
    user = username.lower().strip()
    with _conn() as c:
        cur = c.cursor()
        cur.execute(_sql("SELECT timestamp, diagnosis, letter_payload, cabinet_payload FROM history "
                         "WHERE username = ? ORDER BY timestamp DESC"), (user,))
        rows = cur.fetchall()
    out, skipped = [], 0
    for ts, dg, lp, cp in rows:
        try:
            out.append({"timestamp": ts, "diagnosis": _dec(dg, user, "diagnosis"),
                        "letter_data": json.loads(_dec(lp, user, "letter")), "cabinet_data": json.loads(_dec(cp, user, "cabinet"))})
        except (crypto_store.DecryptError, ValueError):
            skipped += 1                       # wrong or missing key: never crash, never show garbage
    if skipped:
        print(f"WARNING: {skipped} history record(s) could not be decrypted (is DATA_KEY the right key?).")
    return out


def delete_user(username: str) -> dict:
    """Permanently removes the account and every saved record. Returns how many of each."""
    user = username.lower().strip()
    with _conn() as c:
        cur = c.cursor()
        cur.execute(_sql("DELETE FROM history WHERE username = ?"), (user,))
        records = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0
        cur.execute(_sql("DELETE FROM users WHERE username = ?"), (user,))
        accounts = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0
    return {"history": records, "account": accounts}


# Create the tables as soon as the server starts
init_db()
