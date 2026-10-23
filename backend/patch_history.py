"""patch_history.py - saving the same letter again (letter read, changes compared, cabinet checked) UPDATES one history
entry instead of adding a new one each time. Safe to run twice. Undo with: git checkout backend/database.py"""
import sys

NEW_FUNC = '''SAME_CHECK_HOURS = 6


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


'''


def patch(text):
    if "_fingerprint" in text:
        return text, []
    if "def save_history_record" not in text or "def fetch_user_history" not in text or "from datetime import datetime\n" not in text:
        return text, ["could not find save_history_record in database.py (run the privacy installer first)"]
    a, b = text.index("def save_history_record"), text.index("def fetch_user_history")
    out = text[:a] + NEW_FUNC + text[b:]
    return out.replace("from datetime import datetime\n", "from datetime import datetime, timedelta\n", 1), []


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "backend/database.py"
    src = open(path, encoding="utf-8").read()
    new, problems = patch(src)
    if problems:
        print("NOT changed. Problems:"); [print("  -", p) for p in problems]; sys.exit(1)
    if new == src:
        print("backend/database.py already merges saves of the same letter")
    else:
        open(path, "w", encoding="utf-8").write(new); print("backend/database.py updated")
