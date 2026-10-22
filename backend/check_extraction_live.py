import os
SAMPLES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sample_data")
import json
from extraction import extract_from_text, extract_from_file

# Test 1: plain text
with open(os.path.join(SAMPLES, "1_pediatric_asthma.txt")) as f:
    text = f.read()

result = extract_from_text(text)
print("=== TEXT (asthma) ===")
print(json.dumps(result, indent=2))

# Test 2: PDF
result_pdf = extract_from_file(
    os.path.join(SAMPLES, "2_post_appendectomy.pdf"),
    "application/pdf"
)
print("\n=== PDF (appendectomy) ===")
print(json.dumps(result_pdf, indent=2))

# Test 3: image
result_img = extract_from_file(
    os.path.join(SAMPLES, "5_pediatric_fracture.png"),
    "image/png"
)
print("\n=== IMAGE (fracture) ===")
print(json.dumps(result_img, indent=2))
