import os
import json
import tempfile
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from dotenv import load_dotenv

from extraction import extract_from_text, extract_from_file
from medicine_extraction import extract_medicine_from_image, extract_medicine_from_text
from crossreference import cross_reference
# Import our relational SQLite gateway functions
from database import register_user, authenticate_user, save_history_record, fetch_user_history

load_dotenv()

app = FastAPI(title="Cabinet Clear API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    username = payload.get("username", "").strip()
    password = payload.get("password", "").strip()
    if not username or not password:
        return JSONResponse(status_code=400, content={"success": False, "error": "Username and password required"})
    if register_user(username, password):
        return {"success": True, "message": "User account built successfully"}
    return JSONResponse(status_code=400, content={"success": False, "error": "Username already exists"})

@app.post("/auth/login")
async def login_endpoint(payload: dict):
    username = payload.get("username", "").strip()
    password = payload.get("password", "").strip()
    if authenticate_user(username, password):
        return {"success": True, "username": username}
    return JSONResponse(status_code=401, content={"success": False, "error": "Invalid username or credentials"})

# --- TIMELINE HISTORY ENDPOINTS ---
@app.post("/history/save")
async def save_history_endpoint(payload: dict):
    username = payload.get("username", "")
    diagnosis = payload.get("diagnosis", "Unknown Diagnosis")
    letter = payload.get("letter_data", {})
    cabinet = payload.get("cabinet_data", {})
    if not username:
        return JSONResponse(status_code=400, content={"success": False, "error": "User session parameter missing"})
    save_history_record(username, diagnosis, letter, cabinet)
    return {"success": True}

@app.get("/history/get/{username}")
async def get_history_endpoint(username: str):
    records = fetch_user_history(username)
    return {"success": True, "data": records}

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
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.split('.')[-1]}") as tmp:
                tmp.write(contents)
                tmp_path = tmp.name
            result = extract_from_file(tmp_path, mime)
            os.unlink(tmp_path)
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
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.split('.')[-1]}") as tmp:
                tmp.write(contents)
                tmp_path = tmp.name
            result = extract_medicine_from_image(tmp_path, mime)
            os.unlink(tmp_path)
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
