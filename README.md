# Cabinet Clear

**Understand your discharge letter. Know exactly what to keep, take, or throw away.**

> It's 11 p.m. Maya, 9, is finally asleep after an asthma flare-up. Her dad is sitting at the kitchen table with a discharge letter full of dosing instructions in one hand and a drawer of old inhalers and amoxicillin bottles in the other, trying to figure out which ones are safe to use tonight and which ones have been expired since last winter. Cabinet Clear is built for that exact moment.

<p align="center">
  <img src="screenshots/results_screen.png" width="420" alt="Cabinet Clear results screen showing Keep/Dispose/Unclear/Pharmacy buckets">
</p>

Built by **[FILL IN: how you want to be credited]**. Cabinet Clear began as a hackathon project in June 2026. Version 2, described here, was built in October 2026 for the Congressional App Challenge.

---

## Try it

| | |
|---|---|
| **Live app** | https://cabinet-clear-for-sunny-hacks.vercel.app/ (no account needed) |
| **Demo video** | **[FILL IN: link]** |
| **Phone** | Open the link in Safari or Chrome, then *Share → Add to Home Screen*. It installs like an app. |
| **Language** | The **Türkçe / English** button is in the top right corner. |
| **Sample letters** | `sample_data/discharge_letters/`: open a `.txt`, copy the text, and paste it into the app. |

> **Heads-up:** the app runs on free hosting that goes to sleep when nobody is using it. The **first** request after a quiet spell can take up to a minute. Open the live link once, wait, and everything after that is fast.

---

## The Problem

Every year, families leave the hospital with a discharge letter full of medical jargon and a medicine cabinet full of bottles they're not sure about. People miss doses, take expired medication, or skip follow-ups — not from carelessness, but because the information was never designed for someone exhausted and stressed.

**Cabinet Clear turns that chaos into a clear, actionable plan in under two minutes.**

---

## What It Does

📄 **Read any discharge letter** — paste text, upload a PDF, or snap a photo. Get a plain-language summary: diagnosis, medications, follow-ups, and warning signs ranked by urgency.

📸 **Scan your medicine cabinet** — photograph each bottle's label and expiration date, **or photograph a whole shelf at once**. For single-label photos, a custom-trained CNN checks photo clarity *before* extraction runs, so blurry shots get caught immediately.

🔍 **Cross-reference everything** — fuzzy brand-to-generic matching (Tylenol → Acetaminophen) backed by real FDA drug data, so the system isn't fooled by OCR typos or brand names.

⚕️ **Catch what a tired parent might miss** — automatic drug interaction warnings between medications you're keeping.

📋 **Walk away with a plan** — every medicine sorted into **Keep**, **Dispose**, **Unclear**, or **Get from Pharmacy**, plus a downloadable PDF summary to bring to your pharmacist.

📱 **Installable as a phone app** — PWA support means it lives on your home screen, no app store required.

🔐 **Save your history** — sign in to keep a record of past discharge letters and cabinet checks. History is encrypted in the database, and you can delete your account and everything saved at any time.

### New in version 2 (October 2026)

| Feature | What it does |
|---|---|
| **What changed?** | Paste your medicines from *before* the hospital stay. The app compares them with the discharge letter and shows what is **new, stopped, changed, or needs a pharmacist's eye**. The comparison is plain Python, not AI, and it produces questions to ask your doctor or pharmacist. It never says which treatment is correct. |
| **Explain it for me** | Rate how stressed you feel and how well you understood the doctor (both optional). The explanation adapts: short and calm, standard, or detailed. A safety checker then compares the explanation against the letter, and if anything doesn't match, the app shows a plain version built directly from the letter's facts. |
| **Read more from trusted sources** | Links to hospital, government and professional-society pages, chosen by keyword rules from the diagnosis. The AI never picks links, so there are no invented URLs. |
| **Whole-shelf scan** | One photo of a shelf: numbered outlines around each package, with what could actually be read on each. Unreadable ones are sent to "Unclear" and never guessed. |
| **Türkçe / English** | The whole app, the AI's explanations and the PDF work in Turkish. |
| **Permanent, protected accounts** | Sign-in tokens, rate limits, a daily cap on AI calls, encrypted history, delete-my-account, and a plain-language privacy note. |

---

## Why AI, Not Just a Search Engine

A general chatbot can explain medical terms. It can't tell you that the Ibuprofen bottle in your cabinet matches your discharge prescription *but expired eight months ago*, or that two of your "keep" medications have a known interaction. That requires cross-referencing structured data from two different unstructured sources in real time — which is exactly what this pipeline is built to do.

---

## Architecture

```
┌─────────────────────┐         ┌──────────────────────┐
│  Discharge Letter    │         │   Medicine Photo      │
│  (text / PDF / image)│         │   (front + expiry)    │
└──────────┬───────────┘         └───────────┬───────────┘
           │                                  │
           ▼                                  ▼
   Claude multimodal extraction      Custom CNN clarity gate
   → structured JSON                 (ResNet18 + Grad-CAM)
   (meds, follow-ups,                         │
    warning signs)                   clear? ──┴── unclear?
           │                            │            │
           │                            ▼            ▼
           │                  Claude label      "Retake photo"
           │                  extraction        prompt
           │                  (name, dosage,
           │                   expiry date)
           │                            │
           ▼                            ▼
   ┌─────────────────────────────────────────┐
   │     Deterministic Cross-Reference Engine  │
   │  • Brand→generic canonicalization (FDA)   │
   │  • Fuzzy OCR-typo correction               │
   │  • Expiration check                        │
   │  • Drug interaction lookup                 │
   └───────────────────┬───────────────────────┘
                        ▼
        Keep / Dispose / Unclear / Get from Pharmacy
                        │
                        ▼
              Plain-language UI + PDF export
```

**Where it runs**

```
 Phone / browser (installable web app)         Vercel   ← the page you open
            │  https
            ▼
 FastAPI server (rate limits, sign-in tokens)  Render
      │                 │                │
      ▼                 ▼                ▼
 Claude API        OpenFDA data     Neon PostgreSQL  ← accounts + encrypted history
```

---

## AI Components

| Component | What it does | Built with |
|---|---|---|
| **Image clarity classifier** | Determines if a medicine photo is sharp enough to trust before extraction runs | Custom-trained ResNet18 (PyTorch), 1,748 images, transfer learning |
| **Explainability layer** | Visualizes *which part* of a label the model is evaluating | Grad-CAM |
| **Letter extraction** | Reads discharge letters in any format, returns structured plain-language summary | Claude API (Anthropic) |
| **Label extraction** | Reads drug name, dosage, and expiration date from photos | Claude API (Anthropic) |
| **Urgency scoring** | Ranks warning signs by how urgently they require action | Claude API + structured prompting |
| **Adaptive explanation** | Rewrites the letter's facts in a style that fits how the reader feels | Claude API + a rule-based faithfulness checker |
| **Whole-shelf scan** | Finds each package in one photo and reads what is printed | Claude API (vision) + code that validates every outline |
| **Brand/generic resolution** | Maps "Tylenol" → "Acetaminophen" even with OCR typos | OpenFDA drug label data + fuzzy string matching |
| **Drug interaction check** | Flags risky combinations among kept medications | Static clinical reference + OpenFDA interaction data |
| **Medication comparison** | Finds what changed between two medicine lists | Custom Python rules (no AI) |
| **Cross-reference engine** | Deterministic rules engine — the safety-critical decision layer | Custom Python logic |

**Why deterministic rules for the final decision layer?** Medical safety decisions shouldn't depend on a model that can hallucinate. The LLM handles language understanding (reading messy documents); a transparent, auditable rules engine handles the actual Keep/Dispose logic. This is intentional, not a limitation.

---

## Responsible AI

**🎯 The AI never decides whether to take, stop, or change a medication.** That stays with a doctor or pharmacist — always. The AI only organizes information that's already written down and checks objective facts like expiration dates.

**⚠️ Known risk — extraction errors and hallucination:** The Claude extraction layer reads unstructured text and images, which means it can misread a drug name, invent a detail that isn't actually on the label, or misjudge an ambiguous expiration date format. This is the single biggest risk in the pipeline, because a wrong "Keep" or "Dispose" classification has real consequences.

**🛡️ Mitigation — confidence-gated routing, not blind trust:**
- Every extraction call is prompted to return a `confidence` rating (high / medium / low) and to flag anything it found unclear, rather than silently guessing.
- **Low-confidence results never reach the Keep or Dispose buckets.** The cross-reference engine routes them straight to "Unclear — ask your pharmacist," regardless of what the AI extracted. A wrong-but-confident-looking answer is treated the same as a missing one.
- The custom CNN clarity gate runs *before* extraction is even attempted on a photo — unclear images are rejected immediately with a Grad-CAM visualization showing exactly what was unreadable, so a bad read never enters the pipeline in the first place.
- The final Keep/Dispose decision itself is made by a **deterministic, auditable Python rules engine** — not the LLM. The LLM's job is limited to reading messy input into structured fields; it does not get the final say on what happens to any medication.
- The original extracted text is always shown alongside the AI's summary so the user can sanity-check it against the source document.

**Added in version 2**
- **Explanations are checked against the letter, not trusted.** Code verifies that every medicine, dose and number in an AI-written explanation matches the letter, that no medicine or number was invented, that every warning sign is present in its original wording, that no follow-up was dropped, and that no unsafe advice (such as "stop the medicine") appears. If any check fails, the person sees a plain version built directly from the extracted facts.
- **The AI is told not to guess how the reader feels** and not to turn vague words like "persistent" into specific counts.
- **Expiry is decided by code.** The AI only transcribes the printed date. The app works out whether it has passed.
- **Names come only from print.** In the whole-shelf scan, a medicine is named only if the name was readable on the package. Anything else becomes "Unknown" and goes to "Unclear." Nothing is guessed from shape or color.
- **The AI-written text is never the last word.** Warning signs are shown beside the letter's own wording, and every screen says to confirm with a doctor or pharmacist.

This is a defense-in-depth approach: no single layer is trusted to be right on its own.

---

## Evaluation and Tests

All of these run without an API key or internet connection (`ANTHROPIC_API_KEY=test python3 test_<name>.py`, see [Running the tests](#running-the-tests)). The caveat column matters, so please read it.

| Component | What was tested | Result | Caveat |
|---|---|---|---|
| Clarity CNN | 350 validation images | 100% precision and recall | Built from augmented copies of the training photos, so this is optimistic. See [The CNN, In Depth](#the-cnn-in-depth). |
| Medication comparison | 35 cases covering 50 medications: brand vs generic, mcg vs mg, "twice daily" vs "BID", salts, extended-release, tapers, shared ingredients | **50/50** correct, against 24/50 for naive exact-text matching | The cases were written by the developer while building. An independent blind set: **[FILL IN: result, or "planned"]**. |
| Explanation safety checker | 47 deliberately damaged explanations (wrong dose, invented medicine, dropped warning sign, unsafe advice…) | **47/47 caught.** The plain fallback passes its own checks in all 15 test cases. | Uses synthetic letters. Results with the real model (fallback rate, reading level): **[FILL IN: run `eval_explain.py`]** |
| Whole-shelf scan | Outline validation, expiry-date parsing (18 date examples), the on-screen behavior | Automated tests pass | Accuracy on real shelf photos has not been measured yet: **[FILL IN]** |
| Security | 50 automated checks: tokens, history access, limits, size caps, browser origin rules, password lock-out | All pass | See [Security and Privacy](#security-and-privacy) |
| Privacy | Encryption, tampering, key rotation, copied records, account deletion, upload clean-up | All pass | |
| Storage | Accounts and history on SQLite and on PostgreSQL, including 6 simultaneous sign-ups for one name | All pass | Tested on PostgreSQL 16 and in production on Neon |
| Turkish | The page's translator and the server's translator agree on 255 texts | Identical | Wording reviewed by: **[FILL IN]** |

---

## The CNN, In Depth

This is the one piece of the pipeline that's a genuinely custom-trained neural network rather than an API call, so it's worth explaining properly.

### The problem it solves

Before any AI tries to *read* a medicine label, something needs to answer a simpler question first: **is this photo even good enough to read?** A blurry, dark, or too-far-away photo of a label can cause downstream extraction to silently misread a drug name or, worse, an expiration date — and a wrong expiration date is exactly the kind of error that has real consequences in this app. So instead of trusting every photo equally, every medicine photo passes through a dedicated clarity classifier first.

### Why this is classification, not segmentation

It's tempting to reach for architectures like U-Net or ResUNet for any "real" computer vision project, but those are built for *segmentation* — outlining a specific region pixel-by-pixel (e.g. tracing a tumor boundary in a scan). That's the wrong tool here. "Is this photo clear or blurry?" is a **binary classification** problem — one label per image, not a pixel map — so the right architecture is a standard CNN classifier, not a segmentation network. Using the wrong architecture on purpose just to look more advanced would have made the model heavier and harder to train for no real benefit, so we used the architecture that actually matches the task.

### Model architecture

- **Base model:** ResNet18, pretrained on ImageNet
- **Transfer learning approach:** the early convolutional layers are frozen (they already know general image features like edges and textures), and only the final block (`layer4`) plus a new classification head are fine-tuned on our data
- **Classification head:** a single linear layer down to 1 output, passed through a sigmoid, giving a probability between 0 (unclear) and 1 (clear)
- **Loss function:** Binary Cross-Entropy (BCELoss) — the correct loss for a binary classification problem with a sigmoid output
- **Optimizer:** Adam, learning rate 1e-4, applied only to the unfrozen parameters

### Dataset and training

| | |
|---|---|
| **Base images** | 437 medicine packaging photos (public dataset: **[FILL IN: name, source and license]**) |
| **Augmentation** | Each base "clear" image was used to generate 3 "unclear" variants: Gaussian blur, brightness reduction (simulating poor lighting), and downscale-then-upscale (simulating a photo taken too far away) |
| **Total dataset** | 1,748 images (437 clear + 1,311 unclear) |
| **Train / validation split** | 1,398 / 350 (80/20) |
| **Epochs** | 8 |
| **Hardware** | Google Colab Pro, T4 GPU |

### Results

```
              precision    recall   f1-score
   unclear        1.00      1.00      1.00
     clear        1.00      1.00      1.00
```

<p align="center">
  <img src="confusionmatrix.png" width="420" alt="Confusion matrix for the clarity classifier showing 270 unclear and 80 clear validation images, zero misclassifications">
</p>

**Being honest about what this number means:** a perfect validation score on a dataset built from augmented copies of the same source images is expected to look better than it would on fully independent real-world photos, because the model can partly learn "this looks like a blurred/darkened variant of something I trained on" rather than purely general blur/clarity detection. We're stating this directly rather than presenting the headline number without context. In live testing during development, the classifier did correctly reject genuinely blurry photos taken fresh on a phone camera — but a larger, independently-collected test set is the natural next step to validate this more rigorously.

### Explainability with Grad-CAM

Training a model that gets the right answer isn't the same as knowing *why* it got the right answer. We used Grad-CAM (Gradient-weighted Class Activation Mapping) to visualize which pixels the model is actually paying attention to when it makes a prediction.

<p align="center">
  <img src="gradcam.png" width="500" alt="Grad-CAM heatmap overlaid on a medicine box photo, showing the model's attention concentrated on the label text rather than the background">
</p>

This matters because a model can sometimes get the right answer for the wrong reason — for example, learning to associate "tabletop texture" or "lighting conditions" with the clear/unclear label instead of actually evaluating the legibility of the text. The Grad-CAM output above shows the model's attention (warm colors = high attention) concentrated directly on the printed text areas of the label, not the background or the pill blister pack — which is the evidence that it learned the right thing.

### Where the CNN sits in the pipeline

The clarity check runs as a **gate**, before any text extraction is attempted:

```
medicine photo → CNN clarity check
                        │
              clear?  ──┴──  unclear?
                │              │
                ▼              ▼
        proceed to AI    reject + show
        label extraction  Grad-CAM overlay,
                          ask for retake
```

If a photo is rejected, the user sees the Grad-CAM heatmap directly in the app, so they can see *which part* of the image was the problem (usually the expiration date area, since it's often a separate, lower-contrast stamp on the packaging) and retake just that shot.

---

## Whole-Shelf Scan

Take one photo of a shelf or cabinet. The app draws a numbered outline around each package it finds and reads what is printed on each one. Tick the ones you want and add them to the cabinet check.

- Outlines come from Claude's image reading. The code then **validates every outline** (inside the photo, large enough, near-duplicates removed, at most 30), straightens phone-photo rotation, and shrinks large photos.
- Each package gets a confidence level. Unreadable or low-confidence packages are marked **"Close-up needed"**, are not ticked by default, and go to **Unclear** if added.
- The clarity CNN is used for single-label photos. A shelf photo is judged package by package instead, using the confidence level and the readability of each name.
- The same cross-reference as the one-at-a-time scanner applies afterwards, so the result flows into Keep / Dispose / Unclear / Get from Pharmacy unchanged.
- The code is organized so that the box-finding step can be replaced by our own trained detector without changing the screen or the checks (see the research notes below).

---

## Languages

The app works in English and Turkish, which makes it usable for Turkish-speaking families.

- A dictionary of fixed texts (`frontend/tr.json`) is shared by the page and the server, so both translate the same way. Texts that contain names or numbers use patterns.
- The AI is told which language to write in. Medicine names, doses, numbers and dates are never translated.
- Turkish letters work as input. The PDF uses a Unicode font so letters like ş, ğ, İ and ı print correctly.
- Limits: the FDA text inside some interaction warnings, and the linked reading pages, stay in English (the links are marked "İngilizce").
- Turkish wording review: **[FILL IN]**

---

## Security and Privacy

**Access**
- Signing in returns a signed token (HMAC-SHA256, 7 days). Saved history can only be read, saved, or deleted with a valid token, and only for the account in the token.
- Passwords are stored as bcrypt hashes. After 10 wrong passwords from one visitor, sign-in and account deletion lock for 15 minutes.
- Per-visitor limits on AI calls, a daily cap on AI calls for the whole service (default 600), size limits on uploads (10 MB) and pasted letters (30,000 characters), and a browser-origin allow-list.
- An early version let anyone read a user's saved history by guessing the username. We found this in our own review, fixed it, and added tests that prove it can't happen.

**Privacy**
- Saved history is encrypted before it is stored (AES-256-GCM). Each value is locked to its owner and field, and the key lives only in a server setting, never in the database.
- People can delete their account and every saved record from inside the app.
- Letters and photos are **not stored**. They are processed and deleted, including when reading them fails (an early version left the file behind on failure, and that was fixed).
- Without signing in, nothing about the user is saved.
- **What is sent to the AI:** to read letters and photos, the app sends them to Anthropic's AI service. Anthropic states that it does not train its models on content sent through its API by default. Read its current policy: https://www.anthropic.com/legal/privacy
- **Limits, stated plainly:** the server needs the key to show history back to its owner, so whoever operates the server could also read it. The encryption protects stored data (for example, a leaked database), not against the key holder. The app is an educational tool and is not claimed to meet any health-privacy regulation.

---

## Research Notes: A Package Detector That Did Not Generalize

For a later phase, we trained our own detector (YOLOv8s, one class: "medicine package") to find packages without an API call. We report this result because it taught us something.

- Trained on a public medicine-box dataset (2,934 train / 650 validation photos). On its own validation photos, the training log reports about 99.5% mAP@50, which looks excellent.
- Tested on **84 photos from a different public dataset** that it never saw, it found only **43%** of packages (95% range 33% to 54%), with precision of 51%.
- Lesson: a score on photos from the same source can be badly optimistic. We are checking whether the gap comes from the model or from differences in how the two datasets label things (boxes on a table versus pill bottles on a desk), and we plan to collect our own labeled photos of US packaging and crowded shelves as an independent test.
- This detector is **not used in the live app.** The whole-shelf scan uses Claude's image reading instead, with the validation described above.

Datasets (via Roboflow Universe): `yolo-m1fwc / medicine-box-o3he4` (CC BY 4.0), used for training, and `texas-am-university-bdqxe / medicine-box-a33sn` (MIT), used only for testing. Versions used: **[FILL IN: from the download lines in your Colab notebook]**.

---

## Tech Stack

**Backend:** FastAPI · PyTorch · torchvision · pytorch-grad-cam · thefuzz · fpdf2 · bcrypt · cryptography · pg8000
**Frontend:** Vanilla HTML/CSS/JS · installable web app (PWA) · English and Turkish
**Storage:** PostgreSQL on Neon (SQLite for local use)
**Hosting:** Vercel (page) · Render (server) · Neon (database)
**AI:** Claude API (Anthropic) · custom ResNet18 CNN
**Data:** OpenFDA drug label API · synthetic discharge letters · self-collected training images

---

## API Endpoints

| Method | Path | What it does |
|---|---|---|
| POST | `/extract-letter` | Reads a discharge letter (text, PDF or image) |
| POST | `/score-urgency` | Ranks warning signs by urgency |
| POST | `/check-clarity` | CNN photo-clarity check with Grad-CAM |
| POST | `/scan-medicine` | Reads one medicine label |
| POST | `/scan-cabinet` | Finds and reads every package in one shelf photo |
| POST | `/analyze` | Cross-references the letter and the cabinet |
| POST | `/check-interactions` | Drug interaction warnings |
| POST | `/parse-med-list` | Turns a typed medicine list into structured data |
| POST | `/reconcile` | Compares the earlier list with the discharge list |
| POST | `/explain` | Adaptive explanation, checked against the letter |
| POST | `/generate-pdf` | PDF summary (English or Turkish) |
| POST | `/auth/register`, `/auth/login` | Accounts and sign-in tokens |
| POST / GET | `/history/save`, `/history/get/{username}` | Saved history (token required, own account only) |
| DELETE | `/account` | Deletes the account and all saved history (token and password required) |
| GET | `/health` | Where data is stored, and whether it is encrypted |

---

## Project Structure

```
cabinet-clear/
├── backend/
│   ├── app.py                  # FastAPI server, all endpoints
│   ├── extraction.py           # Discharge letter extraction + urgency scoring
│   ├── medicine_extraction.py  # Medicine label extraction
│   ├── cabinet_scan.py         # Whole-shelf scan: outline checks, expiry parsing
│   ├── crossreference.py       # Fuzzy matching + cross-reference engine
│   ├── reconcile.py            # Before/after medication comparison (no AI)
│   ├── explain.py              # Adaptive explanations + faithfulness checker
│   ├── resources.py            # Trusted reading links, chosen by rules
│   ├── interaction_checker.py  # Drug interaction detection
│   ├── clarity_checker.py      # CNN inference + Grad-CAM
│   ├── pdf_generator.py        # PDF summary export (English and Turkish)
│   ├── security.py             # Tokens, rate limits, daily cap, size limits
│   ├── database.py             # Accounts + history (PostgreSQL or SQLite, bcrypt)
│   ├── crypto_store.py         # Encryption of saved history
│   ├── lang_ctx.py             # Which language a request wants
│   ├── lang_middleware.py      # Reads the language header
│   ├── translate_server.py     # Turkish text for server-written messages
│   ├── clarity_model.pth       # Trained CNN weights
│   ├── drug_db.json            # FDA brand→generic mappings
│   ├── test_*.py               # Automated tests
│   ├── eval_explain.py         # Measures the real model's fallback rate and reading level
│   ├── check_links.py          # Checks the trusted reading links still open
│   └── requirements.txt        # Python dependencies
├── frontend/
│   ├── index.html              # Full app UI (sign in, letter, cabinet, plan)
│   ├── i18n.js, tr.json        # English / Turkish switch and its dictionary
│   ├── session.js              # Keeps the sign-in token in memory
│   ├── cabinet_scan.js         # Whole-shelf scan screen
│   ├── privacy.js              # Privacy note and delete-my-account
│   ├── manifest.json, sw.js    # PWA config and service worker
│   └── icon-*.png              # App icons
└── sample_data/
    └── discharge_letters/      # Synthetic test letters (txt/pdf/png × 5 scenarios)
```

---

## Running It On Your Own Computer

### 1. Prerequisites

- **Python 3.11 or 3.12** (recommended). PyTorch's Windows builds can fail to load on the newest Python releases; if you see a `DLL initialization failed` error, install 3.12 from [python.org](https://www.python.org/downloads/) (multiple versions can coexist).
- **Windows only — Microsoft Visual C++ Redistributable** ([aka.ms/vs/17/release/vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe)), then restart the computer.
- **An Anthropic (Claude) API key**: [console.anthropic.com](https://console.anthropic.com).
- A stable internet connection for the first install (PyTorch alone is roughly 120 MB).

### 2. Clone and set up a virtual environment

```bash
git clone https://github.com/<your-username>/cabinet-clear.git
cd cabinet-clear/backend
```

**Mac/Linux:**
```bash
python3.12 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
```

Your prompt should now start with `(venv)`. Reactivate it every time you open a new terminal.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

If a download times out, run the same command again. It resumes where it left off.

### 4. Add your API key

Create a file called `.env` inside `backend/` with one line:

```
ANTHROPIC_API_KEY=your_actual_key_here
```

It is excluded from the repo by `.gitignore`. Never commit a real key.

### 5. Start the server

```bash
uvicorn app:app --reload --port 8080
```

You should see `Uvicorn running on http://127.0.0.1:8080`. Keep this terminal open. Open http://localhost:8080/health to check it: it should answer `"storage":"sqlite"` (your data stays in a local file).

### 6. Start the page (a second terminal)

```bash
cd cabinet-clear/frontend
python3 -m http.server 8000
```

Then in `frontend/index.html`, change the line that starts with `const API =` to `http://localhost:8080` (don't commit that change), and open **http://localhost:8000**.

> **Use port 8000 for the page.** The server only accepts browser requests from your own pages (localhost 8000 and 8080, and the deployed addresses). The older `/app` page served by the backend itself does not include the newer scripts (language switch, sign-in token, shelf scan, privacy), so use the page above, or the live link.

### Running the tests

From the `backend/` folder, with the virtual environment active:

```bash
for t in test_*.py; do ANTHROPIC_API_KEY=test python3 $t > /dev/null 2>&1 && echo "PASS  $t" || echo "FAIL  $t"; done
```

Every line should say `PASS`. No API key or internet connection is used (the value `test` is a placeholder). Run a file on its own to see its details: for example, `python3 test_reconcile.py` prints how the comparison engine scores against a naive baseline. On Windows, run the files one at a time (`python test_security.py`) after setting `$env:ANTHROPIC_API_KEY="test"`. To also test PostgreSQL, set `TEST_DATABASE_URL` to a database you don't mind filling with test data.

---

## Configuration

Set these as environment variables (in `.env` locally, in the host's settings when deployed). Only the first is required.

| Name | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | **Required.** Lets the server call Claude. |
| `AUTH_SECRET` | Signs sign-in tokens. Without it, everyone is signed out when the server restarts. |
| `DATABASE_URL` | A PostgreSQL address. With it, accounts and history are permanent. Without it, a local file is used (temporary on free hosting). |
| `DATA_KEY` | A 32-byte key (base64) that turns on encryption of saved history. Keep a backup: lost key means unrecoverable history. Several keys separated by commas allow key rotation. |
| `ALLOWED_ORIGINS` | Optional. Comma-separated list of pages allowed to call the server. |
| `DAILY_AI_CALLS`, `AI_LIMIT_PER_10MIN` | Optional. Spending and speed limits. |

---

## AI Usage Disclosure

AI is used in two ways, and both are disclosed here as the challenge requires.

**1. Inside the app.** A Claude model (Anthropic API) reads discharge letters, medicine labels and shelf photos, and writes the plain-language explanations. Code around it checks the AI's work, as described under [Responsible AI](#responsible-ai).

**2. While building the app.** Claude (Anthropic's AI assistant) was used during development. It wrote a large part of the code for version 2, working from requirements, decisions and bug reports given by the developer: the medication comparison, adaptive explanations, the Turkish/English switch, the security and privacy work, the database support, the whole-shelf scan, and the automated tests. The developer chose the problem and the features, set the safety rules, tested every feature on a real phone, found and reported problems, made the design decisions, deployed the app, and reviewed the Turkish text. **[FILL IN: who built the original June version, and whether any AI tools helped with it.]**

**Not AI-generated:** **[FILL IN: for example, the clarity model, which you trained on ___ using ___ photos, and the original June version, which you built by ___]**

---

## Limitations and Known Issues

- **Not medical advice.** The app organizes information that is already written down. It does not diagnose or recommend treatment.
- **The AI can misread** a letter or label. That is why uncertain results go to "Unclear," and why the original text is always shown beside the summary.
- **The clarity CNN's perfect score is optimistic** (see its section). It needs a larger independent test set.
- **The whole-shelf scan** has been tested in code, but its accuracy on real shelf photos has not yet been measured. Small print on a shelf photo is often unreadable, so expect many packages to ask for a close-up.
- **Free hosting:** the first request after a quiet period can take up to a minute.
- **Encryption protects stored data, not against whoever holds the key.**
- **Turkish:** some linked pages and FDA text remain in English.
- **Test accounts only:** please don't enter real medical information in the public demo.

---

## Credits and Data Sources

- **Anthropic Claude API** for language and image understanding.
- **OpenFDA** drug label data for brand-to-generic mapping and interaction text.
- **PyTorch**, **torchvision**, **pytorch-grad-cam**, **FastAPI**, **fpdf2**, **thefuzz**, **bcrypt**, **cryptography**.
- **DejaVu Sans** font (shipped with matplotlib) for Turkish PDF text.
- **Roboflow Universe** datasets listed in the research notes (credits above).
- Clarity-model training photos: **[FILL IN: source and license]**.
- Discharge letters in `sample_data/` are synthetic and were written for testing.

---

## Disclaimer

Cabinet Clear organizes information only. It does not provide medical advice and does not replace consultation with a licensed doctor or pharmacist. Always confirm medication decisions with a healthcare professional.
