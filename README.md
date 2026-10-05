# UnifiOps: Gen AI Platform for Automated Content Transformation

**SIH Problem Statement 26154 · NTRO · Usha Mittal Institute of Technology**

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Project Resources](#2-project-resources)
3. [Problem Statement](#3-problem-statement)
4. [Our Solution](#4-our-solution)
5. [Key Features](#5-key-features)
6. [Repository Structure](#6-repository-structure)
7. [Setup and Installation](#7-setup-and-installation)
8. [How the System Works](#8-how-the-system-works)
9. [Important Modules](#9-important-modules)
10. [Team Members](#10-team-members)
11. [Troubleshooting](#11-troubleshooting)
12. [Development Notes](#12-development-notes)

## 1. Project Overview

UnifiOps is a locally running platform that takes a single source document, such as a CERT In advisory, threat report, research paper, fraud warning, or policy document, and transforms it into six output formats:

1. **Executive Summary** with key findings
2. **Formal Advisory PDF** with structured sections
3. **Social Media Posts** for LinkedIn and X/Twitter
4. **PowerPoint Slide Deck** with content aware slides
5. **SVG Infographic** based on extracted data
6. **Video Storyboard and MP4** with scene based motion graphics

Processing runs locally using Ollama and the `qwen2.5:3b` model. No external AI APIs or cloud services are required during document processing.

## 2. Project Resources

1. **Demo:** [https://youtu.be/27WRiIDVBL0](https://youtu.be/27WRiIDVBL0)
2. **System Architecture Document:** [https://drive.google.com/file/d/1VdxwNwaMxfvnL0b8SuZhV49kIprRdtTb/view?usp=sharing](https://drive.google.com/file/d/1VdxwNwaMxfvnL0b8SuZhV49kIprRdtTb/view?usp=sharing)

## 3. Problem Statement

Government and enterprise cybersecurity teams often need to communicate the same information to different audiences and across different formats.

The main challenges are:

1. Analysts manually rewrite the same advisory for multiple formats and audiences.
2. Copying information between formats can introduce inconsistencies and errors.
3. Extracting CVEs, IP indicators, affected products, severity ratings, and recommended actions from long documents is slow and error prone.
4. Generic AI tools can introduce unsupported facts or statistics.
5. Sensitive documents may not be suitable for cloud based AI services.

This makes the distribution of important advisories and reports time consuming and difficult to scale.

## 4. Our Solution

UnifiOps uses a structured, fact preserving pipeline that runs on local infrastructure.

### Document Ingestion

Accepts **PDF, DOCX, and TXT** files and extracts text using `pdfplumber` and `python-docx`.

### Deterministic Fact Locking

Before the LLM is used, regex based extraction identifies critical information including:

1. CVE IDs
2. IP addresses
3. Severity ratings
4. Named platforms and products

These values act as ground truth references during generation and verification.

### Canonical Fact Extraction

The sanitized document is processed by the local Ollama model using a structured schema. If the primary extraction fails, the system falls back to JSON format extraction and then deterministic rule based extraction.

### Document Grounded Entity Extraction

Affected platforms and products are identified from the uploaded document using multiple patterns, including explicit enumerations, domains, contextual phrases, CamelCase tokens, multi word names, and `"X users/victims"` patterns.

Entities must be supported by the current document rather than a generic brand list.

### Multi Format Generation

Six generators create the requested outputs using the canonical facts and source text. Failure of one generator does not prevent the remaining outputs from being produced.

### Fact Verification

Generated outputs are checked against the locked facts. Unsupported CVEs, IPs, or severity ratings are flagged, and a preservation score is included in the API response.

### Frontend

The FastAPI application serves the HTML and JavaScript frontend. Each output has a dedicated page and reads transformation results from browser session storage.

## 5. Key Features

| Feature                           | Description                                                                                                  |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Local execution**               | Ollama runs locally without cloud AI APIs.                                                                   |
| **Three level fallback**          | Schema based LLM extraction, JSON extraction, then deterministic extraction.                                 |
| **Deterministic fact locking**    | Critical technical values are extracted before LLM processing.                                               |
| **Document grounded entities**    | Affected products and platforms are identified from the uploaded document.                                   |
| **PII redaction**                 | Email addresses and API keys or secrets are removed before LLM processing.                                   |
| **SHA 256 integrity hash**        | Each processed file is hashed and recorded in the audit log.                                                 |
| **Fact verification**             | Generated content is checked against locked parameters.                                                      |
| **Dynamic video generation**      | Source types are mapped to different visual scene structures.                                                |
| **Content aware presentations**   | Ollama plans the slide structure before PPTX generation.                                                     |
| **Social media validation**       | LinkedIn and X/Twitter content is checked against platform limits and sensitive information.                 |
| **Threat intelligence retrieval** | CISA KEV and CERT In data are stored locally and used for supporting evidence.                               |
| **Two interfaces**                | Streamlit dashboard for local development and FastAPI with HTML and JavaScript for the main web application. |
| **Audit logging**                 | Transformations are logged with timestamps, file hashes, configuration, and verification scores.             |

## 6. Repository Structure

```text
sih_content_transform/
│
├── .env.example                  # Environment variable template
├── .gitignore                    # Git ignore rules
├── README.md                     # Project documentation
├── requirements.txt              # Root level dependency file
│
├── data/
│   ├── outputs/                  # Generated artifacts
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
│   └── screenshots/              # UI screenshots
│
├── html_frontend/                # Static HTML and JavaScript frontend
│   ├── 01_homepage.html          # Landing page and project introduction
│   ├── 02_chat_interface.html    # Document upload and query interface
│   ├── 02_social.html            # Social media output interface
│   ├── 03_processing.html        # Processing status and navigation
│   ├── 03_video.html             # Video output interface
│   ├── 04_social_media.html      # LinkedIn and X/Twitter content display
│   ├── 05_video.html             # Video storyboard and MP4 player
│   ├── 06_summary.html            # Executive summary and key facts
│   ├── 07_infographics.html      # SVG infographic viewer
│   ├── 08_advisory.html          # Advisory bulletin viewer
│   ├── 09_slides.html            # Presentation slide viewer
│   ├── gsap.min.js               # GSAP animation library
│   └── tailwind.js               # Local Tailwind CSS build
│
├── my_code/                      # Primary application code
│   ├── app.py                    # Streamlit operator dashboard
│   ├── doc.py                    # Technical documentation PDF generator
│   ├── requirements.txt          # Pinned production dependencies
│   │
│   ├── apps/
│   │   ├── api.py                # FastAPI server and transformation API
│   │   └── gui.py                # Alternate Streamlit dashboard
│   │
│   ├── modules/
│   │   ├── extractor.py          # Document text extraction and fact locking
│   │   ├── llm_engine.py         # Ollama based canonical fact extraction
│   │   ├── generators.py         # Summary, advisory, social, PPTX, video and SVG generators
│   │   ├── social_engine.py      # Social media generation and validation adapter
│   │   ├── video_engine.py       # Video blueprint generation and MP4 rendering
│   │   ├── presentation_engine.py # LLM planned PPTX generation
│   │   ├── design_engine.py      # Shared themes, layouts and visual styling
│   │   ├── threat_intel_engine.py # Local threat intelligence retrieval
│   │   ├── verifier.py           # Generated output fact verification
│   │   └── security.py            # Hashing, redaction and audit logging
│   │
│   ├── models/
│   │   ├── liveportrait_onnx/    # Optional LivePortrait ONNX models
│   │   └── tpsmm_onnx/           # Optional TPSMM ONNX models
│   │
│   ├── assets/
│   │   ├── characters/            # Presenter avatar assets
│   │   └── motion/                # Neural animation motion clips
│   │
│   ├── data/
│   │   └── outputs/              # Generated artifacts
│   │
│   ├── temp_uploads/             # Temporary uploaded files
│   ├── video_scenes/             # Temporary video frame cache
│   │
│   └── tests/
│       ├── test_setup.py         # Environment and Ollama connectivity test
│       ├── test_phase2.py        # Document ingestion and fact locking test
│       ├── test_phase3.py        # Canonical fact extraction test
│       ├── test_phase4.py        # Artifact generator tests
│       ├── test_phase5.py        # Social media engine tests
│       ├── test_phase6.py        # Presentation engine tests
│       ├── test_phase7.py        # FastAPI backend tests
│       └── test_phase8.py        # Streamlit dashboard tests
│
├── pallavi_code/                 # Social media content engine
│   ├── generator.py              # Social media post generation
│   ├── validator.py              # LinkedIn and X validation
│   ├── parser.py                 # Document parsing utilities
│   ├── app.py                    # Standalone Flask social engine
│   └── requirements.txt          # Social engine dependencies
│
├── ishita_code/                  # Threat intelligence backend
│   ├── backend/
│   │   ├── app/
│   │   │   ├── main.py           # SENTINEL FastAPI application
│   │   │   ├── api/rag.py        # RAG ingestion and query endpoints
│   │   │   ├── models/rag.py     # Threat intelligence database models
│   │   │   └── services/rag/
│   │   │       └── store.py      # Threat intelligence vector store
│   │   ├── data/
│   │   │   └── threat_intel_store.json # Bundled threat intelligence data
│   │   └── .env.example          # SENTINEL environment template
│   │
│   ├── datasets/                 # Bundled threat intelligence evidence
│   │   ├── Advisories-1.pdf
│   │   ├── Advisories-2.pdf
│   │   ├── Advisories-3.pdf
│   │   ├── Vulnerability-1.pdf
│   │   ├── Vulnerability-2.pdf
│   │   ├── Vulnerability-3.pdf
│   │   └── known_exploited_vulnerabilities (1).csv
│   │
│   └── src/                      # SENTINEL React and TypeScript frontend
│
├── archive/
│   └── prototypes/               # Archived early stage prototypes
│       ├── tanvi_code/
│       ├── sanika_code/
│       └── stitch_frontend/
│
└── tests/
    ├── run_all_tests.py          # Runs the complete test sequence
    ├── verify_video_engine.py    # Tests the video blueprint and motion pipeline
    └── live_motion_check.py      # Runs an end to end Ollama motion check
```

## 7. Setup and Installation

### Prerequisites

| Requirement           | Version        | Notes                                  |
| --------------------- | -------------- | -------------------------------------- |
| Python                | 3.10 or 3.11   | 3.11.x recommended                     |
| Ollama                | Latest         | Must run locally                       |
| Git                   | Recent version | For cloning                            |
| Windows, Linux, macOS |                | Windows supports DirectML for ONNX GPU |

Ollama must be running before starting the application.

### Step 1: Clone the Repository

```bash
git clone https://github.com/vrushikakpanchal/DataHacklers_131722.git
cd DataHacklers_131722
```

### Step 2: Pull the Ollama Model

```bash
ollama pull qwen2.5:3b
```

Verify the model:

```bash
ollama list
```

`qwen2.5:1.5b` can also be used on lower memory systems.

### Step 3: Create a Virtual Environment

**Windows**

```bash
python -m venv venv
venv\Scripts\activate
```

**macOS and Linux**

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 4: Install Dependencies

Use the pinned dependencies in `my_code/requirements.txt`:

```bash
pip install -r my_code/requirements.txt
```

On Windows, `onnxruntime-directml` is used for DirectML support. Other platforms use CPU based `onnxruntime`.

`weasyprint` may require the GTK runtime on Windows. If unavailable, advisory generation falls back to HTML.

For Linux TTS support:

```bash
sudo apt-get install espeak
```

### Step 5: Configure Environment Variables

Copy the environment template:

```bash
cp .env.example .env
```

| Variable         | Default                               | Purpose         |
| ---------------- | ------------------------------------- | --------------- |
| `OLLAMA_API_URL` | `http://localhost:11434/api/generate` | Ollama endpoint |
| `OLLAMA_MODEL`   | `qwen2.5:3b`                          | Local model     |
| `PORT`           | `8000`                                | FastAPI port    |

### Step 6: Create Required Directories

These directories are created automatically, but can also be created manually:

```bash
mkdir -p my_code/data/outputs
mkdir -p my_code/temp_uploads
mkdir -p my_code/video_scenes
```

### Step 7: Start the Application

**Option A: FastAPI and HTML Frontend**

```bash
cd my_code
uvicorn apps.api:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` in a browser.

The `--reload` option restarts the server when code changes.

**Option B: Streamlit Dashboard**

```bash
cd my_code
streamlit run app.py
```

Open `http://localhost:8501` if it does not open automatically.

### Step 8: Verify the Setup

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "ollama": "online",
  "model": "qwen2.5:3b"
}
```

If Ollama is offline, start it with:

```bash
ollama serve
```

### Step 9: Run Tests

```bash
cd my_code
python -m pytest tests/ -v
```

Or run all phases:

```bash
python tests/run_all_tests.py
```

### Optional: ONNX Neural Character Animation

The video engine can use LivePortrait or TPSMM ONNX models.

Place the models at:

```text
my_code/models/liveportrait_onnx/LP-Distilled0.1.onnx
my_code/models/liveportrait_onnx/appearance_feature_extractor.onnx
```

or:

```text
my_code/models/tpsmm_onnx/tpsmm.onnx
```

These models are not included in the repository. Without them, generated placeholder assets are used and the video engine can continue with static frames.

### Optional: SENTINEL Threat Intelligence Backend

The bundled CISA KEV CSV and CERT In advisory PDFs in `ishita_code/datasets/` are indexed into a local SQLite database on first use.

To run the SENTINEL backend separately:

```bash
cd ishita_code/backend
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --port 8001
```

API documentation is available at:

`http://localhost:8001/api/docs`

The main UnifiOps pipeline does not require this service to run.

## 8. How the System Works

```text
User uploads PDF / DOCX / TXT
              │
              ▼
┌─────────────────────────────┐
│ 1. Text Extraction          │
│    pdfplumber / python-docx │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 2. Deterministic Locking    │
│    CVEs · IPs · Severity    │
│    Named Entities           │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 3. PII Redaction + SHA 256  │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 4. Canonical Extraction     │
│    Ollama qwen2.5:3b        │
│    Three level fallback     │
└─────────────┬───────────────┘
              │
       ┌──────┼─────────┬────────────┐
       ▼      ▼         ▼            ▼
   Advisory Slides  Infographic   Social
       │      │         │            │
       └──────┴─────────┴────────────┘
              │
       ┌──────┴────────────┐
       ▼                   ▼
     Video          Executive Summary
              │
              ▼
┌─────────────────────────────┐
│ 5. Fact Verification        │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 6. Audit Log + API Response │
└─────────────────────────────┘
```

The system extracts source text, locks important technical facts, removes sensitive information, and sends the sanitized content to the local Ollama model. The resulting canonical facts are used by the six output generators. Each result is checked against the locked facts before the final API response and audit record are created.

## 9. Important Modules

| File                                            | Description                                                                          |
| ----------------------------------------------- | ------------------------------------------------------------------------------------ |
| `modules/extractor.py`                          | Extracts PDF, DOCX and TXT text and performs deterministic fact locking.             |
| `modules/llm_engine.py`                         | Uses Ollama with a Pydantic schema to extract canonical facts.                       |
| `modules/generators.py`                         | Generates summaries, reports, advisories, social posts, PPTX, SVG and video outputs. |
| `modules/social_engine.py`                      | Connects the main pipeline with the `pallavi_code` social media engine.              |
| `modules/video_engine.py`                       | Creates video blueprints, scenes, narration and MP4 output.                          |
| `modules/presentation_engine.py`                | Plans slide structure with Ollama and generates PPTX files.                          |
| `modules/design_engine.py`                      | Provides shared themes, layouts, palettes, icons and typography settings.            |
| `modules/threat_intel_engine.py`                | Retrieves supporting threat intelligence from the local store.                       |
| `modules/verifier.py`                           | Checks generated outputs against locked CVEs, IPs and severity values.               |
| `modules/security.py`                           | Handles SHA 256 hashing, PII redaction and audit logging.                            |
| `apps/api.py`                                   | Runs the FastAPI server and exposes the transformation API.                          |
| `app.py`                                        | Runs the Streamlit operator dashboard.                                               |
| `doc.py`                                        | Generates the project technical documentation PDF.                                   |
| `apps/gui.py`                                   | Provides an alternate Streamlit interface.                                           |
| `pallavi_code/generator.py`                     | Generates social media post content.                                                 |
| `pallavi_code/validator.py`                     | Validates social posts for character limits and sensitive information.               |
| `pallavi_code/parser.py`                        | Provides document parsing utilities for the social engine.                           |
| `pallavi_code/app.py`                           | Runs the standalone Flask social media application.                                  |
| `ishita_code/backend/app/main.py`               | Runs the SENTINEL FastAPI backend.                                                   |
| `ishita_code/backend/app/api/rag.py`            | Provides RAG ingestion and query endpoints.                                          |
| `ishita_code/backend/app/models/rag.py`         | Defines threat intelligence database models.                                         |
| `ishita_code/backend/app/services/rag/store.py` | Stores and queries CISA, CERT In and NVD threat intelligence.                        |
| `tests/run_all_tests.py`                        | Runs the complete test sequence.                                                     |
| `tests/verify_video_engine.py`                  | Tests the video blueprint and motion pipeline.                                       |
| `tests/live_motion_check.py`                    | Runs an end to end Ollama motion check.                                              |

## 10. Team Members

**Institution:** Usha Mittal Institute of Technology

| Name                   | Role                                                 |
| ---------------------- | ---------------------------------------------------- |
| **Vrushika K Panchal** | Team Leader                                          |
| **Tanvi Pednekar**     | Video generation engine and narration synthesis      |
| **Pallavi Sutar**      | Social media content engine and validation           |
| **Ishita Jagtap**      | Threat intelligence RAG backend and SENTINEL service |
| **Shravani Patil**     | Frontend development and UI/UX                       |
| **Sanika Thakur**      | Document processing and presentation generation      |

## 11. Troubleshooting

### `ollama: offline`

Start Ollama:

```bash
ollama serve
```

Then verify the model:

```bash
ollama list
```

### `ModuleNotFoundError`

Make sure you are inside `my_code/` and the virtual environment is active.

```bash
cd sih_content_transform/my_code
```

**Windows:**

```bash
..\venv\Scripts\activate
```

Then start the server:

```bash
uvicorn apps.api:app --host 0.0.0.0 --port 8000
```

### Advisory is generated as HTML instead of PDF

`weasyprint` requires the GTK3 runtime on Windows. If it is unavailable, the application automatically produces an HTML version.

### Video generation is slow or fails

Ensure the required packages are installed:

```bash
pip install -r my_code/requirements.txt
```

MP4 generation can take 2 to 10 minutes on CPU depending on scene count and resolution. Use `fast_mode=True` or Fast Mode in the UI to generate the blueprint without rendering the MP4.

### `pyttsx3` fails

On Linux:

```bash
sudo apt-get install espeak
```

On Windows, a system TTS voice is required. If no voice is available, narration audio will be silent.

### Port 8000 is already in use

Use another port:

```bash
uvicorn apps.api:app --host 0.0.0.0 --port 8080
```

Update the `PORT` value in `.env` if required.

### `affected_systems` is empty or incorrect

Check that the source document explicitly names the affected platforms or products. If Ollama times out, try a shorter document or increase `OLLAMA_TIMEOUT_SECONDS` in `.env`.

### Threat intelligence results are missing

The bundled CISA KEV CSV and CERT In PDFs are indexed on first use. Ensure the files in `ishita_code/datasets/` are present.

## 12. Development Notes

### Application Entry Points

There are two main interfaces:

1. `my_code/app.py` is the Streamlit dashboard for local development and debugging.
2. `my_code/apps/api.py` is the FastAPI application and primary web interface.

Both use the shared `my_code/modules/` package.

### Fallback Extraction

The canonical fact extraction pipeline follows:

```text
Pydantic schema Ollama extraction
             ↓
JSON format Ollama extraction
             ↓
Deterministic rule based extraction
```

This allows the system to return a usable result even when the LLM is unavailable.

### Fact Locking

CVE IDs, IP addresses, and severity ratings are extracted with deterministic rules and passed to the LLM as locked parameters. Generated outputs are checked against these values.

### Document Grounded Entity Extraction

Affected platforms and products must be supported by the uploaded document. The system does not rely on a hardcoded brand list.

### Video Rendering

The video engine supports two rendering paths:

1. **Browser path** uses `motion_script` and the Code as Motion SVG renderer in the frontend.
2. **Offline MP4 path** uses Pillow for frame rendering, `pyttsx3` for narration, and MoviePy for compilation.

### Optional ONNX Animation

If ONNX models are available, the video engine can add a presenter character overlay. Without them, generated placeholder assets are used.

### Integrated Libraries

`pallavi_code` and `ishita_code` are integrated into the main pipeline rather than being required as separate services. The SENTINEL backend is optional for the main transformation workflow.

### Generated Outputs

Generated files are stored in:

```text
data/outputs/
```

Successive runs can overwrite files with the same names. Copy the directory elsewhere if previous outputs need to be preserved.

### Python Path

When running from `my_code/`, modules resolve automatically. When running tests from the repository root, set the Python path if required.

**Windows:**

```bash
set PYTHONPATH=my_code
```

**Linux and macOS:**

```bash
export PYTHONPATH=my_code
```

---

*SIH Problem Statement 26154: NTRO Gen AI Platform for Automated Content Transformation*
*Usha Mittal Institute of Technology | Team Name: Data Hacklers | Team ID: 131722*
