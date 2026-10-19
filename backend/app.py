import os
import json
import tempfile
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from dotenv import load_dotenv
from starlette.requests import Request
from starlette.concurrency import run_in_threadpool
from security import (ALLOWED_ORIGINS, ORIGIN_REGEX, issue_token, user_from_request, valid_username, valid_password,
                      USERNAME_RULE, PASSWORD_RULE, MSG_OWN_ONLY, MSG_EXPIRED)

from extraction import extract_from_text, extract_from_file
from medicine_extraction import extract_medicine_from_image, extract_medicine_from_text
from crossreference import cross_reference
from reconcile import compare_med_lists
from explain import generate_explanation
# Import our relational SQLite gateway functions
from database import register_user, authenticate_user, save_history_record, fetch_user_history, delete_user

load_dotenv()

app = FastAPI(title="Cabinet Clear API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ORIGIN_REGEX,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend directory for real-time changes
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

@app.get("/app")
def serve_frontend():
    return FileResponse("../frontend/index.html")

@app.get("/manifest.json")
def serve_manifest():
    return FileResponse("../frontend/manifest.json", media_type="application/json")

@app.get("/sw.js")
def serve_sw():
    return FileResponse("../frontend/sw.js", media_type="application/javascript")

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp",
    "application/pdf"
}

def get_mime(filename: str, content_type: str) -> str:
    ext = filename.lower().split(".")[-1]
    mapping = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
               "png": "image/png", "webp": "image/webp",
               "pdf": "application/pdf"}
    return mapping.get(ext, content_type)

@app.get("/")
def root():
    return {"status": "Cabinet Clear API is running"}

# --- AUTHENTICATION ENDPOINTS ---
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
    if await run_in_threadpool(register_user, username, password):
        return {"success": True, "message": "User account built successfully"}
    return JSONResponse(status_code=400, content={"success": False, "error": "Username already exists"})

@app.post("/auth/login")
async def login_endpoint(payload: dict):
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()
    if await run_in_threadpool(authenticate_user, username, password):
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
    try:
        await run_in_threadpool(save_history_record, user, diagnosis, letter, cabinet)
    except ValueError:      # the account was deleted
        return JSONResponse(status_code=401, content={"success": False, "error": MSG_EXPIRED})
    return {"success": True}

@app.get("/history/get/{username}")
async def get_history_endpoint(username: str, request: Request):
    user, problem = user_from_request(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": problem})
    if username.strip().lower() != user:
        return JSONResponse(status_code=403, content={"success": False, "error": MSG_OWN_ONLY})
    return {"success": True, "data": await run_in_threadpool(fetch_user_history, user)}

# --- EXISTING EXTRACTION AND EVALUATION ENDPOINTS ---
@app.post("/extract-letter")
async def extract_letter(file: UploadFile = File(None), text: str = Form(None)):
    try:
        if text and text.strip():
            result = extract_from_text(text.strip())
            return JSONResponse(content={"success": True, "data": result, "input_type": "text"})
        if file:
            mime = get_mime(file.filename, file.content_type)
            if mime not in ALLOWED_MIME_TYPES:
                return JSONResponse(status_code=400, content={"success": False, "error": "Unsupported type."})
            contents = await file.read()
            with tempfile.NamedTemporaryFile(delete=False, suffix=_safe_suffix(file.filename)) as tmp:
                tmp.write(contents)
                tmp_path = tmp.name
            try:
                result = extract_from_file(tmp_path, mime)
            finally:
                os.unlink(tmp_path)      # always delete the uploaded letter, even if reading it failed
            return JSONResponse(content={"success": True, "data": result, "input_type": "file", "mime_type": mime})
        return JSONResponse(status_code=400, content={"success": False, "error": "Please provide either a file or text input."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/scan-medicine")
async def scan_medicine(file: UploadFile = File(None), text: str = Form(None)):
    try:
        if text and text.strip():
            result = extract_medicine_from_text(text.strip())
            return JSONResponse(content={"success": True, "data": result})
        if file:
            mime = get_mime(file.filename, file.content_type)
            if mime not in {"image/jpeg", "image/png", "image/webp"}:
                return JSONResponse(status_code=400, content={"success": False, "error": "Please upload a valid image format."})
            contents = await file.read()
            with tempfile.NamedTemporaryFile(delete=False, suffix=_safe_suffix(file.filename)) as tmp:
                tmp.write(contents)
                tmp_path = tmp.name
            try:
                result = extract_medicine_from_image(tmp_path, mime)
            finally:
                os.unlink(tmp_path)      # always delete the uploaded photo, even if reading it failed
            return JSONResponse(content={"success": True, "data": result})
        return JSONResponse(status_code=400, content={"success": False, "error": "Missing input context data."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/analyze")
async def analyze(payload: dict):
    try:
        discharge_data = payload.get("discharge_data")
        cabinet_meds = payload.get("cabinet_meds", [])
        if not discharge_data:
            return JSONResponse(status_code=400, content={"success": False, "error": "discharge_data is required."})
        result = cross_reference(discharge_data, cabinet_meds)
        return JSONResponse(content={"success": True, "data": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/check-interactions")
async def check_interactions_endpoint(payload: dict):
    try:
        from interaction_checker import check_interactions
        med_names = payload.get("medications", [])
        if not med_names:
            return JSONResponse(content={"success": True, "data": []})
        warnings = check_interactions(med_names)
        return JSONResponse(content={"success": True, "data": warnings})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/score-urgency")
async def score_urgency_endpoint(payload: dict):
    try:
        from extraction import score_urgency
        warning_signs = payload.get("warning_signs", [])
        scored = score_urgency(warning_signs)
        return JSONResponse(content={"success": True, "data": scored})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/generate-pdf")
async def generate_pdf_endpoint(payload: dict):
    try:
        from pdf_generator import generate_summary_pdf
        discharge_data = payload.get("discharge_data", {})
        cross_ref_result = payload.get("cross_ref_result", {})
        interactions = payload.get("interactions", [])
        pdf_bytes = generate_summary_pdf(discharge_data, cross_ref_result, interactions)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=cabinet_clear_summary.pdf"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/check-clarity")
async def check_clarity_endpoint(file: UploadFile = File(...)):
    try:
        from clarity_checker import check_clarity
        contents = await file.read()
        result = check_clarity(contents)
        return JSONResponse(content={"success": True, "data": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/parse-med-list")
async def parse_med_list_endpoint(payload: dict):
    """Turn a typed or pasted medicine list into structured medications."""
    try:
        text = (payload.get("text") or "").strip()
        if not text:
            return JSONResponse(status_code=400, content={"success": False, "error": "Please type or paste your medicines."})
        meds = extract_from_text(text).get("medications", []) or []
        return JSONResponse(content={"success": True, "data": meds})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.post("/reconcile")
async def reconcile_endpoint(payload: dict):
    """Compare the 'before' list with the discharge list. Plain Python, no AI."""
    try:
        result = compare_med_lists(payload.get("before") or [], payload.get("after") or [])
        return JSONResponse(content={"success": True, "data": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/explain")
async def explain_endpoint(payload: dict):
    """Explain the extracted discharge letter in a style that fits how the reader feels."""
    try:
        data = payload.get("discharge_data")
        if not data:
            return JSONResponse(status_code=400, content={"success": False, "error": "discharge_data is required."})
        result = generate_explanation(data, payload.get("stress", 3), payload.get("understanding", 3))
        return JSONResponse(content={"success": True, "data": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})    

# language: the page sends X-Lang (en or tr); the AI prompts and the PDF follow it
from lang_middleware import install as _install_language
_install_language(app)

# security: sign-in tokens, speed limits, daily AI cap and size limits (see security.py)
from security import install as _install_security
_install_security(app)


# --- WHOLE-SHELF SCAN: one photo, every package outlined and read where possible ---
from cabinet_scan import scan_cabinet

@app.post("/scan-cabinet")
async def scan_cabinet_endpoint(file: UploadFile = File(...)):
    try:
        mime = get_mime(file.filename or "", file.content_type or "")
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            return JSONResponse(status_code=400, content={"success": False, "error": "Please upload a valid image format."})
        contents = await file.read()
        return JSONResponse(content={"success": True, "data": scan_cabinet(contents)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


# --- where is your data stored? (open /health to check) ---
@app.get("/health")
async def health_endpoint():
    import database
    kind = database.storage_kind()
    return {"status": "ok", "storage": kind, "permanent": kind == "postgres", "encrypted": database.encryption_enabled()}


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
