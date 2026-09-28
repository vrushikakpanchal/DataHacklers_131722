# SIH PS 26154 — Working Flow and Integration Architecture

This document describes the active execution path in `my_code/app.py` and the modules it imports. It distinguishes implemented behavior from optional paths and limitations. Paths such as `data/outputs/` are relative to the process working directory.

## 1. End-to-End Execution Flow

### Entry point and orchestration

`my_code/app.py` is the main interface and orchestration script. It imports the extraction, security, writing, social, presentation, video, and threat-intelligence functions at startup. It presents a document input area, operator controls, two generation buttons, and output tabs. The application retains generated values in Streamlit session state for rendering and download controls.

When the operator selects **Generate Written Formats**, the script calls the written/social/presentation/advisory/infographic/evidence functions in its tab order during that application run. These calls are sequential in the current code; there is no parallel task queue. **Generate Video Output** is a separate action that generates a blueprint and then renders the MP4.

### Phase 1: Ingestion and text extraction — `modules/extractor.py`

The upload widget in `app.py` accepts `.pdf`, `.docx`, and `.txt`. Uploaded bytes are written to `temp_uploads/<uploaded-name>` relative to the current working directory. Alternatively, an operator can paste text directly; pasted text bypasses the file extractor.

`extract_raw_text(file_path)` checks that the path exists, dispatches by extension, and returns text:

- TXT is opened as UTF-8 and read as a string.
- PDF is opened with `pdfplumber`; non-empty page text is joined with newline characters.
- DOCX is opened with `python-docx`; paragraph text and table cell text are collected and joined.
- Other extensions raise `ValueError`.

The extractor does not use PyMuPDF/`fitz`, preserve page or section metadata in its return value, normalize text beyond joining the extracted parts, or enforce a payload-size/schema limit. `lock_deterministic_parameters(text)` separately finds CVE patterns, IPv4-looking addresses, severity words, and a character count. It does not validate all extracted facts. `process_and_lock_document()` is a helper but is not the main `app.py` ingestion call.

### Phase 2: Redaction, hashing, and audit — `modules/security.py`

After extraction, `app.py` optionally calls `redact_sensitive_pii`. Its regex rules redact email addresses and values following selected API-key, secret-key, or auth-token labels. It returns the changed text and two redaction counts. This is pattern-based coverage, not comprehensive PII or secret detection. If redaction raises an exception, `app.py` warns and continues with the unredacted source text.

The app computes a SHA-256 digest after upload/extraction and before generation. For a file it hashes the uploaded file bytes at `source_path`; for pasted text it hashes the raw text string. Thus the displayed digest identifies the original input, not the redacted derivative.

`log_transformation_audit_event()` creates an event dictionary and writes a formatted Loguru message to `data/outputs/audit.log`. It does not write `audit_log.json`, a relational database record, or an append-only hash chain. In the current app, audit calls occur for the written-format/threat-check action and for the video action; this is not a log entry for every individual renderer invocation. The function returns its event dictionary, while the app does not persist that return value separately.

### Phase 3: Domain and theme inference — `modules/design_engine.py`

`infer_design(canonical_facts)` applies deterministic keyword checks to fields such as title, summary, topic, category, severity, CVE IDs, affected systems, recommended actions, and metrics. It selects one of four built-in themes (`cyber`, `finance`, `technical`, or `general`), one layout intent, an icon/motif name, a palette, typography constants, and spacing constants. The default is the general palette and recommendation-matrix layout.

The design engine does not call an LLM. It does not independently analyze an entire source document; it infers from the fact fields supplied by a renderer. `svg_icon()` returns a small inline icon from a fixed built-in set. `generators.py`, `presentation_engine.py`, and `video_engine.py` use the design helper for their visual output.

### Phase 4: Operator parameters — `app.py` and generator wrappers

The sidebar gathers target audience, tone, language, detail level, communication objective, content style, redaction choice, and video duration. `app.py` passes language, detail level, objective, and content style to summary, FAQ, report, and canonical-fact generation. It passes the audience, tone, language, objective, and style values to the social adapter and passes audience, tone, language, duration, objective, and style to video-blueprint generation.

The presentation call receives source text only; it does not receive the sidebar selections. The PDF and SVG renderers consume canonical facts rather than the full operator settings. Parameters are prompt text or function arguments; they are not universal system-level policies and do not override verification.

### Phase 5: Multi-format generation

#### Executive summary, FAQs, detailed report, and canonical facts — `modules/generators.py`

`generate_summary`, `generate_faqs`, and `generate_report` call `ollama.chat` with the default model name `qwen2.5:3b` and the supported operator parameters. The main app catches errors around these calls and displays an error. These three functions do not have a cached-template fallback.

`build_canonical_facts` asks Ollama for a JSON advisory structure. It catches any exception and returns a hard-coded fallback fact object using a shortened source summary and a generic recommendation. When deterministic locked parameters are supplied, their CVEs and IPs are merged into the returned fields; a locked severity is copied only if the model result lacks severity.

#### Social posts — `modules/social_engine.py` and `pallavi_code/`

`process_social_transformation` adapts facts/settings and calls Pallavi's `generate_social_content` from `pallavi_code/generator.py`. If that structured call raises, the adapter tries Pallavi's `generate_content` with formatted source text. It then passes LinkedIn and X-thread output to `pallavi_code/validator.py::validate_content` and returns posts plus validation results.

This is an alternate Ollama-backed generation attempt, not a guaranteed offline/static template fallback. The adapter's returned validation concerns the social output and is separate from the main threat-evidence validation.

#### Structured advisory and PDF/HTML — `modules/generators.py`

`generate_pdf_advisory(canonical_facts)` writes an HTML advisory to `data/outputs/advisory_report.html`, then attempts PDF rendering with WeasyPrint at `data/outputs/advisory_report.pdf`. If WeasyPrint raises, it returns the HTML path. The app exposes whichever file was returned and labels the download accordingly. The current function builds HTML using interpolated fact values; this module does not add a separate sanitization/escaping layer for each field.

#### SVG infographic — `modules/generators.py` and `modules/design_engine.py`

`generate_infographic_svg` builds SVG markup directly and writes `data/outputs/infographic_blueprint.svg`. It uses inferred theme/layout values, inline icons, rounded cards, badges, and layout-specific content placement. It does not depend on the `svgwrite` package. The app embeds the SVG in the interface and offers the `.svg` file for download. Rendering or file errors are caught by the app and displayed.

#### PowerPoint deck — `modules/presentation_engine.py`

`generate_dynamic_presentation(source_text)` calls local Ollama to create a Pydantic-validated slide structure, then `build_presentation` creates a `python-pptx` deck at `data/outputs/dynamic_presentation.pptx`. The renderer creates a cover and distinct overview, analysis/action, process, and recommendation layouts, with additional content slides if present. It uses rounded shape containers, theme-derived colors, and writes speaker notes to each slide's notes text frame.

There is no Ollama-disconnection or cached-outline fallback in this module. A generation or validation error is caught in `app.py`, shown to the operator, and prevents the normal deck download path for that run.

#### Video blueprint, scenes, narration, and MP4 — `modules/video_engine.py`

The video tab first calls `generate_video_blueprint`, which sends source text and selected video parameters to the local Ollama HTTP endpoint at `http://localhost:11434/api/generate`. Network errors and invalid responses are raised as runtime errors; the app displays the blueprint error. No cached blueprint template is used.

On a valid blueprint, `create_video`:

1. Creates `output/video_scenes/` and a temporary directory for narration WAV files.
2. Calls `pyttsx3` once for each scene with non-empty narration, then measures each WAV duration using MoviePy.
3. Draws scene PNGs using Pillow and the inferred design. The scene images are written to `output/video_scenes/scene_<number>.png`.
4. Creates MoviePy image clips; durations are extended as needed to cover the audio. It adds zoom/drift, animated text/progress overlays, fades, and crossfades.
5. Attaches available narration audio clips with audio fades and encodes the final video, normally `output/generated_advisory.mp4`, using H.264 video and AAC audio.
6. Closes measured audio clips and, after successful encoding, closes the final and scene clips. The temporary WAV directory is cleaned when its context exits.

The renderer includes visual narration/subtitle overlays during normal rendering. It does **not** catch `pyttsx3.init()` or synthesis errors and continue with a silent/subtitle-only video; such an error aborts the render before scene assembly completes. MoviePy clips are explicitly closed after successful encoding, but cleanup is not protected by a `finally` block if encoding raises.

`process_video_transformation()` is an additional wrapper that serializes canonical facts, creates a blueprint with default settings, and writes an MP4 under its `output_dir` (default `data/outputs`). The active Streamlit app calls `generate_video_blueprint()` and `create_video()` directly instead.

#### Threat intelligence retrieval — `modules/threat_intel_engine.py`

When written formats run, the app calls `retrieve_threat_intel(processed_text)`. The adapter first tries Ishita's optional SQLAlchemy/RAG store and indexing path. Its bundled evidence inputs include a local JSON sample store, a CISA KEV CSV, and CERT-In PDF files. If the optional RAG import/setup/query fails, it falls back to exact-CVE and token-overlap matching against locally loaded JSON/CSV/PDF records. This is a local bundled-evidence path; the main app does not call a live NVD or CISA API.

The app validates the generated detailed report against source indicators and retrieved matches using `validate_advisory_against_evidence`, which calls `modules/verifier.py`. The UI displays retrieved records, discrepancy details, preservation rate, source digest, and audit status. Evidence retrieval can return no matches or a warning; this does not stop the other generated formats.

### Phase 6: Fact verification — `modules/verifier.py` and threat adapter

`verify_content_against_facts` performs case-insensitive substring checks for locked CVEs and severity labels and exact substring checks for IP addresses. It computes a preservation percentage across all selected indicators. Its PASS decision requires CVEs and IPs to be present; missing severity labels are reported and affect the score but do not alone change that decision to WARN.

`validate_advisory_against_evidence` separately identifies CVEs not found in source or retrieved evidence, IPs not found in source, and severity labels outside its collected source/evidence set. It then calls the deterministic verifier and returns a PASS or FLAGGED result.

In the active `app.py` path, this threat/evidence verification is applied to `report_data` (the detailed generated report), not comprehensively to every output. Pallavi's social validator checks social output through its own rules. The presentation and video are not passed through a common post-generation fact-verification gate. Video audit status is set from render success and uses a hard-coded score of 100; it is not a video fact-verification score. A passing status therefore means only that the implemented checks passed, not that all generated claims are true.

## 2. System Dependency and Integration Matrix

| Module / component | Underlying dependency | Primary role and active integration | Fallback / resilience behavior | Main artifact or result |
|---|---|---|---|---|
| `app.py` | Streamlit; imported project modules | Main UI, operator parameters, sequencing, previews, downloads, exception display | Per-tab `try/except` blocks display errors; no job queue or global recovery layer | Session state plus rendered/downloadable outputs |
| `extractor.py` | `pdfplumber`, `python-docx`, Python file I/O and regex | TXT/PDF/DOCX extraction and deterministic indicator locking | Unsupported extension/path raises an error; no parser fallback | Extracted text and lock-parameter dictionary |
| `security.py` | `hashlib`, `re`, `loguru` | Source SHA-256, selected pattern redaction, local log message | Redaction exception is caught by `app.py`, which continues with original text; logger is the configured audit sink | SHA-256 hex string; `data/outputs/audit.log` |
| `design_engine.py` | Internal Python keyword/rule logic | Palette, theme, layout, icon, spacing, and typography inference | Built-in `general` theme and recommendation-matrix layout | Design parameter dictionary / inline SVG icon |
| `generators.py` | `ollama`; Python HTML/SVG generation; optional `weasyprint`; `python-pptx` imports for legacy helpers | Summary, FAQ, report, canonical facts, advisory, SVG, and legacy generation helpers | Canonical-facts function returns a generic fallback object on any exception; PDF function returns HTML if WeasyPrint fails; summary/FAQ/report have no internal fallback | Text in app state; advisory PDF or HTML; SVG at `data/outputs/infographic_blueprint.svg` |
| `social_engine.py` | `pallavi_code/generator.py`, `pallavi_code/validator.py`; Pallavi generator uses `requests` to local Ollama | Adapter for LinkedIn and X-thread creation and social validation | If structured generation raises, tries `generate_content`; second path may also require Ollama and is not a fixed template guarantee | Posts and validator result in app state |
| `presentation_engine.py` | `ollama`, `pydantic`, `python-pptx` | Structured slide outline, themed PPTX, embedded speaker notes | No cached outline or static deck fallback on model failure; app displays an error | `data/outputs/dynamic_presentation.pptx` plus outline |
| `video_engine.py` | `requests`, `pyttsx3`, `numpy`, Pillow, MoviePy, local Ollama HTTP API | Blueprint, scene images, narration WAVs, transitions, and MP4 render | Ollama error is raised; TTS error aborts rendering; no silent/subtitle-only failure fallback. Temporary WAVs are cleaned; clip close occurs after successful encoding | `output/video_scenes/scene_*.png`; `output/generated_advisory.mp4` in active app |
| `threat_intel_engine.py` | Optional Ishita SQLAlchemy/RAG modules; bundled JSON/CSV/PDF; optional `pdfplumber` | Local threat-record retrieval and advisory/evidence comparison | On missing/broken RAG or query failure, uses bundled local records and keyword/CVE matching | Match and validation dictionaries; local SQLite may be created under `my_code/data/` if RAG setup succeeds |
| `verifier.py` | Python regex/string matching and JSON serialization | Selected CVE/IP/severity presence checks and preservation score | Returns warning/status and missing-value lists; does not assess semantic truth | Verification dictionaries shown in threat tab |
| Pallavi generator/validator | Local Ollama HTTP API via `requests`; regex and validation helpers | Generates and checks social deliverables | Adapter retries through its `generate_content` path after primary structured generation errors; no guarantee of generation if Ollama is down | LinkedIn string, X thread, validation result |

**Not present in the active flow:** `fitz`/PyMuPDF extraction, `svgwrite`, `audit_log.json`, a relational audit database in `my_code`, guaranteed subtitle-only rendering after TTS failure, a cached video blueprint after Ollama failure, parallel generation workers, or a universal verifier gate over all generated artifacts.

## 3. Runtime Failure Modes and Actual Resilience

| Failure mode | Actual code behavior | Operator-visible effect / limit |
|---|---|---|
| Missing or broken audio driver / `pyttsx3` initialization | `_generate_narration_audio` calls `pyttsx3.init()` without a catch-and-continue fallback. Synthesis exceptions propagate from `create_video`. | `app.py` catches the video-render exception and displays “Video Rendering Error”. Scene assembly/MP4 completion is not guaranteed; no silent video or subtitle-only fallback is implemented. |
| Ollama unavailable during video blueprint generation | The HTTP request exception is wrapped in `RuntimeError`; JSON/response parse failures also raise. `app.py` catches and displays “Blueprint Error”. | No cached blueprint is loaded. A prior blueprint in session state is not a designed fallback and should not be treated as one. |
| Ollama unavailable during summary, FAQ, report, or deck generation | Summary/FAQ/report errors reach the app's exception handling. Presentation structure generation propagates the Ollama or schema error to its app handler. | The relevant output shows an error. Only `build_canonical_facts` has a generic hard-coded result fallback; that fallback does not make the other outputs available. |
| Social model call failure | The adapter catches an exception from `generate_social_content` and tries `generate_content`. | The second function is still an Ollama-backed generation path; total model/service failure can still result in the app displaying a social generation error. |
| WeasyPrint or native PDF dependency failure | The advisory function catches the PDF-render exception and returns the previously written HTML report path. | The app offers the HTML advisory and warns that PDF rendering was unavailable. |
| Optional RAG backend missing or query fails | The threat adapter records a warning and uses its bundled local JSON/CSV/PDF lookup. | Results may be fewer or absent; app shows retrieval source/warning and still reports the validation output. |
| Memory/resource pressure during MP4 export | Frames are fixed at 1280x720; video clips are composed and encoded at 24 fps. The code closes measured audio clips and closes final/scene clips after successful encoding; temporary narration files use a temporary directory. | There is no explicit low-memory mode, bounded worker queue, or `finally` cleanup of all MoviePy clips if encoding fails. A failed export can leave resources open until process cleanup. |
| Invalid or empty video blueprint | `create_video` raises `ValueError` if there are no scenes. | The app displays a render error; there is no automatic substitute storyboard. |

## Output Locations at a Glance

| Output | Location in the active application |
|---|---|
| Audit log | `data/outputs/audit.log` |
| Advisory HTML | `data/outputs/advisory_report.html` |
| Advisory PDF, when WeasyPrint succeeds | `data/outputs/advisory_report.pdf` |
| SVG infographic | `data/outputs/infographic_blueprint.svg` |
| PowerPoint presentation | `data/outputs/dynamic_presentation.pptx` |
| Video scene PNGs | `output/video_scenes/scene_<number>.png` |
| Narrated MP4 | `output/generated_advisory.mp4` |
| Uploaded documents | `temp_uploads/<uploaded-name>` |

