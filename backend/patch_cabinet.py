"""patch_cabinet.py - adds the /scan-cabinet endpoint to backend/app.py. Safe to run twice; changes nothing if anything expected is missing."""
import sys

ENDPOINT = '''

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
'''

def patch(text):
    if '"/scan-cabinet"' in text:
        return text, []
    problems = []
    if "def get_mime(" not in text:
        problems.append("could not find get_mime in app.py")
    if "UploadFile" not in text or "File" not in text:
        problems.append("could not find UploadFile / File imports in app.py")
    if "JSONResponse" not in text:
        problems.append("could not find JSONResponse in app.py")
    if problems:
        return text, problems
    return text.rstrip("\n") + "\n" + ENDPOINT, []

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "backend/app.py"
    src = open(path, encoding="utf-8").read()
    new, problems = patch(src)
    if problems:
        print("NOT changed. Problems:"); [print("  -", p) for p in problems]; sys.exit(1)
    if new == src:
        print("backend/app.py already has /scan-cabinet")
    else:
        open(path, "w", encoding="utf-8").write(new); print("backend/app.py updated with /scan-cabinet")
