"""patch_privacy.py - privacy changes to backend/app.py. Safe to run twice; changes nothing if a piece is missing.
Undo with: git checkout backend/app.py"""
import sys

IMPORT_DB = ("from database import register_user, authenticate_user, save_history_record, fetch_user_history",
             "from database import register_user, authenticate_user, save_history_record, fetch_user_history, delete_user")
IMPORT_SEC = ("USERNAME_RULE, PASSWORD_RULE, MSG_OWN_ONLY)", "USERNAME_RULE, PASSWORD_RULE, MSG_OWN_ONLY, MSG_EXPIRED)")
SAVE = ('''    await run_in_threadpool(save_history_record, user, diagnosis, letter, cabinet)
    return {"success": True}''', '''    try:
        await run_in_threadpool(save_history_record, user, diagnosis, letter, cabinet)
    except ValueError:      # the account was deleted
        return JSONResponse(status_code=401, content={"success": False, "error": MSG_EXPIRED})
    return {"success": True}''')
HEALTH = ('return {"status": "ok", "storage": kind, "permanent": kind == "postgres"}',
          'return {"status": "ok", "storage": kind, "permanent": kind == "postgres", "encrypted": database.encryption_enabled()}')
LETTER = ('''            result = extract_from_file(tmp_path, mime)
            os.unlink(tmp_path)
''', '''            try:
                result = extract_from_file(tmp_path, mime)
            finally:
                os.unlink(tmp_path)      # always delete the uploaded letter, even if reading it failed
''')
LABEL = ('''            result = extract_medicine_from_image(tmp_path, mime)
            os.unlink(tmp_path)
''', '''            try:
                result = extract_medicine_from_image(tmp_path, mime)
            finally:
                os.unlink(tmp_path)      # always delete the uploaded photo, even if reading it failed
''')
SUFFIX = ("suffix=f\".{file.filename.split('.')[-1]}\"", "suffix=_safe_suffix(file.filename)")
EXTRA = '''

def _safe_suffix(filename):
    """A file name from a visitor is never trusted: only a few image and PDF endings are kept."""
    ext = (filename or "").rsplit(".", 1)[-1].lower()
    return "." + ext if ext in {"jpg", "jpeg", "png", "webp", "pdf"} else ".bin"


# --- DELETE MY ACCOUNT: needs a sign-in token AND the password; removes the account and every saved record ---
@app.delete("/account")
async def delete_account_endpoint(request: Request, payload: dict):
    user, problem = user_from_request(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": problem})
    password = str(payload.get("password", "")).strip()
    if not await run_in_threadpool(authenticate_user, user, password):
        return JSONResponse(status_code=403, content={"success": False, "error": "Incorrect password."})
    result = await run_in_threadpool(delete_user, user)
    return {"success": True, "deleted": result}
'''


def patch(text):
    if "delete_user" in text and '"/account"' in text:
        return text, []
    problems = []
    for name, (old, _) in {"database import": IMPORT_DB, "security import": IMPORT_SEC, "save endpoint": SAVE, "health page": HEALTH,
                           "letter upload": LETTER, "label upload": LABEL}.items():
        if old not in text:
            problems.append(f"could not find the {name} (run the earlier installers first)")
    if text.count(SUFFIX[0]) != 2:
        problems.append("could not find the two upload file-name lines")
    if problems:
        return text, problems
    out = text
    for old, new in (IMPORT_DB, IMPORT_SEC, SAVE, HEALTH, LETTER, LABEL):
        out = out.replace(old, new, 1)
    out = out.replace(SUFFIX[0], SUFFIX[1])
    return out.rstrip("\n") + "\n" + EXTRA, []


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "backend/app.py"
    src = open(path, encoding="utf-8").read()
    new, problems = patch(src)
    if problems:
        print("NOT changed. Problems:"); [print("  -", p) for p in problems]; sys.exit(1)
    if new == src:
        print("backend/app.py already has the privacy changes")
    else:
        open(path, "w", encoding="utf-8").write(new); print("backend/app.py updated with the privacy changes")
