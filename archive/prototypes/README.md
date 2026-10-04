# Prototype Archive

This directory preserves standalone prototype implementations developed during the early phases of the **NTRO Problem Statement 26154: Gen AI Platform for Automated Content Transformation** project.

The active, production-grade versions of these components have been integrated into `my_code/modules/` and `html_frontend/`. These historical prototypes are preserved here for reference, research, and reproducibility.

---

## Archived Prototypes

### 1. `tanvi_code/`
- **Focus:** Video Blueprint & Narration Generation
- **Original Stack:** Flask, Qwen, MoviePy, pyttsx3
- **Active Integration:** Refactored and integrated into `my_code/modules/video_engine.py` (with the interactive client-side Code-as-Motion playback engine in `html_frontend/05_video.html` and optional offline MoviePy rendering).

### 2. `sanika_code/`
- **Focus:** Slide & Presentation Generation
- **Original Stack:** Python-pptx, local LLM schema extractor
- **Active Integration:** Refactored and integrated into `my_code/modules/presentation_engine.py` with dynamic layout scaling and deterministic fact grounding.

### 3. `stitch_frontend/`
- **Focus:** Early UI Mockups & Screen Stitching
- **Original Stack:** Raw HTML, Tailwind CDN, vanilla JavaScript
- **Active Integration:** Standardized and evolved into the production web application in `html_frontend/`, served directly by `my_code/apps/api.py`.
