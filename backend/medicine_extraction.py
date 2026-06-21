import os
import json
import base64
from datetime import datetime
from dotenv import load_dotenv
import anthropic

load_dotenv()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = "claude-sonnet-4-6"

MEDICINE_PROMPT = """You are helping a caregiver identify medicine information from a photo or text of a medicine label or box.

Extract the following as a JSON object with EXACTLY this structure:

{
  "drug_name": "brand or generic name of the medication",
  "active_ingredient": "active ingredient and strength if visible",
  "dosage_strength": "e.g. 500mg, 10mg/5ml",
  "expiration_date": "exactly as printed, e.g. EXP 08/2024 or Best By Jan 2025",
  "expiration_parsed": "YYYY-MM format if parseable, otherwise null",
  "is_expired": true or false or null,
  "extraction_confidence": "high | medium | low",
  "confidence_notes": "explain if anything was hard to read, unclear, or missing"
}

Today's date is """ + datetime.now().strftime("%Y-%m-%d") + """.
Use today's date to determine if the medication is expired.
Output ONLY the JSON object, no markdown, no extra text.
"""

def _parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())

def extract_medicine_from_image(file_path: str, mime_type: str = "image/jpeg") -> dict:
    with open(file_path, "rb") as f:
        data = f.read()
    b64_data = base64.b64encode(data).decode("utf-8")

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": b64_data
                    }
                },
                {"type": "text", "text": MEDICINE_PROMPT}
            ]
        }]
    )
    return _parse_json(response.content[0].text)

def extract_medicine_from_text(label_text: str) -> dict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": f"{MEDICINE_PROMPT}\n\n{label_text}"}]
    )
    return _parse_json(response.content[0].text)