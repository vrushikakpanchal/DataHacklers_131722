# UnifiOps — Gen AI Platform for Automated Content Transformation

**SIH Problem Statement 26154 · NTRO · Usha Mittal Institute of Technology**

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [Our Solution](#3-our-solution)
4. [Key Features](#4-key-features)
5. [Repository Structure](#5-repository-structure)
6. [Setup & Installation](#6-setup--installation)
7. [How the System Works](#7-how-the-system-works)
8. [Important Modules](#8-important-modules)
9. [Team Members](#9-team-members)
10. [Troubleshooting](#10-troubleshooting)
11. [Development Notes](#11-development-notes)

---

## 1. Project Overview

UnifiOps is a locally-running AI platform that takes a single source document — a CERT-In advisory, a threat report, a research paper, a fraud warning, or any policy document — and automatically transforms it into six professional, ready-to-publish output formats:

- **Executive Summary** with key findings
- **Formal Advisory PDF** with structured sections
- **Social Media Posts** (LinkedIn and X/Twitter)
- **PowerPoint Slide Deck** (content-aware, multi-slide)
- **SVG Infographic** (data-driven visual)
- **Video Storyboard + MP4** (scene-by-scene motion graphics)

All processing runs on a standard development machine using a local Ollama LLM. No data ever leaves the machine. No external APIs, cloud services, or internet connections are required during document processing.

---

## 2. Problem Statement

Government and enterprise cybersecurity teams regularly produce critical advisories, threat reports, and policy documents. Communicating the findings effectively across different audiences — technical teams, executives, the general public, and social media followers — requires significant manual effort and expertise:

- A cybersecurity analyst must manually rewrite the same information multiple times, once for each format and audience.
- Copy-pasting across formats introduces inconsistencies and errors.
- Extracting the correct affected products, CVE identifiers, IP indicators, severity ratings, and recommended actions from dense advisory text is error-prone and slow.
- Generic AI tools often fabricate facts, invent statistics, or produce content that does not match the source document.
- Sensitive documents cannot be uploaded to cloud-based AI services.

The result is that most advisories never get reformatted at all, limiting their reach and impact.

---

## 3. Our Solution

UnifiOps solves this by running a structured, fact-preserving pipeline entirely on local infrastructure:

**Document ingestion** — The system accepts PDF, DOCX, and TXT files and extracts clean text using `pdfplumber` and `python-docx`.

**Deterministic locking** — Before any LLM is involved, a regex-based extractor locks the critical technical facts: CVE IDs, IP addresses, severity ratings, and explicitly-named platforms or products. These locked values are later used as ground-truth anchors to detect and prevent hallucination.

**Canonical fact extraction** — The sanitized document text is sent to a locally-running Ollama model (`qwen2.5:3b`) with a strict schema. The model is instructed to reproduce technical identifiers exactly and never invent details. If the LLM fails or returns an empty response, the system falls back to a rule-based extractor, and then to a purely deterministic fallback — so a result is always produced.

**Affected platforms and products** — Entity extraction uses six document-grounded pattern strategies (explicit enumeration lines, domain names, contextual phrases, CamelCase tokens, multi-word proper nouns, and "X users/victims" patterns) to identify specifically-named services, apps, and software from the current document. Results are never drawn from a generic brand list; every entity must appear in the uploaded file in a context that indicates it is affected.

**Multi-format generation** — Once canonical facts are available, six artifact generators run in parallel. Each generator uses only the supplied canonical facts and source text — no outside knowledge is injected. Failed generators are skipped gracefully; they do not block the other outputs.

**Fact verification** — Every generated artifact is checked against the locked parameters. CVEs, IPs, and severity ratings that appear in the output but were not found in the source are flagged. A preservation rate score is included in the API response.

**Frontend** — A web interface (served by FastAPI) presents all six outputs through dedicated pages. Each page reads the transformation result from the browser's session storage and renders the content dynamically, so the user never leaves the interface to download and re-open files.

---

## 4. Key Features

- **100% local execution** — Ollama (`qwen2.5:3b`) runs on the same machine. No cloud calls, no API keys for AI services.
- **Three-level fallback chain** — LLM schema extraction → LLM JSON format extraction → deterministic rule-based extraction. The pipeline always produces output.
- **Deterministic fact locking** — CVEs, IPs, severity ratings, and named entities are extracted by regex before the LLM sees the document, providing verifiable ground truth.
- **Document-grounded entity extraction** — Affected platforms and products are identified from the current document only; no hardcoded brand lists that cross-contaminate results.
- **PII redaction** — Email addresses and API keys/secrets are automatically redacted before text reaches the LLM.
- **SHA-256 integrity hash** — Every processed file is hashed; the hash is returned in the API response and written to the audit log.
- **Anti-hallucination audit** — Generated outputs are scored against locked facts; discrepancies are flagged as `FLAGGED_FOR_REVIEW`.
- **Dynamic video generation** — The video engine classifies the source document type (cyber advisory, threat report, research paper, news, policy, announcement) and assigns different visual scene types (title splash, alert card, step flow, network diagram, timeline, stat blocks, recommendation list, etc.) so each video has a distinct visual structure.
- **Content-aware slide generation** — The presentation engine calls Ollama to plan the slide outline, then builds a properly formatted PPTX with speaker notes.
- **Social media content with validation** — LinkedIn and X/Twitter posts are generated with platform-specific formatting rules and validated for character limits and sensitive information.
- **Threat intelligence cross-referencing** — Bundled CISA KEV data and CERT-In advisory PDFs are indexed into a local SQLite-backed vector store and queried to validate generated advisories.
- **Two interfaces** — A Streamlit operator dashboard (`app.py`) for local development and a full web application (FastAPI + HTML/JS frontend) for production use.
- **Audit logging** — Every transformation is logged with timestamp, file hash, operator configuration, and verification score via loguru.

---

## 5. Repository Structure

```
sih_content_transform/
│
├── .env.example                  # Environment variable template (copy to .env)
├── .gitignore                    # Git ignore rules (excludes ONNX models, outputs, uploads)
├── README.md                     # This file
├── requirements.txt              # Root-level minimal/unpinned dependencies (stub)
│
├── data/
│   ├── outputs/                  # Runtime-generated artifacts (advisory, PPTX, SVG, etc.)
│   │   └── .gitkeep
│   └── sample_inputs/            # Sample documents for testing
│       ├── ADVISORY-Matriminy Scam.pdf
│       ├── CERT-In Advisory CIVN-2024-0089.txt
│       ├── Data_Hacklers.pdf
│       ├── input.pdf
│       ├── sample_advisory.txt
│       └── sample_report.txt
│
├── docs/
│   ├── SIH_26154_Presentation_Content.md
│   ├── SIH_26154_Project_Documentation.pdf
│   ├── SIH_26154_Technical_Approach.md
│   ├── SIH_26154_Working_Flow_Architecture.md
│   └── Social_Media_Content_Engine.pdf
│
├── assets/
│   └── screenshots/              # UI screenshots used in documentation
│
├── html_frontend/                # Static HTML/JS frontend served by FastAPI
│   ├── 01_homepage.html          # Landing page — "1 INPUT → 6 OUTPUTS" hero
│   ├── 02_chat_interface.html    # Upload interface and query entry point
│   ├── 03_processing.html        # Live pipeline progress and navigation hub
│   ├── 04_social_media.html      # LinkedIn and X/Twitter post display
│   ├── 05_video.html             # Video storyboard viewer and MP4 player
│   ├── 06_summary.html           # Executive summary and key facts display
│   ├── 07_infographics.html      # SVG infographic viewer
│   ├── 08_advisory.html          # Formal advisory bulletin viewer
│   ├── 09_slides.html            # Presentation slide structure viewer
│   ├── tailwind.js               # Tailwind CSS standalone build (local fallback)
│   └── gsap.min.js               # GSAP animation library
│
├── my_code/                      # Primary application codebase
│   ├── app.py                    # Streamlit operator dashboard (8 tabs, all features)
│   ├── doc.py                    # Technical documentation PDF generator
│   ├── requirements.txt          # Pinned production dependencies (use this for install)
│   │
│   ├── apps/
│   │   ├── api.py                # FastAPI server — 14 routes, full transform pipeline
│   │   └── gui.py                # Alternate Streamlit dashboard (simpler, 6 tabs)
│   │
│   ├── modules/
│   │   ├── extractor.py          # Text extraction (PDF/DOCX/TXT) + deterministic locking
│   │   ├── llm_engine.py         # Pydantic-schema-constrained LLM fact extraction
│   │   ├── generators.py         # All artifact generators (summary, report, advisory, social, PPTX, video, SVG)
│   │   ├── social_engine.py      # Social media adapter integrating pallavi_code validator
│   │   ├── video_engine.py       # Video blueprint generation + MP4 rendering + scene visual types
│   │   ├── presentation_engine.py# Dynamic LLM-planned PPTX generation
│   │   ├── design_engine.py      # Shared visual theming (palettes, layouts, SVG icons)
│   │   ├── threat_intel_engine.py# Threat intel retrieval from Ishita's RAG store + bundled datasets
│   │   ├── verifier.py           # Anti-hallucination fact preservation checker
│   │   └── security.py           # SHA-256 hashing, PII redaction, audit logging
│   │
│   ├── models/
│   │   ├── liveportrait_onnx/    # LivePortrait ONNX weights (not tracked in git; optional)
│   │   └── tpsmm_onnx/           # TPSMM ONNX weights (not tracked in git; optional)
│   │
│   ├── assets/
│   │   ├── characters/           # Presenter avatar PNG (auto-generated if absent)
│   │   └── motion/               # Driving motion clips for neural animation (auto-generated if absent)
│   │
│   ├── data/
│   │   └── outputs/              # Generated artifacts when running from my_code/
│   │
│   ├── temp_uploads/             # Ephemeral upload staging directory
│   ├── video_scenes/             # Temporary video frame cache
│   │
│   └── tests/
│       ├── test_setup.py         # Environment and Ollama connectivity check
│       ├── test_phase2.py        # Document ingestion and deterministic locking
│       ├── test_phase3.py        # LLM canonical fact extraction
│       ├── test_phase4.py        # All artifact generators
│       ├── test_phase5.py        # Social media engine
│       ├── test_phase6.py        # Presentation engine
│       ├── test_phase7.py        # FastAPI backend (TestClient)
│       └── test_phase8.py        # Streamlit dashboard
│
├── pallavi_code/                 # Social media content engine (active shared library)
│   ├── generator.py              # Social post generation logic
│   ├── validator.py              # LinkedIn/X post validation (char limits, sensitive info)
│   ├── parser.py                 # Document parsing utilities
│   ├── app.py                    # Standalone social engine Flask app
│   └── requirements.txt
│
├── ishita_code/                  # Threat intelligence backend (active, integrated)
│   ├── backend/                  # Standalone FastAPI "SENTINEL" service
│   │   ├── app/
│   │   │   ├── main.py           # FastAPI app with 12 routers (auth, RAG, transformations, etc.)
│   │   │   ├── api/rag.py        # RAG ingest and query API endpoints
│   │   │   ├── models/rag.py     # SQLAlchemy ORM for threat intel records
│   │   │   └── services/rag/
│   │   │       └── store.py      # ThreatIntelVectorStore (SQLite/PostgreSQL, CISA/CERT-In/NVD ingest)
│   │   ├── data/
│   │   │   └── threat_intel_store.json  # Bundled threat intel JSON store
│   │   └── .env.example          # SENTINEL environment variables template
│   ├── datasets/                 # Bundled evidence files (indexed at runtime)
│   │   ├── Advisories-1.pdf      # CERT-In advisory evidence
│   │   ├── Advisories-2.pdf
│   │   ├── Advisories-3.pdf
│   │   ├── Vulnerability-1.pdf   # Vulnerability evidence PDFs
│   │   ├── Vulnerability-2.pdf
│   │   ├── Vulnerability-3.pdf
│   │   └── known_exploited_vulnerabilities (1).csv  # CISA KEV dataset
│   └── src/                      # React/TypeScript SPA for the standalone SENTINEL UI
│
├── archive/
│   └── prototypes/               # Archived early-stage prototypes (not active)
│       ├── tanvi_code/           # Early video blueprint prototype (Flask + MoviePy)
│       ├── sanika_code/          # Early PPTX generator prototype
│       └── stitch_frontend/      # Early HTML wireframe mockups
│
└── tests/                        # Root-level test runner
    ├── run_all_tests.py          # Runs all 9 test phases in sequence
    ├── verify_video_engine.py    # Video blueprint and motion harness
    └── live_motion_check.py      # Live Ollama end-to-end motion check
```

---

## 6. Setup & Installation

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10 or 3.11 | 3.11.x recommended |
| [Ollama](https://ollama.com) | Latest | Must be running locally |
| Git | Any recent | For cloning |
| Windows / Linux / macOS | — | Windows uses DirectML for ONNX GPU; others use CPU |

> **Ollama must be running** before you start the application. Download it from [https://ollama.com](https://ollama.com).

---

### Step 1 — Clone the Repository

```bash
git clone https://github.com/vrushikakpanchal/DataHacklers_131722.git
cd DataHacklers_131722
```

---

### Step 2 — Pull the Required Ollama Model

```bash
ollama pull qwen2.5:3b
```

Verify it is available:

```bash
ollama list
```

You should see `qwen2.5:3b` in the list. If you are on a low-memory machine, `qwen2.5:1.5b` also works but produces shorter outputs.

---

### Step 3 — Create and Activate a Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

---

### Step 4 — Install Dependencies

Use the pinned requirements from `my_code/` (not the root `requirements.txt`):

```bash
pip install -r my_code/requirements.txt
```

> On **Windows**, `onnxruntime-directml` is installed for DirectML (GPU) support. On other platforms, `onnxruntime` (CPU) is installed instead. This is handled automatically by the platform marker in `requirements.txt`.

> `weasyprint` requires the GTK runtime on Windows. If the install fails or PDF rendering fails at runtime, the advisory generator will fall back to producing an HTML file instead. See [weasyprint installation docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) for platform-specific instructions.

> `pyttsx3` requires a text-to-speech engine. On Windows this uses SAPI5 (built in). On Linux, install `espeak`: `sudo apt-get install espeak`. On macOS it uses the built-in `nsss` engine.

---

### Step 5 — Configure Environment Variables

Copy the template and edit if needed:

```bash
cp .env.example .env
```

The defaults work for a standard local setup. The only values you may need to change:

| Variable | Default | When to change |
|---|---|---|
| `OLLAMA_API_URL` | `http://localhost:11434/api/generate` | If Ollama runs on a different host/port |
| `OLLAMA_MODEL` | `qwen2.5:3b` | If you pulled a different model |
| `PORT` | `8000` | If port 8000 is occupied |

The application reads `.env` from the working directory. Environment variables are loaded automatically if a `.env` file is present; otherwise the defaults in the code are used.

---

### Step 6 — Create Required Directories

The output and upload directories are created automatically when the server starts, but you can create them manually:

```bash
mkdir -p my_code/data/outputs
mkdir -p my_code/temp_uploads
mkdir -p my_code/video_scenes
```

---

### Step 7 — Start the Application

**Option A: Web Application (FastAPI + HTML frontend) — Recommended**

```bash
cd my_code
uvicorn apps.api:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser at: **http://localhost:8000**

The `--reload` flag enables auto-restart on code changes. Remove it for production.

**Option B: Streamlit Operator Dashboard**

```bash
cd my_code
streamlit run app.py
```

Streamlit will open automatically in your browser at **http://localhost:8501**.

---

### Step 8 — Verify the Setup

Check that the server is healthy and Ollama is reachable:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy", "ollama": "online", "model": "qwen2.5:3b"}
```

If you see `"ollama": "offline"`, make sure the Ollama service is running (`ollama serve` in a separate terminal).

---

### Step 9 — Run the Test Suite (Optional)

```bash
cd my_code
python -m pytest tests/ -v
```

Or run all phases with the root-level runner:

```bash
python tests/run_all_tests.py
```

---

### Optional: ONNX Neural Character Animation

The video engine includes an optional neural character animation layer that uses ONNX models (LivePortrait or TPSMM). This layer is **not required** — the video engine automatically generates synthetic placeholder assets and falls back to static frames if the ONNX models are absent.

If you want to enable neural animation, place the ONNX model files at:

```
my_code/models/liveportrait_onnx/LP-Distilled0.1.onnx
my_code/models/liveportrait_onnx/appearance_feature_extractor.onnx
```

or

```
my_code/models/tpsmm_onnx/tpsmm.onnx
```

These files are not included in the repository (they are excluded by `.gitignore`) and must be downloaded separately.

---

### Optional: SENTINEL Threat Intelligence Backend (ishita_code)

The bundled CISA KEV CSV and CERT-In advisory PDFs in `ishita_code/datasets/` are automatically indexed into a local SQLite database at `my_code/data/threat_intel.sqlite3` on first use — no separate setup is required.

If you want to run the SENTINEL FastAPI service as a standalone application:

```bash
cd ishita_code/backend
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --port 8001
```

Docs available at: **http://localhost:8001/api/docs**

This is entirely optional. The main pipeline works without the SENTINEL service running.

---

## 7. How the System Works

```
                    ┌─────────────────────────────┐
                    │  User uploads PDF/DOCX/TXT  │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  1. Text Extraction          │
                    │  (pdfplumber / python-docx)  │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  2. Deterministic Locking    │
                    │  CVEs · IPs · Severity ·     │
                    │  Named Entities (regex)      │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  3. PII Redaction + SHA-256  │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  4. LLM Canonical Extraction │
                    │  Ollama qwen2.5:3b           │
                    │  (3 fallback levels)         │
                    └─────────────┬───────────────┘
                                  │
               ┌──────────────────┼──────────────────┐
               │                  │                  │
    ┌──────────▼──────┐  ┌────────▼───────┐  ┌───────▼──────────┐
    │ Advisory PDF     │  │ Slide Deck     │  │ SVG Infographic  │
    │ (weasyprint)     │  │ (python-pptx)  │  │ (pure SVG)       │
    └──────────────────┘  └────────────────┘  └──────────────────┘
               │                  │                  │
    ┌──────────▼──────┐  ┌────────▼───────┐  ┌───────▼──────────┐
    │ LinkedIn + X     │  │ Video Blueprint│  │ Executive Summary│
    │ (pallavi_code)   │  │ + MP4 render   │  │ (Ollama)         │
    └──────────────────┘  └────────────────┘  └──────────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  5. Fact Verification        │
                    │  (locked params vs. outputs) │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  6. Audit Log + API Response │
                    └─────────────────────────────┘
```

A user uploads a document. The server extracts the text, locks the technical facts with regex (no LLM involved yet), redacts sensitive data, hashes the file, and then asks the local Ollama model to extract structured canonical facts from the sanitized text. Once canonical facts exist, six artifact generators run. Each generator uses only facts from that document. The outputs are verified against the locked facts, an audit record is written, and the full result is returned as a JSON response. The frontend reads this JSON from session storage and renders each output on its dedicated page.

---

## 8. Important Modules

| Module | Responsibility |
|---|---|
| `modules/extractor.py` | Extracts raw text from PDF/DOCX/TXT files. Runs the deterministic parameter locking pass (CVE regex, IP regex, severity regex, named-entity extraction). Provides the fallback canonical facts builder when the LLM is unavailable. |
| `modules/llm_engine.py` | Sends the sanitized document to Ollama with a Pydantic-schema-constrained prompt. The model is forced to produce a valid `CanonicalFacts` JSON object. Locked parameters are injected into the prompt as non-negotiable ground truth. |
| `modules/generators.py` | Contains all artifact generators: executive summary, FAQ generation, technical report, HTML/PDF advisory, social media posts (LinkedIn + X), basic PPTX, SVG infographic. Each generator calls Ollama with strict source-grounding rules. |
| `modules/social_engine.py` | Adapter between the main pipeline and `pallavi_code`. Normalises canonical fact field names, selects a content archetype (CRITICAL_ALERT vs. TECHNICAL_BREAKDOWN), generates posts, then runs validation. |
| `modules/video_engine.py` | Classifies the source document type, assigns a visual scene type to each scene (title splash, alert card, steps flow, network diagram, timeline, stat blocks, etc.), generates a multi-scene video blueprint from Ollama, renders PNG frames with Pillow, synthesizes narration with pyttsx3, and compiles an MP4 with moviepy. Also drives the browser Code-as-Motion SVG renderer via the `motion_script` field. |
| `modules/presentation_engine.py` | Asks Ollama to plan a content-appropriate slide outline (title, key points, speaker notes per slide), then builds a properly formatted PPTX file using python-pptx. More sophisticated than the basic 4-slide generator in `generators.py`. |
| `modules/design_engine.py` | Shared theming library. Infers a visual theme (cyber, finance, technical, general) from the canonical facts and returns palette colours, layout type, icon name, and typography settings. Used by the SVG infographic, PPTX, and video renderers. |
| `modules/threat_intel_engine.py` | Retrieves supporting evidence for the uploaded document from a local SQLite-backed store indexed from CISA KEV data and CERT-In advisory PDFs. Used to cross-validate generated advisories against known CVE records. |
| `modules/verifier.py` | Checks that every CVE ID, IP address, and severity rating from the locked parameters appears in each generated output. Returns a preservation rate (0.0–1.0) and flags missing indicators. |
| `modules/security.py` | Computes SHA-256 hashes (file or string), redacts email addresses and API keys/secrets from text before LLM processing, and writes structured audit log entries via loguru. |
| `apps/api.py` | FastAPI server. Serves the HTML frontend as static files, handles `POST /api/v1/transform` (the main pipeline), serves generated artifacts via `/api/v1/outputs/{filename}`, and provides a `/health` check. |
| `pallavi_code/validator.py` | Validates LinkedIn and X/Twitter posts for character limits, sensitive information (emails, IPs, API keys, internal hostnames), and non-empty content. |
| `ishita_code/backend/app/services/rag/store.py` | SQLAlchemy-backed threat intelligence store. Ingests CISA KEV CSV, CERT-In PDFs, and NVD JSON. Queries by CVE ID, product name, version, or free text. Used by `threat_intel_engine.py`. |

---

## 9. Team Members

**Institution:** Usha Mittal Institute of Technology

| Name | Role |
|---|---|
| **Vrushika K Panchal** | Team Leader |
| **Tanvi Pednekar** | Video generation engine and narration synthesis |
| **Pallavi Sutar** | Social media content engine and validation |
| **Ishita Jagtap** | Threat intelligence RAG backend and SENTINEL service |
| **Shravani Patil** | Frontend development and UI/UX |
| **Sanika Thakur** | Document processing and presentation generation |

---

## 10. Troubleshooting

**`ollama: offline` in health check**
Ollama is not running. Start it with:
```bash
ollama serve
```
Then verify the model is pulled: `ollama list`

---

**`ModuleNotFoundError` when starting the server**
You are not in the right directory or the virtual environment is not activated.
```bash
# Make sure you are inside my_code/ and the venv is active
cd sih_content_transform/my_code
# Windows:
..\venv\Scripts\activate
uvicorn apps.api:app --host 0.0.0.0 --port 8000
```

---

**PDF advisory renders as HTML instead of PDF**
`weasyprint` requires the GTK3 runtime on Windows. If it is not installed, the system automatically falls back to saving an HTML file, which is fully readable in any browser. To enable PDF output on Windows, follow the [weasyprint Windows installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows).

---

**Video generation is very slow or fails**
- Video rendering (MP4 compilation) requires `moviepy`, `numpy`, `Pillow`, `pyttsx3`, and `opencv-python`. If any are missing, `create_video()` will raise `RuntimeError`. Check your install: `pip install -r my_code/requirements.txt`.
- On Windows, a system TTS voice is required for `pyttsx3`. If no voice is available, narration audio will be silent.
- Generating an MP4 can take 2–10 minutes on CPU depending on the number of scenes and resolution. Use `fast_mode=True` in the API (or tick Fast Mode in the UI) to get only the blueprint and skip MP4 rendering.

---

**`pyttsx3` fails to initialise**
On Linux, install the `espeak` TTS engine:
```bash
sudo apt-get install espeak
```

---

**Port 8000 is already in use**
Change the port:
```bash
uvicorn apps.api:app --host 0.0.0.0 --port 8080
```
Update the `PORT` value in your `.env` file to match.

---

**The `affected_systems` field is empty or shows the wrong products**
This happens when:
1. The LLM returned an empty list *and* no named entities were found by the deterministic extractor. Check that the document actually names specific affected platforms or products in its text.
2. Ollama timed out (default 180 s). Try a shorter document or increase `OLLAMA_TIMEOUT_SECONDS` in `.env`.

---

**Threat intelligence tab shows no matches**
The bundled CISA KEV CSV and CERT-In PDFs are indexed into `my_code/data/threat_intel.sqlite3` on first use. If this file does not exist yet, the first run will index automatically. Make sure `ishita_code/datasets/` contains the CSV and PDF files (they are tracked in git).

---

## 11. Development Notes

**Two application entry points exist.** `my_code/app.py` is the Streamlit dashboard and `my_code/apps/api.py` is the FastAPI server. Both import from the same `my_code/modules/` package. The Streamlit app is better for local development and debugging individual pipeline steps. The FastAPI app is the production interface.

**The transform pipeline has a three-level fallback chain.** `extract_canonical_facts()` (Pydantic schema-constrained Ollama call) → `build_canonical_facts()` (JSON-format Ollama call) → `build_fallback_canonical_facts()` (pure regex, no LLM). This means the system always returns a usable result even when Ollama is down.

**Locked parameters are the hallucination prevention layer.** CVEs, IPs, and severity ratings extracted by regex are injected into every LLM prompt as "LOCKED DETERMINISTIC PARAMETERS". The verifier then checks that these values appear in every generated output. If a generated advisory contains a CVE that was not in the source, it is flagged.

**Entity extraction is strictly document-grounded.** `_extract_named_entities()` uses only patterns that require the entity to appear in the current document in a specific context (explicit enumeration, domain name, "X users/victims" construction, etc.). There is no hardcoded brand-name list. This ensures that a WhatsApp advisory only lists WhatsApp as the affected platform, not every social app the extractor knows about.

**The video engine has two rendering paths.**
- The browser path (primary): The frontend renders scenes using the `motion_script` array and the Code-as-Motion SVG engine in `05_video.html`. This works without moviepy/ffmpeg.
- The offline MP4 path: `create_video()` uses Pillow (frame rendering) + pyttsx3 (narration audio) + moviepy (compilation). This runs when `HEAVY_RENDER_AVAILABLE = True` (all dependencies installed). On the API, it runs only when `fast_mode=False`.

**ONNX neural character animation is optional.** The video engine detects whether ONNX model files exist in `my_code/models/` and uses them for a presenter character overlay if available. If not, it generates synthetic placeholder assets automatically. This feature does not affect the scene visual types or the motion_script; it only adds a character overlay to the offline MP4 frames.

**`pallavi_code` and `ishita_code` are integrated libraries, not separate services.** `social_engine.py` imports from `pallavi_code.validator` and `modules.generators` directly. `threat_intel_engine.py` adds `ishita_code/backend/` to `sys.path` and imports `ThreatIntelVectorStore` directly. Neither requires a running external service for the main pipeline to work; the SENTINEL backend is only needed if you want the full multi-tenant REST API with authentication.

**Output files accumulate in `data/outputs/`.** Successive runs overwrite the same filenames (`advisory_report.html`, `presentation.pptx`, etc.). If you need to preserve multiple runs, copy the outputs directory manually between runs.

**Python path.** When running from `my_code/`, the modules resolve correctly because `my_code/apps/api.py` uses `sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))`. When running tests from the repo root, add `my_code/` to `PYTHONPATH` if needed: `set PYTHONPATH=my_code` (Windows) or `export PYTHONPATH=my_code` (Linux/macOS).

---

*SIH Problem Statement 26154 — NTRO Gen AI Platform for Automated Content Transformation*
*Usha Mittal Institute of Technology · 2025–2026*
