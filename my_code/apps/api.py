import os
import sys
import shutil
import json
import logging
import requests
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.extractor import process_and_lock_document, extract_raw_text, lock_deterministic_parameters, build_fallback_canonical_facts
from modules.llm_engine import extract_canonical_facts
from modules.generators import (
    build_canonical_facts,
    generate_summary,
    generate_pdf_advisory,
    generate_presentation,
    generate_infographic_svg
)
from modules.social_engine import process_social_transformation
from modules.video_engine import generate_video_blueprint, process_video_transformation
from modules.presentation_engine import generate_dynamic_presentation
from modules.verifier import verify_all_generated_outputs
from modules.security import compute_sha256, redact_sensitive_pii, log_transformation_audit_event

app = FastAPI(
    title="NTRO GenAI Content Transformation Engine",
    description="Automated multi-format content transformation API for NTRO (SIH PS 26154)",
    version="1.0.0"
)

logger = logging.getLogger(__name__)


def _try_artifact(label, generator, *args, **kwargs):
    """Run an optional artifact generator without failing the whole request."""
    try:
        return generator(*args, **kwargs)
    except Exception:
        logger.exception("Optional %s generation failed", label)
        return None


def _fallback_video_blueprint(canonical_facts):
    actions = canonical_facts.get("recommended_actions", [])
    return {
        "title": canonical_facts.get("title", "Security Advisory Briefing"),
        "summary": canonical_facts.get("summary", ""),
        "scenes": [{
            "scene_number": 1,
            "intent": "title_alert",
            "on_screen_text": canonical_facts.get("title", "Security Advisory"),
            "visual_description": "Security advisory title and severity",
            "narration": canonical_facts.get("summary", "Review the security advisory."),
            "duration_seconds": 20,
            "metrics": [],
            "actions": actions,
        }],
        "generation_mode": "local_fallback",
    }


def _output_url(path):
    if not path or not os.path.isfile(path):
        return None
    return f"/api/v1/outputs/{os.path.basename(path)}"

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HTML_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "html_frontend"
UPLOAD_DIR = os.path.join("data", "sample_inputs")
OUTPUT_DIR = os.path.join("data", "outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


app.mount("/static", StaticFiles(directory=str(HTML_FRONTEND_DIR)), name="html_frontend")

class OperatorConfig(BaseModel):
    tone: str = "Executive / Formal"
    target_audience: str = "Leadership & Technical Teams"
    detail_level: str = "High"


@app.get("/")
def root():
    return FileResponse(HTML_FRONTEND_DIR / "01_homepage.html")


@app.get("/chat")
def chat_page():
    return FileResponse(HTML_FRONTEND_DIR / "02_chat_interface.html")


@app.get("/processing")
def processing_page():
    return FileResponse(HTML_FRONTEND_DIR / "03_processing.html")


@app.get("/social")
def social_page():
    return FileResponse(HTML_FRONTEND_DIR / "04_social_media.html")


@app.get("/video")
def video_page():
    return FileResponse(HTML_FRONTEND_DIR / "05_video.html")


@app.get("/summary")
def summary_page():
    return FileResponse(HTML_FRONTEND_DIR / "06_summary.html")


@app.get("/infographics", response_class=FileResponse)
async def get_infographics_page_plural():
    return FileResponse(HTML_FRONTEND_DIR / "07_infographics.html")


@app.get("/infographic", response_class=FileResponse)
async def get_infographics_page_singular():
    return FileResponse(HTML_FRONTEND_DIR / "07_infographics.html")


@app.get("/advisory")
def advisory_page():
    return FileResponse(HTML_FRONTEND_DIR / "08_advisory.html")


@app.get("/slides")
def slides_page():
    return FileResponse(HTML_FRONTEND_DIR / "09_slides.html")


@app.get("/health")
def health_check():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        response.raise_for_status()
        return {"status": "healthy", "ollama": "online", "model": "qwen2.5:3b"}
    except requests.RequestException:
        logger.warning("Ollama health check failed; local fallback engines remain available")
        return {"status": "degraded", "ollama": "offline", "fallback": "local_rules_engine"}


@app.post("/api/v1/transform")
async def transform_document(
    file: UploadFile = File(...),
    tone: str = Form("Executive / Formal"),
    target_audience: str = Form("Leadership & Technical Teams"),
    detail_level: str = Form("High"),
    fast_mode: bool = Form(False)
):
    """
    Full transformation pipeline endpoint:
    1. Ingest File & Lock Parameters
    2. Redact PII & Compute Hash
    3. LLM Schema Fact Extraction
    4. Multi-Format Output Generation (Integrated Pallavi + Tanvi + My_Code Engines)
    5. Fact Verification & Anti-Hallucination Audit
    6. Local Security Audit Logging
    """
    try:
        # Save uploaded file locally
        temp_file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 1. Ingestion & Parameter Locking
        ingestion_res = process_and_lock_document(temp_file_path)
        raw_text = ingestion_res["raw_text"]
        locked_params = ingestion_res["locked_parameters"]

        # 2. Security: PII Redaction & Cryptographic Hash
        sanitized_text, redaction_stats = redact_sensitive_pii(raw_text)
        file_sha256 = compute_sha256(temp_file_path)

        # 3. Local LLM Schema Extraction
        try:
            canonical_facts = extract_canonical_facts(sanitized_text, locked_params, model_name="qwen2.5:3b")
        except Exception:
            logger.exception("Canonical fact extraction failed; trying the generator fallback")
            try:
                canonical_facts = build_canonical_facts(sanitized_text, locked_params, model_name="qwen2.5:3b")
            except Exception:
                logger.exception("LLM canonical facts fallback failed; using deterministic source facts")
                canonical_facts = build_fallback_canonical_facts(sanitized_text, locked_params)

        summary = _try_artifact("executive summary", generate_summary, sanitized_text, model_name="qwen2.5:3b")
        if not summary:
            summary = canonical_facts.get("summary", "")

        # 4. Artifact Generators
        # A. Baseline Document & Visual Generators (my_code)
        pdf_path = _try_artifact("advisory PDF", generate_pdf_advisory, canonical_facts)
        dynamic_presentation = _try_artifact(
            "dynamic presentation",
            generate_dynamic_presentation,
            sanitized_text,
            output_path=os.path.join(OUTPUT_DIR, "presentation.pptx"),
            model_name="qwen2.5:3b",
        )
        if isinstance(dynamic_presentation, tuple) and len(dynamic_presentation) == 2:
            pptx_path, presentation_structure = dynamic_presentation
        else:
            pptx_path = _try_artifact("fallback presentation", generate_presentation, canonical_facts)
            presentation_structure = None
        svg_path = _try_artifact("infographic SVG", generate_infographic_svg, canonical_facts)

        # B. Social Media Content Engine & Validator (pallavi_code)
        try:
            social_res = process_social_transformation(
                canonical_facts,
                tone=tone,
                target_audience=target_audience,
                detail_level=detail_level,
            )
        except Exception:
            logger.exception("Social content generation failed")
            social_res = {"posts": {"linkedin": "", "x_thread": []}, "validation": None}
        social_posts = social_res.get("posts")
        social_validation = social_res.get("validation")

        # Save social output JSON
        social_json_path = os.path.join(OUTPUT_DIR, "social_posts.json")
        try:
            with open(social_json_path, "w", encoding="utf-8") as f:
                json.dump({"posts": social_posts, "validation": social_validation}, f, indent=2)
        except OSError:
            logger.exception("Could not save social posts JSON")
            social_json_path = None

        # C. Video Script & Rendering Engine (tanvi_code)
        video_path = None
        try:
            if fast_mode:
                source_text = json.dumps(canonical_facts, ensure_ascii=False, indent=2)
                video_package = generate_video_blueprint(
                    text=source_text,
                    target_audience="General Public",
                    tone="Informative",
                    duration="60s"
                )
                video_res = {"blueprint": video_package, "video_path": None}
            else:
                video_res = process_video_transformation(canonical_facts, output_dir=OUTPUT_DIR)
                video_package = video_res.get("blueprint")
                video_path = video_res.get("video_path")
        except Exception:
            logger.exception("Video blueprint or rendering failed; using a local blueprint")
            video_package = _fallback_video_blueprint(canonical_facts)
            video_res = {"blueprint": video_package, "video_path": None}

        # Save video blueprint JSON
        video_json_path = os.path.join(OUTPUT_DIR, "video_package.json")
        try:
            with open(video_json_path, "w", encoding="utf-8") as f:
                json.dump(video_package, f, indent=2)
        except OSError:
            logger.exception("Could not save video package JSON")
            video_json_path = None

        infographic = {
            "title": canonical_facts.get("title"),
            "severity": canonical_facts.get("severity"),
            "summary": canonical_facts.get("summary"),
            "cve_ids": canonical_facts.get("cve_ids", []),
            "affected_systems": canonical_facts.get("affected_systems", []),
            "recommended_actions": canonical_facts.get("recommended_actions", []),
            "svg_url": _output_url(svg_path),
        }

        # 5. Verification & Anti-Hallucination Audit
        audit_report = verify_all_generated_outputs(canonical_facts, social_posts, video_package)

        # 6. Write Audit Event
        operator_config = {"tone": tone, "target_audience": target_audience, "detail_level": detail_level}
        log_transformation_audit_event(
            source_file=file.filename,
            source_hash=file_sha256,
            operator_config=operator_config,
            verification_score=audit_report.get("average_fact_preservation_rate", 1.0),
            status=audit_report.get("overall_status", "PASSED")
        )

        return JSONResponse(content={
            "status": "success",
            "filename": file.filename,
            "sha256_hash": file_sha256,
            "redaction_stats": redaction_stats,
            "canonical_facts": canonical_facts,
            "summary": summary,
            "social_posts": social_posts,
            "video_package": video_package,
            "infographic": infographic,
            "presentation_structure": presentation_structure,
            "social_media_validation": social_validation,
            "verification_audit": audit_report,
            "download_urls": {
                "advisory_pdf": _output_url(pdf_path),
                "presentation_pptx": _output_url(pptx_path),
                "infographic_svg": _output_url(svg_path),
                "social_json": _output_url(social_json_path),
                "social_posts_json": _output_url(social_json_path),
                "video_package_json": _output_url(video_json_path),
                "video_mp4": _output_url(video_path),
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/outputs/generated_advisory.mp4")
def get_generated_advisory_video():
    file_path = os.path.join(OUTPUT_DIR, "generated_advisory.mp4")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Generated video is not available yet.")
    return FileResponse(file_path, media_type="video/mp4", filename="generated_advisory.mp4")

@app.get("/api/v1/outputs/{filename}")
def get_output_file(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Requested artifact file not found.")
    return FileResponse(file_path)
