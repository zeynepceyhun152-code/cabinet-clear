"""
patch_app.py - adds the security changes to backend/app.py. Safe to run twice. Changes nothing unless every
expected piece of app.py is found (it prints what is missing instead). Undo with: git checkout backend/app.py
"""
import sys

NEW_BLOCK = '''# --- AUTHENTICATION ENDPOINTS ---
@app.post("/auth/register")
async def register_endpoint(payload: dict):
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()
    if not username or not password:
        return JSONResponse(status_code=400, content={"success": False, "error": "Username and password required"})
    if not valid_username(username):
        return JSONResponse(status_code=400, content={"success": False, "error": USERNAME_RULE})
    if not valid_password(password):
        return JSONResponse(status_code=400, content={"success": False, "error": PASSWORD_RULE})
    if register_user(username, password):
        return {"success": True, "message": "User account built successfully"}
    return JSONResponse(status_code=400, content={"success": False, "error": "Username already exists"})

@app.post("/auth/login")
async def login_endpoint(payload: dict):
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()
    if authenticate_user(username, password):
        return {"success": True, "username": username, "token": issue_token(username)}
    return JSONResponse(status_code=401, content={"success": False, "error": "Invalid username or credentials"})

# --- TIMELINE HISTORY ENDPOINTS (a valid sign-in token is required, and only for your own history) ---
@app.post("/history/save")
async def save_history_endpoint(request: Request, payload: dict):
    user, problem = user_from_request(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": problem})
    diagnosis = payload.get("diagnosis", "Unknown Diagnosis")
    letter = payload.get("letter_data", {})
    cabinet = payload.get("cabinet_data", {})
    save_history_record(user, diagnosis, letter, cabinet)
    return {"success": True}

@app.get("/history/get/{username}")
async def get_history_endpoint(username: str, request: Request):
    user, problem = user_from_request(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": problem})
    if username.strip().lower() != user:
        return JSONResponse(status_code=403, content={"success": False, "error": MSG_OWN_ONLY})
    return {"success": True, "data": fetch_user_history(user)}

'''
IMPORTS = '''from starlette.requests import Request
from security import (ALLOWED_ORIGINS, ORIGIN_REGEX, issue_token, user_from_request, valid_username, valid_password,
                      USERNAME_RULE, PASSWORD_RULE, MSG_OWN_ONLY)
'''
HOOK = '''
# security: sign-in tokens, speed limits, daily AI cap and size limits (see security.py)
from security import install as _install_security
_install_security(app)
'''
START, END = "# --- AUTHENTICATION ENDPOINTS ---", "# --- EXISTING EXTRACTION AND EVALUATION ENDPOINTS ---"


def patch(text):
    """Returns (new_text, problems). If problems is not empty, new_text is the unchanged input."""
    if "from security import" in text:
        return text, []
    problems = []
    if "from dotenv import load_dotenv\n" not in text:
        problems.append("could not find the line 'from dotenv import load_dotenv'")
    if 'allow_origins=["*"],' not in text:
        problems.append('could not find allow_origins=["*"],')
    if START not in text or END not in text or text.index(START) > text.index(END):
        problems.append("could not find the sign-in and history section")
    if problems:
        return text, problems
    out = text.replace("from dotenv import load_dotenv\n", "from dotenv import load_dotenv\n" + IMPORTS, 1)
    out = out.replace('allow_origins=["*"],', 'allow_origins=ALLOWED_ORIGINS,\n    allow_origin_regex=ORIGIN_REGEX,', 1)
    a, b = out.index(START), out.index(END)
    out = out[:a] + NEW_BLOCK + out[b:]
    return out.rstrip("\n") + "\n" + HOOK, []


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "backend/app.py"
    src = open(path, encoding="utf-8").read()
    new, problems = patch(src)
    if problems:
        print("NOT changed. Problems:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    if new == src:
        print("backend/app.py already has the security changes")
    else:
        open(path, "w", encoding="utf-8").write(new)
        print("backend/app.py updated")
