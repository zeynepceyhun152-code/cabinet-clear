"""patch_db.py - small changes to backend/app.py for the new database. Safe to run twice; changes nothing if a piece is missing."""
import sys

REPLACEMENTS = [
    ("    if register_user(username, password):", "    if await run_in_threadpool(register_user, username, password):"),
    ("    if authenticate_user(username, password):", "    if await run_in_threadpool(authenticate_user, username, password):"),
    ("    save_history_record(user, diagnosis, letter, cabinet)", "    await run_in_threadpool(save_history_record, user, diagnosis, letter, cabinet)"),
    ('    return {"success": True, "data": fetch_user_history(user)}', '    return {"success": True, "data": await run_in_threadpool(fetch_user_history, user)}'),
]
IMPORT_AFTER = "from starlette.requests import Request\n"
IMPORT_NEW = "from starlette.concurrency import run_in_threadpool\n"
HEALTH = '''

# --- where is your data stored? (open /health to check) ---
@app.get("/health")
async def health_endpoint():
    import database
    kind = database.storage_kind()
    return {"status": "ok", "storage": kind, "permanent": kind == "postgres"}
'''


def patch(text):
    if "run_in_threadpool" in text and '"/health"' in text:
        return text, []
    problems = []
    if IMPORT_AFTER not in text:
        problems.append("could not find 'from starlette.requests import Request' (run the security installer first)")
    for old, _ in REPLACEMENTS:
        if old not in text and "run_in_threadpool" not in text:
            problems.append(f"could not find: {old.strip()}")
    if problems:
        return text, problems
    out = text
    if "run_in_threadpool" not in out:
        out = out.replace(IMPORT_AFTER, IMPORT_AFTER + IMPORT_NEW, 1)
        for old, new in REPLACEMENTS:
            out = out.replace(old, new, 1)
    if '"/health"' not in out:
        out = out.rstrip("\n") + "\n" + HEALTH
    return out, []


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "backend/app.py"
    src = open(path, encoding="utf-8").read()
    new, problems = patch(src)
    if problems:
        print("NOT changed. Problems:"); [print("  -", p) for p in problems]; sys.exit(1)
    if new == src:
        print("backend/app.py already has the database changes")
    else:
        open(path, "w", encoding="utf-8").write(new); print("backend/app.py updated for the new database")
