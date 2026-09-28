import os
import sys
import shutil
import json
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.extractor import process_and_lock_document, extract_raw_text, lock_deterministic_parameters
from modules.llm_engine import extract_canonical_facts
from modules.generators import (
    generate_pdf_advisory,
    generate_presentation,
    generate_infographic_svg
)
from modules.social_engine import process_social_transformation
from modules.video_engine import process_video_transformation
from modules.verifier import verify_all_generated_outputs
from modules.security import compute_sha256, redact_sensitive_pii, log_transformation_audit_event

app = FastAPI(
    title="NTRO GenAI Content Transformation Engine",
    description="Automated multi-format content transformation API for NTRO (SIH PS 26154)",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join("data", "sample_inputs")
OUTPUT_DIR = os.path.join("data", "outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


class OperatorConfig(BaseModel):
    tone: str = "Executive / Formal"
    target_audience: str = "Leadership & Technical Teams"
    detail_level: str = "High"


@app.get("/")
def root():
    return {"status": "online", "system": "NTRO GenAI Platform API (SIH PS 26154)"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "model_engine": "qwen2.5:3b (Local Ollama)"}


@app.post("/api/v1/transform")
async def transform_document(
    file: UploadFile = File(...),
    tone: str = Form("Executive / Formal"),
    target_audience: str = Form("Leadership & Technical Teams"),
    detail_level: str = Form("High")
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
        canonical_facts = extract_canonical_facts(sanitized_text, locked_params, model_name="qwen2.5:3b")

        # 4. Artifact Generators
        # A. Baseline Document & Visual Generators (my_code)
        pdf_path = generate_pdf_advisory(canonical_facts)
        pptx_path = generate_presentation(canonical_facts)
        svg_path = generate_infographic_svg(canonical_facts)

        # B. Social Media Content Engine & Validator (pallavi_code)
        social_res = process_social_transformation(canonical_facts)
        social_posts = social_res.get("posts")
        social_validation = social_res.get("validation")

        # Save social output JSON
        social_json_path = os.path.join(OUTPUT_DIR, "social_posts.json")
        with open(social_json_path, "w", encoding="utf-8") as f:
            json.dump({"posts": social_posts, "validation": social_validation}, f, indent=2)

        # C. Video Script & Rendering Engine (tanvi_code)
        video_res = process_video_transformation(canonical_facts, output_dir=OUTPUT_DIR)
        video_package = video_res.get("blueprint")

        # Save video blueprint JSON
        video_json_path = os.path.join(OUTPUT_DIR, "video_package.json")
        with open(video_json_path, "w", encoding="utf-8") as f:
            json.dump(video_package, f, indent=2)

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
            "filename": file.filename,
            "sha256_hash": file_sha256,
            "redaction_stats": redaction_stats,
            "canonical_facts": canonical_facts,
            "social_media_validation": social_validation,
            "verification_audit": audit_report,
            "download_urls": {
                "advisory_pdf": f"/api/v1/outputs/{os.path.basename(pdf_path)}",
                "presentation_pptx": f"/api/v1/outputs/{os.path.basename(pptx_path)}",
                "infographic_svg": f"/api/v1/outputs/{os.path.basename(svg_path)}",
                "social_posts_json": "/api/v1/outputs/social_posts.json",
                "video_package_json": "/api/v1/outputs/video_package.json"
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/outputs/{filename}")
def get_output_file(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Requested artifact file not found.")
    return FileResponse(file_path)