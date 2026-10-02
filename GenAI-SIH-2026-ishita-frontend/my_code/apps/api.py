import os
import sys
import json
import uuid
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

MY_CODE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = MY_CODE_DIR.parent
os.chdir(REPO_ROOT)
if str(MY_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(MY_CODE_DIR))

from modules.extractor import process_and_lock_document, extract_raw_text, lock_deterministic_parameters
from modules.llm_engine import extract_canonical_facts
from modules.generators import (
    generate_pdf_advisory,
    generate_presentation,
    generate_infographic_svg,
    generate_summary,
)
from modules.social_engine import process_social_transformation
from modules.video_engine import process_video_transformation
from modules.presentation_engine import generate_dynamic_presentation
from modules.verifier import verify_all_generated_outputs
from modules.security import compute_sha256, redact_sensitive_pii, log_transformation_audit_event

FRONTEND_DIR = REPO_ROOT / "stitch_frontend"
UPLOAD_DIR = REPO_ROOT / "temp_uploads"
OUTPUT_DIR = REPO_ROOT / "data" / "outputs"
JOBS_DIR = OUTPUT_DIR / "jobs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(JOBS_DIR, exist_ok=True)

app = FastAPI(
    title="SecuScribe Content Transformation API",
    description="Multi-format cybersecurity content transformation API (SIH PS 26154)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class OperatorConfig(BaseModel):
    tone: str = "Executive / Formal"
    target_audience: str = "Leadership & Technical Teams"
    detail_level: str = "High"


DELIVERABLE_KEYS = (
    "social",
    "video",
    "advisory",
    "summary",
    "slides",
    "infographic",
)


def _parse_selected(raw: str) -> List[str]:
    if not raw or not raw.strip():
        return list(DELIVERABLE_KEYS)
    items = [item.strip().lower() for item in raw.split(",") if item.strip()]
    valid = [item for item in items if item in DELIVERABLE_KEYS]
    return valid or list(DELIVERABLE_KEYS)


def _safe_basename(filename: Optional[str], fallback: str) -> str:
    name = os.path.basename(filename or fallback).replace("..", "")
    return name or fallback


def _write_job(job: dict) -> None:
    path = JOBS_DIR / f"{job['job_id']}.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(job, handle, indent=2, default=str)


def _load_jobs() -> List[dict]:
    jobs = []
    if not JOBS_DIR.exists():
        return jobs
    for path in sorted(JOBS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(path, encoding="utf-8") as handle:
                jobs.append(json.load(handle))
        except (OSError, json.JSONDecodeError):
            continue
    return jobs


@app.get("/health")
def health_check():
    return {"status": "healthy", "product": "SecuScribe", "api": "online"}


@app.get("/api/v1/status")
def api_status():
    return {"status": "online", "system": "SecuScribe Content Transformation API"}


@app.get("/api/v1/jobs")
def list_jobs():
    summaries = []
    for job in _load_jobs()[:20]:
        summaries.append(
            {
                "job_id": job.get("job_id"),
                "filename": job.get("filename"),
                "created_at": job.get("created_at"),
                "status": job.get("status"),
                "title": (job.get("canonical_facts") or {}).get("title") or job.get("filename"),
            }
        )
    return {"jobs": summaries}


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str):
    path = JOBS_DIR / f"{job_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Transformation job not found.")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


@app.post("/api/v1/transform")
async def transform_document(
    file: Optional[UploadFile] = File(None),
    source_text: str = Form(""),
    tone: str = Form("Executive / Formal"),
    target_audience: str = Form("Leadership & Technical Teams"),
    detail_level: str = Form("High"),
    language: str = Form("English"),
    goal: str = Form("Inform"),
    instructions: str = Form(""),
    selected_deliverables: str = Form("social,video,advisory,summary,slides,infographic"),
):
    """Run the existing local transformation pipeline and return generated artifacts."""
    selected = _parse_selected(selected_deliverables)
    job_id = str(uuid.uuid4())
    errors = {}
    temp_file_path = None

    try:
        if file is not None and file.filename:
            filename = _safe_basename(file.filename, "upload.bin")
            temp_file_path = str(UPLOAD_DIR / f"{job_id}_{filename}")
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        elif source_text.strip():
            filename = "pasted_source.txt"
            temp_file_path = str(UPLOAD_DIR / f"{job_id}_{filename}")
            with open(temp_file_path, "w", encoding="utf-8") as buffer:
                buffer.write(source_text.strip())
                if instructions.strip():
                    buffer.write("\n\nOperator instructions:\n")
                    buffer.write(instructions.strip())
        else:
            raise HTTPException(
                status_code=400,
                detail="Attach a PDF, DOCX, or TXT file, or provide source text to transform.",
            )

        file_size = os.path.getsize(temp_file_path)
        ingestion_res = process_and_lock_document(temp_file_path)
        raw_text = ingestion_res["raw_text"]
        locked_params = ingestion_res["locked_parameters"]
        if instructions.strip() and file is not None:
            raw_text = raw_text + "\n\nOperator instructions:\n" + instructions.strip()

        sanitized_text, redaction_stats = redact_sensitive_pii(raw_text)
        file_sha256 = compute_sha256(temp_file_path)

        try:
            canonical_facts = extract_canonical_facts(
                sanitized_text, locked_params
            )
        except Exception as exc:
            canonical_facts = {
                "title": filename,
                "severity": (locked_params.get("locked_severities") or ["UNRATED"])[0],
                "summary": sanitized_text[:400],
                "cve_ids": locked_params.get("locked_cves", []),
                "affected_systems": [],
                "recommended_actions": [],
                "locked_ips": locked_params.get("locked_ips", []),
            }
            errors["canonical_facts"] = str(exc)

        operator_config = {
            "tone": tone,
            "target_audience": target_audience,
            "detail_level": detail_level,
            "language": language,
            "goal": goal,
        }
        social_settings = {
            "audience": target_audience,
            "tone": tone,
            "objective": goal,
            "language": language,
            "detail": detail_level,
        }

        download_urls = {}
        social_posts = None
        social_validation = None
        video_package = None
        video_path = None
        executive_summary = None
        slide_structure = None
        pdf_path = None
        pptx_path = None
        svg_path = None

        if "advisory" in selected:
            try:
                pdf_path = generate_pdf_advisory(canonical_facts)
                download_urls["advisory"] = f"/api/v1/outputs/{os.path.basename(pdf_path)}"
                download_urls["advisory_pdf"] = download_urls["advisory"]
            except Exception as exc:
                errors["advisory"] = str(exc)

        if "slides" in selected:
            try:
                pptx_path, slide_structure = generate_dynamic_presentation(
                    sanitized_text,
                    output_path=str(OUTPUT_DIR / "dynamic_presentation.pptx"),
                )
                download_urls["presentation_pptx"] = f"/api/v1/outputs/{os.path.basename(pptx_path)}"
            except Exception as exc:
                errors["slides"] = str(exc)
                try:
                    pptx_path = generate_presentation(canonical_facts)
                    download_urls["presentation_pptx"] = f"/api/v1/outputs/{os.path.basename(pptx_path)}"
                except Exception as inner:
                    errors["slides"] = str(inner)

        if "infographic" in selected:
            try:
                svg_path = generate_infographic_svg(canonical_facts)
                download_urls["infographic_svg"] = f"/api/v1/outputs/{os.path.basename(svg_path)}"
            except Exception as exc:
                errors["infographic"] = str(exc)

        if "social" in selected:
            try:
                social_res = process_social_transformation(canonical_facts, settings=social_settings)
                social_posts = social_res.get("posts")
                social_validation = social_res.get("validation")
                social_json_path = OUTPUT_DIR / "social_posts.json"
                with open(social_json_path, "w", encoding="utf-8") as handle:
                    json.dump({"posts": social_posts, "validation": social_validation}, handle, indent=2)
                download_urls["social_posts_json"] = "/api/v1/outputs/social_posts.json"
            except Exception as exc:
                errors["social"] = str(exc)

        if "video" in selected:
            try:
                video_package = None
                video_path = None
                try:
                    video_res = process_video_transformation(canonical_facts, output_dir=str(OUTPUT_DIR))
                    if isinstance(video_res, dict):
                        video_package = video_res.get("blueprint")
                        video_path = video_res.get("video_path")
                except Exception as inner_exc:
                    from modules.generators import generate_video_package
                    video_package = generate_video_package(canonical_facts)

                if not video_package:
                    from modules.generators import generate_video_package
                    video_package = generate_video_package(canonical_facts)

                video_json_path = OUTPUT_DIR / "video_package.json"
                with open(video_json_path, "w", encoding="utf-8") as handle:
                    json.dump(video_package, handle, indent=2)
                download_urls["video_package_json"] = "/api/v1/outputs/video_package.json"
                if video_path and os.path.exists(video_path):
                    download_urls["video_mp4"] = f"/api/v1/outputs/{os.path.basename(video_path)}"
            except Exception as exc:
                errors["video"] = str(exc)

        if "summary" in selected:
            try:
                executive_summary = generate_summary(
                    sanitized_text,
                    language=language,
                    detail_level=detail_level,
                    objective=goal,
                    content_style=tone,
                )
            except Exception as exc:
                executive_summary = canonical_facts.get("summary") or sanitized_text[:500]
                errors["summary"] = str(exc)

        audit_report = {}
        try:
            audit_report = verify_all_generated_outputs(
                canonical_facts, social_posts or {}, video_package or {}
            )
        except Exception as exc:
            errors["verification"] = str(exc)
            audit_report = {
                "average_fact_preservation_rate": 0,
                "overall_status": "UNAVAILABLE",
            }

        overall_status = "FAILED" if errors and not canonical_facts else audit_report.get("overall_status", "PASSED")
        if errors and any(key in errors for key in selected):
            overall_status = "PARTIAL" if (social_posts or executive_summary or pdf_path) else "FAILED"

        log_transformation_audit_event(
            source_file=filename,
            source_hash=file_sha256,
            operator_config=operator_config,
            verification_score=audit_report.get("average_fact_preservation_rate", 0),
            status=overall_status,
        )

        payload = {
            "job_id": job_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "filename": filename,
            "file_size": file_size,
            "sha256_hash": file_sha256,
            "status": overall_status,
            "selected_deliverables": selected,
            "operator_config": operator_config,
            "instructions": instructions,
            "redaction_stats": redaction_stats,
            "canonical_facts": canonical_facts,
            "executive_summary": executive_summary,
            "social_posts": social_posts,
            "social_media_validation": social_validation,
            "video_package": video_package,
            "slide_structure": slide_structure,
            "verification_audit": audit_report,
            "download_urls": download_urls,
            "errors": errors,
        }
        _write_job(payload)
        return JSONResponse(content=payload)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/outputs/{filename}")
def get_output_file(filename: str):
    safe_name = os.path.basename(filename)
    file_path = OUTPUT_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Requested artifact file not found.")
    return FileResponse(str(file_path), filename=safe_name)


@app.get("/")
def serve_home():
    home = FRONTEND_DIR / "01_homepage.html"
    if not home.exists():
        return {"status": "online", "system": "SecuScribe Content Transformation API"}
    return FileResponse(home)


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
