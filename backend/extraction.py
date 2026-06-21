import os
import json
import base64
from dotenv import load_dotenv
import anthropic

load_dotenv()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = "claude-sonnet-4-6"

EXTRACTION_PROMPT = """You are helping a parent or caregiver understand a hospital discharge letter.

Read the provided document and extract the following information as a JSON object with EXACTLY this structure:

{
  "diagnosis_summary": "1-2 sentence plain-language explanation of what happened, written for someone with no medical background",
  "medications": [
    {"name": "...", "dosage": "...", "frequency": "...", "duration": "...", "purpose": "plain-language: what this medication is for"}
  ],
  "follow_up_appointments": [
    {"type": "...", "timeframe": "...", "reason": "..."}
  ],
  "warning_signs": [
    "plain-language description of a symptom/sign that means go to ER or call doctor immediately"
  ],
  "activity_restrictions": [
    "plain-language restriction, e.g. no swimming for 2 weeks"
  ],
  "extraction_confidence": "high | medium | low",
  "confidence_notes": "if medium or low, briefly explain what was unclear or hard to read"
}

Rules:
- Only include information that is actually present in the document. Do not invent medications, dates, or instructions.
- If any part of the document is unclear, illegible, or ambiguous, set extraction_confidence accordingly and explain in confidence_notes.
- Output ONLY the JSON object, no other text, no markdown code fences.
"""

def _parse_json_response(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())

def extract_from_text(letter_text: str) -> dict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": f"{EXTRACTION_PROMPT}\n\n{letter_text}"}]
    )
    return _parse_json_response(response.content[0].text)

def extract_from_file(file_path: str, mime_type: str) -> dict:
    """mime_type examples: 'application/pdf', 'image/png', 'image/jpeg'"""
    with open(file_path, "rb") as f:
        data = f.read()
    b64_data = base64.b64encode(data).decode("utf-8")

    content_type = "document" if mime_type == "application/pdf" else "image"

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": content_type,
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": b64_data
                    }
                },
                {"type": "text", "text": EXTRACTION_PROMPT}
            ]
        }]
    )
    return _parse_json_response(response.content[0].text)

URGENCY_PROMPT = """You are a medical triage assistant. Given a list of warning signs from a hospital discharge letter, classify each one by urgency level.

Return ONLY a JSON array with this structure:
[
  {
    "sign": "original warning sign text",
    "urgency": "immediate" | "urgent" | "monitor",
    "timeframe": "e.g. call 911 now / within 2 hours / watch over 24 hours",
    "plain_english": "simple explanation of what to watch for"
  }
]

Urgency levels:
- immediate: life-threatening, call 911 or go to ER right now
- urgent: serious, go to ER or call doctor within 2 hours
- monitor: concerning, watch closely and call doctor if worsens

Output ONLY the JSON array, no markdown, no extra text.
"""

def score_urgency(warning_signs: list) -> list:
    """Score warning signs by urgency level."""
    if not warning_signs:
        return []
    try:
        signs_text = "\n".join(f"- {s}" for s in warning_signs)
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": f"{URGENCY_PROMPT}\n\nWarning signs:\n{signs_text}"}]
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.rsplit("```", 1)[0]
        return json.loads(text.strip())
    except Exception as e:
        return [{"sign": s, "urgency": "monitor", "timeframe": "monitor at home", "plain_english": s} for s in warning_signs]