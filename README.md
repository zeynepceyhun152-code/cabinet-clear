# Cabinet Clear

**Understand your discharge letter. Know exactly what to keep, take, or throw away.**

**Live app: https://cabinetclear.vercel.app** (deployed, so you can use it straight from this link, no account needed). The server runs on free hosting that sleeps when nobody is using it, so the first request after a quiet spell can take up to a minute. Made-up test letters are in `sample_data/`: open a `.txt`, copy the text, and paste it into the app.

> It's 11 p.m. Maya, 9, is finally asleep after an asthma flare-up. Her dad is sitting at the kitchen table with a discharge letter full of dosing instructions in one hand and a drawer of old inhalers and amoxicillin bottles in the other, trying to figure out which ones are safe to use tonight and which ones have been expired since last winter. Cabinet Clear is built for that exact moment.

<p align="center">
  <img src="screenshots/results_screen.png" width="420" alt="Cabinet Clear results screen showing Keep/Dispose/Unclear/Pharmacy buckets">
</p>

---

## Contents

1. [The Problem](#the-problem)
2. [What It Does](#what-it-does)
3. [Why AI, Not Just a Search Engine](#why-ai-not-just-a-search-engine)
4. [Architecture](#architecture)
5. [AI Components](#ai-components)
6. [Responsible AI](#responsible-ai)
7. [The CNN, In Depth](#the-cnn-in-depth)
8. [Tech Stack](#tech-stack)
9. [Project Structure](#project-structure)
10. [Development Timeline](#development-timeline)
11. [Running It On Your Own Computer](#running-it-on-your-own-computer)
12. [AI Usage Disclosure](#ai-usage-disclosure)
13. [Credits](#credits)
14. [Disclaimer](#disclaimer)

---

## The Problem

Every year, families leave the hospital with a discharge letter full of medical jargon and a medicine cabinet full of bottles they're not sure about. People miss doses, take expired medication, or skip follow-ups — not from carelessness, but because the information was never designed for someone exhausted and stressed.

I know this from my own family. When I was diagnosed with prediabetes, my mom, who is a doctor, and I still could not follow what the doctor explained. We were too emotional in that room, and the discharge letter was full of medical words. At home the questions kept coming, and none of them could be asked in the moment. Then I looked at our two medicine cabinets, packed with bottles, and could not tell what was in them or what had expired. So there were two problems: you can't understand your letter, and you can't trust your cabinet. Cabinet Clear solves both, and I use it myself.

---

## What It Does

- **Reads your letter.** Paste it, upload a PDF, or take a photo. You get plain language: the diagnosis, each medicine, follow-ups, and warning signs ranked by urgency.
- **Fits how you feel.** Two optional questions (how overwhelmed you are, how much you understood) give you a short calm explanation, a standard one, or a detailed one. A checker compares every explanation with the letter, and if a dose, medicine or warning sign does not match, the app shows a plain version taken straight from the letter. If you are still confused, it links to 13 trusted reading pages (hospitals, government, professional societies). Simple rules pick the links, not the AI, so there are no made-up links.
- **Checks your photos first.** Before anything is read, a CNN I built checks that each medicine photo is clear enough. It gives the photo a trust score, and a rejected photo comes back with a Grad-CAM image showing where the CNN looked (see [The CNN](#the-cnn-in-depth)). A medicine can have two photos, one for the front label and one for the expiry date, and they are merged into one reading.
- **Sorts your medicines** into Keep, Dispose, Unclear, or Get from Pharmacy. The app works out expiry dates itself, warns about risky combinations, and makes a PDF to bring to your pharmacist.
- **Matches names.** Tylenol and acetaminophen are the same medicine. The app uses a shared list of 311 brand and generic names (including Turkish spellings) and copes with misread letters. It never treats two different medicines, like citalopram and escitalopram, as the same.
- **Shows what changed.** Paste the medicines you took before the hospital. The app compares them with the letter and shows what is new, stopped, or changed, and asks you to check with a pharmacist instead of deciding. This is plain Python rules, not AI.
- **Works on your phone,** installs like an app, and also works in Turkish.
- **Saves your history (optional).** Sign in to keep past letters and cabinet checks. Saved history is encrypted, and you can delete your account and everything in it at any time.

---

## Why AI, Not Just a Search Engine

A general chatbot can explain medical terms. It can't tell you that the ibuprofen bottle in your cabinet matches your discharge prescription but expired eight months ago, or that two of your "keep" medicines can interact. That means combining information from two different messy sources, a letter and a photo, which is exactly what this app does.

---

## Architecture

```
+----------------------+         +------------------------------+
|  Discharge Letter     |         |   Medicine Photo(s)            |
|  (text / PDF / image) |         |   front label + expiry date    |
+-----------+-----------+         +---------------+----------------+
            |                                     |
            v                                     v
    Claude reads the letter             My CNN checks the photo
    -> structured facts                 (clear enough to read?)
    (medicines, follow-ups,                       |
     warning signs)                      clear? --+-- unclear?
            |                              |             |
            |                              v             v
            |                    Claude reads       "Retake photo"
            |                    name, dose,        + Grad-CAM image
            |                    expiry date
            |                              |
            v                              v
    +-------------------------------------------+
    |        Fixed rules (plain Python)           |
    |  - Brand and generic name matching          |
    |  - Fixing misread letters                   |
    |  - Expiry check                             |
    |  - Interaction warnings                     |
    +---------------------+-----------------------+
                          v
          Keep / Dispose / Unclear / Get from Pharmacy
                          |
                          v
                 Plain-language page + PDF
```

Where it runs: the page you open is on **Vercel**, the server (FastAPI) is on **Render**, and accounts and history are stored in a **Neon** PostgreSQL database.

```
Phone / browser (Vercel)  ->  Server (Render)  ->  Claude API · OpenFDA · Database (Neon)
```

---

## AI Components

| Part | What it does | Built with |
|---|---|---|
| **Photo clarity check** | Decides if a medicine photo is clear enough to read, and gives a trust score | My CNN: ResNet18 (PyTorch), trained on 1,748 images |
| **Grad-CAM image** | Shows where the CNN looked | Grad-CAM |
| **Reading and explaining** | Reads letters and labels, ranks warning signs, writes the explanations | Claude API (Anthropic) |
| **Explanation checker** | Compares every explanation with the letter | Python rules |
| **Name matching** | Matches brand and generic names, fixes misread letters | Shared list of 311 names + typo matching (no AI) |
| **Medicine comparison** | Finds what changed between two medicine lists | Python rules (no AI) |
| **Interaction warnings** | Flags risky combinations among kept medicines | A small hand-checked list + OpenFDA label text |
| **Sorting rules** | Makes every Keep / Dispose / Unclear decision | Python rules |
| **Accounts and history** | Stores accounts and saved checks safely | PostgreSQL (Neon), bcrypt, AES-256-GCM encryption |

**Why plain rules make the final decision.** A wrong "Keep" or "Dispose" could hurt someone, and an AI can make things up. So the AI only reads messy documents, and simple rules that I can read and test make every decision.

---

## Responsible AI

**The app never tells anyone to start, stop, or change a medicine.** That stays with a doctor or pharmacist. It only organizes what is already written down and checks facts like expiry dates.

**The biggest risk** is that the AI misreads a drug name, invents a detail, or misjudges a date. Here is what protects against that:
- **Unsure means "Unclear".** Every read comes with a confidence level. A low-confidence read never goes to Keep or Dispose. It goes to "Unclear: ask your pharmacist", the same as a missing answer.
- **Bad photos never reach the AI.** The CNN rejects them first.
- **The original text is always shown** next to the AI's summary, so you can check it.
- **Explanations are checked.** Code verifies that every medicine, dose and number matches the letter, that nothing was invented, that every warning sign is there, and that no unsafe advice (like "stop the medicine") appears.
- **Expiry is worked out by code.** The AI only copies the printed date.
- **Your data is protected.** Signed sign-in tokens, limits on how often the AI can be called, encrypted history, and uploads deleted after processing. My own review found a hole where history could be read by guessing a username. I fixed it and added tests.

**How it was tested** (no API key or internet needed):
- **Medicine comparison:** 35 cases covering 50 medicines, **50 of 50 correct**, against 24 of 50 for plain text matching. I wrote the cases myself.
- **Name matching:** every pair of different medicines in the 311-name list (over 160,000 pairs) was checked, and none are merged. A bug I found, which treated citalopram and escitalopram as the same, was fixed.
- **Explanation checker:** 47 explanations I damaged on purpose (wrong dose, invented medicine, dropped warning sign, unsafe advice). **All 47 were caught.**
- **Security, privacy and storage** (SQLite and PostgreSQL): all tests pass.

---

## The CNN, In Depth

This is the one part of the app that is a neural network I trained myself, not an API call.

### Why it exists

Anyone can send a photo to an AI. But if the photo is blurry, dark, or too far away, the AI can guess, and a guessed drug name or expiry date is dangerous. So before the AI sees a medicine photo, my CNN answers one simple question: **is this photo clear enough to read?**

- **Trust score.** The CNN gives each photo a number between 0 (unclear) and 1 (clear): how confident it is that the photo can be read.
- **Grad-CAM image.** A heat map shows where the CNN looked. If a photo is rejected, you see this map, so you can tell what was wrong (often the expiry date, a small low-contrast stamp) and retake just that shot.

### How I built it

- **Model:** ResNet18, an existing image model already trained on millions of photos (ImageNet). I kept its early layers as they were, and retrained its last block plus a new final layer that outputs the trust score.
- **Training:** 8 rounds, Google Colab with a T4 GPU.
- **Why a classifier and not a segmentation model:** the question is "clear or not" for the whole photo, one label per image, so a classifier is the right tool.

| | |
|---|---|
| **Base images** | 437 photos of medicine tablets and boxes from the Kaggle dataset "Medicine tablet pack image dataset" (see Credits) |
| **Unclear versions** | From each clear photo I made 3 unclear ones: blurred, darkened (poor lighting), and shrunk then enlarged (taken too far away) |
| **Total** | 1,748 images (437 clear + 1,311 unclear) |
| **Training / validation** | 1,398 / 350 |

### Results

```
              precision    recall   f1-score
   unclear        1.00      1.00      1.00
     clear        1.00      1.00      1.00
```

<p align="center">
  <img src="confusionmatrix.png" width="420" alt="Confusion matrix for the clarity classifier showing 270 unclear and 80 clear validation images, zero misclassifications">
</p>

**What this number really means:** a perfect score is too good to fully trust, because the unclear photos were made from the same clear photos the model learned from. It may partly recognize "a blurred copy of something I saw" instead of blur in general. In live tests it did reject blurry photos I took fresh on a phone. It was also trained on one small set of mostly Indian medicine packs, so it still needs testing on more varied photos from other people.

### Checking that it learned the right thing

A model can get the right answer for the wrong reason, like linking a tabletop texture to "clear". Grad-CAM lets me check. In the image below, warm colors (high attention) sit on the printed text of the label, not the background, which is evidence the CNN learned to judge the text.

<p align="center">
  <img src="gradcam.png" width="500" alt="Grad-CAM heatmap overlaid on a medicine box photo, showing the model's attention concentrated on the label text rather than the background">
</p>

---

## Tech Stack

**Backend:** FastAPI · PyTorch · torchvision · pytorch-grad-cam · thefuzz · fpdf2 · bcrypt · cryptography · pg8000
**Frontend:** Vanilla HTML/CSS/JS · installable web app · English and Turkish
**AI:** Claude API (Anthropic) · my ResNet18 CNN
**Storage:** PostgreSQL on Neon (SQLite when run locally)
**Hosting:** Vercel (page) · Render (server) · Neon (database)
**Data:** OpenFDA drug label API · a shared medicine-name list · made-up discharge letters · a public Kaggle dataset of medicine photos (CNN training)

---

## Project Structure

```
cabinet-clear/
├── backend/
│   ├── app.py                  # FastAPI server, all endpoints
│   ├── extraction.py           # Discharge letter extraction + urgency scoring
│   ├── medicine_extraction.py  # Medicine label extraction
│   ├── crossreference.py       # Name matching + sorting rules
│   ├── reconcile.py            # Before/after medicine comparison (no AI)
│   ├── drug_names.py           # Shared brand/generic name list
│   ├── explain.py              # Adaptive explanations + checker
│   ├── resources.py            # Trusted reading links, chosen by rules
│   ├── interaction_checker.py  # Drug interaction detection
│   ├── clarity_checker.py      # CNN + Grad-CAM
│   ├── pdf_generator.py        # PDF summary export
│   ├── security.py             # Tokens, rate limits, daily cap
│   ├── database.py             # Accounts + history (PostgreSQL / SQLite, bcrypt)
│   ├── crypto_store.py         # Encryption of saved history
│   ├── clarity_model.pth       # Trained CNN weights
│   ├── fonts/                  # Font for Turkish letters in PDFs
│   ├── test_*.py               # Automated tests
│   └── requirements.txt        # Python dependencies
├── frontend/
│   ├── index.html              # Full app UI
│   ├── nav.js, custom.css      # Pages, bottom bar, design
│   ├── session.js              # Sign-in and saving history
│   ├── i18n.js, tr.json        # English / Turkish
│   ├── privacy.js              # Privacy note, delete my account
│   ├── manifest.json           # Phone install settings
│   └── sw.js                   # Service worker
├── screenshots/
│   └── results_screen.png      # App screenshot used above
├── confusionmatrix.png         # CNN validation results
├── gradcam.png                 # CNN Grad-CAM example
└── sample_data/                # Made-up test letters (txt/pdf/png × 5 scenarios)
```

---

## Development Timeline

| When | What I did |
|---|---|
| **June 2026** | Started Cabinet Clear at a hackathon and built the original app: reading discharge letters, scanning medicines, the CNN clarity check, the sorting rules, drug interaction warnings, the PDF summary, accounts, and installing it on a phone. |
| **October 2026 (fall break)** | Added the "What changed?" comparison, adaptive explanations with a checker, trusted reading links, the shared 311-name medicine list, and the Turkish/English switch. |
| **October 2026** | Added security and privacy (sign-in tokens, rate limits, encrypted history, delete my account) and a permanent database on Neon. |
| **October 2026** | New design: separate pages for sign-in, history, scanning and your plan, a bottom bar, and a medicine check without a letter. Also trained a package detector (YOLOv8s) as research: 99.5% on its own photos but only 43% on photos from another dataset, so I kept it out of the app. |
| **Late October 2026** | Tested on my phone and fixed what I found (iPhone zoom, Turkish letters in PDFs, history not saving, a bug that treated look-alike drugs as the same). Wrote the automated tests, then froze the code for submission. |

---

## Running It On Your Own Computer

You can also just use the live app above. To run it yourself:

**You need:** Python 3.11 or 3.12 (newer versions can break PyTorch on Windows), and an [Anthropic API key](https://console.anthropic.com). On Windows, install the [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) and restart if PyTorch shows a `DLL initialization failed` error.

**1. Get the code and make a virtual environment**

```bash
git clone https://github.com/zeynepceyhun152-code/cabinet-clear-with-a-better-frontend.git
cd cabinet-clear-with-a-better-frontend/backend
python3.12 -m venv venv
source venv/bin/activate          # Windows: py -3.12 -m venv venv, then .\venv\Scripts\Activate.ps1
```

**2. Install the packages** (takes a few minutes; if a download times out, run it again)

```bash
pip install -r requirements.txt
```

**3. Add your API key.** Create a file called `.env` in `backend/` with one line (it is kept out of the repo, never commit a real key):

```
ANTHROPIC_API_KEY=your_actual_key_here
```

When deployed, the server also reads `AUTH_SECRET` (signs sign-in tokens), `DATABASE_URL` (PostgreSQL) and `DATA_KEY` (turns on history encryption; keep a backup, since a lost key means unrecoverable history).

**4. Start the server** and keep this terminal open:

```bash
uvicorn app:app --reload --port 8080
```

**5. Start the page** in a second terminal:

```bash
cd frontend && python3 -m http.server 8000
```

In `frontend/index.html`, set the line that starts with `const API =` to `http://localhost:8080` (don't commit that change), then open **http://localhost:8000**.

**6. Run the tests (optional).** From `backend/`, after `pip install pypdf`:

```bash
for t in test_*.py; do ANTHROPIC_API_KEY=test python3 $t > /dev/null 2>&1 && echo "PASS  $t" || echo "FAIL  $t"; done
```

No API key or internet is used (`test` is just a placeholder).

---

## AI Usage Disclosure

**Inside the app:** the Claude API (Anthropic) reads discharge letters and medicine labels and writes the plain-language explanations. Code around it checks its work, as described above.

**While building it:** I built the original app myself with all the letter reading, the cabinet check, the CNN, the sorting rules, the PDF export and the accounts. Claude (Anthropic's AI assistant) helped me debug it and enhance the look of frontend.

---

## Credits

- **Anthropic Claude API** for language and image understanding · **OpenFDA** for drug label data.
- **PyTorch**, **torchvision**, **pytorch-grad-cam**, **FastAPI**, **fpdf2**, **thefuzz**, **bcrypt**, **cryptography**, **pg8000**.
- **Neon** (database), **Render** (server) and **Vercel** (web page) for hosting.
- **DejaVu Sans** font (in `backend/fonts`, with its license) for Turkish letters in PDFs.
- CNN training photos: "Medicine tablet pack image dataset" by nitesh31mishra on Kaggle (https://www.kaggle.com/datasets/nitesh31mishra/medicine-tablet-pack-image-dataset). The dataset itself is not in this repository.
- The discharge letters in `sample_data/` are made up, for testing.

---

## Disclaimer

Cabinet Clear organizes information only. It does not provide medical advice and does not replace consultation with a licensed doctor or pharmacist. Always confirm medication decisions with a healthcare professional. Please do not enter real medical information in the public demo.

---

Built by Zeynep Ceyhun, grade 11, Thomas Jefferson School.
