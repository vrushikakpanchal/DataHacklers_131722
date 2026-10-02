# SIH PS 26154 Content Transformation Platform

A locally run, multi-output content transformation application for SIH Problem Statement 26154. The Streamlit interface accepts PDF, DOCX, TXT, or pasted text, applies optional PII redaction, and generates summaries, FAQs, reports, social posts, an advisory, an infographic, a presentation, and a narrated MP4. Local Ollama handles language generation; deterministic checks and bundled threat-intelligence evidence support fact preservation and verification.

## Architecture

`my_code/app.py` is the primary Streamlit entry point. It coordinates document extraction and sanitization, then calls the focused modules in `my_code/modules/`. Social posts use the Pallavi generator/validator adapter. Threat lookups use the integrated adapter and bundled Ishita evidence data, with the SQL-backed RAG path available when its optional backend code is present. Presentation, SVG, and video rendering run locally.

## Prerequisites

- Python 3.10 or newer.
- [Ollama](https://ollama.com/) running locally. The integrated generators use `qwen2.5:3b` by default. The social adapter defaults to `qwen2.5:1.5b`; set `OLLAMA_MODEL=qwen2.5:3b` as shown below or pull the 1.5b model too. `llama3` can be used only after changing the model defaults in the relevant modules.
- Working local speech synthesis support for `pyttsx3`: Windows SAPI voices, Linux eSpeak, or a compatible system voice backend.
- Internet access is not used by the transformation flow, but may be needed to install Python packages and Ollama models. MP4 encoding uses MoviePy's FFmpeg support; install system FFmpeg if the bundled encoder is unavailable.

## Quickstart

Run commands from the repository root so relative folders such as `data/outputs/`, `output/`, and `temp_uploads/` resolve consistently.

### 1. Clone the repository

```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
$env:OLLAMA_MODEL = "qwen2.5:3b"
```

macOS or Linux:

```bash
source venv/bin/activate
export OLLAMA_MODEL=qwen2.5:3b
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r my_code/requirements.txt
```

### 4. Start the local Ollama model

Install Ollama, then download and start the default model:

```bash
ollama pull qwen2.5:3b
ollama run qwen2.5:3b
```

Keep Ollama running. If the service is not already active, start it in a separate terminal with `ollama serve`. The `OLLAMA_MODEL` setting above points the social adapter at the same model used by the other integrated generators.

### 5. Run the application

In another terminal, from the repository root and with the virtual environment active:

```bash
streamlit run my_code/app.py
```

Open the local address printed by Streamlit. Sample documents are available under `my_code/data/sample_inputs/`.

## Project Structure

```text
repository-root/
├── my_code/
│   ├── app.py                       # Main Streamlit application
│   ├── apps/                        # Optional FastAPI and alternate GUI entry points
│   ├── modules/
│   │   ├── extractor.py             # PDF, DOCX, TXT extraction and fact locking
│   │   ├── security.py              # PII redaction, SHA-256, audit logging
│   │   ├── generators.py            # Written outputs, advisory, SVG and legacy helpers
│   │   ├── design_engine.py         # Shared palettes, layout inference and SVG icons
│   │   ├── social_engine.py         # Adapter to Pallavi's social generator/validator
│   │   ├── presentation_engine.py   # Dynamic PPTX generation and speaker notes
│   │   ├── video_engine.py          # Scene graphics, offline narration and MP4 render
│   │   ├── threat_intel_engine.py   # Evidence lookup and advisory validation adapter
│   │   ├── verifier.py              # Deterministic generated-content checks
│   │   └── llm_engine.py            # Canonical facts extraction used by API/GUI paths
│   ├── data/sample_inputs/          # Small sample advisory and report text files
│   ├── tests/                       # Project tests
│   └── requirements.txt             # Dependencies for the integrated application
├── pallavi_code/
│   ├── generator.py                 # Runtime dependency imported by social_engine.py
│   └── validator.py                 # Runtime dependency imported by social_engine.py
├── ishita_code/
│   ├── datasets/                    # CISA KEV CSV and CERT-In PDF evidence
│   └── backend/data/                # Bundled local threat-intelligence sample store
├── data/outputs/                    # Runtime-generated advisory, SVG, PPTX and audit log
├── output/                          # Runtime-generated MP4 and scene PNG files
├── temp_uploads/                    # Temporary uploaded source documents
├── video_scenes/                    # Legacy scene output location
├── .gitignore
└── README.md
```

The standalone Tanvi and Sanika prototypes and Ishita's standalone frontend/backend code are excluded from the distribution. The two Pallavi modules and Ishita evidence assets remain because the integrated adapters still import or read them directly. Empty output/upload folders are retained with `.gitkeep`; generated content and uploaded documents are ignored by Git.

## Troubleshooting

- **Ollama connection or missing-model error:** Start Ollama with `ollama serve`, confirm it is reachable locally, and run `ollama list`. Pull `qwen2.5:3b`; if you do not set `OLLAMA_MODEL=qwen2.5:3b`, also pull `qwen2.5:1.5b` for the social adapter.
- **`moviepy`, Pillow, or NumPy import error:** Activate the project virtual environment and run `pip install -r my_code/requirements.txt` again.
- **`pyttsx3` cannot initialize or narration is silent:** Install and enable a system speech backend/voice (Windows SAPI or Linux eSpeak), then restart the app. MP4 encoding may also need system FFmpeg.
- **Uploads or generated files appear in unexpected locations:** Start Streamlit from the repository root with `streamlit run my_code/app.py`. The app uses relative paths for temporary uploads and outputs.
- **PDF advisory downloads as HTML:** WeasyPrint may need platform-specific native libraries. The app keeps an HTML advisory fallback when PDF rendering is unavailable.
