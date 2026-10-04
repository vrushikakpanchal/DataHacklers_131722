from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.models.user import User
from app.models.transformation import Transformation
from app.models.source import SourceDocument, LockedFact
from app.models.audit import AuditEvent
from app.schemas.source import SourceDocumentResponse, LockedFactResponse
from app.services.source_parser import SourceParser, compute_sha256
from app.modules.advisory.extractor import FactExtractor
from app.api.deps import get_current_user, require_operator
from app.api.resources import get_transformation_for_user, require_transformation_editor

router = APIRouter(tags=["sources"])

class PasteSourceRequest(BaseModel):
    title: Optional[str] = "Pasted Cybersecurity Report"
    filename: Optional[str] = "pasted_report.txt"
    text: str

def format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    else:
        return f"{num_bytes / (1024 * 1024):.1f} MB"

@router.post("/transformations/{transformation_id}/source/upload", response_model=SourceDocumentResponse)
async def upload_source_file(
    transformation_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db)
):
    transformation = get_transformation_for_user(db, transformation_id, current_user)
    require_transformation_editor(transformation, current_user)

    content_bytes = await file.read()
    try:
        raw_text, sanitized_text, content_hash = SourceParser.ingest_document(
            filename=file.filename or "unknown.txt",
            content_bytes=content_bytes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Save SourceDocument
    src_doc = SourceDocument(
        transformation_id=transformation.id,
        filename=file.filename or "uploaded_document",
        file_type=(file.filename.split(".")[-1].upper() if "." in file.filename else "TXT"),
        size_label=format_size(len(content_bytes)),
        raw_text=raw_text,
        sanitized_text=sanitized_text,
        content_hash=content_hash,
        status="parsed"
    )
    db.add(src_doc)

    # Run deterministic extraction
    facts = FactExtractor.extract_facts(sanitized_text)

    # Upsert LockedFact
    existing_fact = db.query(LockedFact).filter(LockedFact.transformation_id == transformation.id).first()
    if existing_fact:
        existing_fact.cve_ids = facts["cve_ids"]
        existing_fact.cvss_scores = facts["cvss_scores"]
        existing_fact.severity = facts["severity"]
        existing_fact.ips = facts["ips"]
        existing_fact.hashes = facts["hashes"]
        existing_fact.urls = facts["urls"]
        existing_fact.domains = facts["domains"]
        existing_fact.candidate_products = facts["candidate_products"]
        existing_fact.candidate_versions = facts["candidate_versions"]
        existing_fact.dlp_findings = facts["dlp_findings"]
    else:
        locked_fact = LockedFact(
            transformation_id=transformation.id,
            cve_ids=facts["cve_ids"],
            cvss_scores=facts["cvss_scores"],
            severity=facts["severity"],
            ips=facts["ips"],
            hashes=facts["hashes"],
            urls=facts["urls"],
            domains=facts["domains"],
            candidate_products=facts["candidate_products"],
            candidate_versions=facts["candidate_versions"],
            dlp_findings=facts["dlp_findings"]
        )
        db.add(locked_fact)

    # Record database audit event
    db.add(AuditEvent(
        actor_id=current_user.id,
        action="SOURCE_UPLOADED",
        target_type="source_document",
        target_id=src_doc.id,
        transformation_id=transformation.id,
        team_id=transformation.team_id,
        summary=f"{current_user.name} uploaded source file '{src_doc.filename}' ({src_doc.size_label})",
        details={
            "filename": src_doc.filename,
            "cves_found": len(facts["cve_ids"]),
            "ips_found": len(facts["ips"]),
            "hashes_found": len(facts["hashes"]),
            "dlp_flagged": len(facts["dlp_findings"])
        },
        content_hash=content_hash
    ))

    db.commit()
    db.refresh(src_doc)
    return SourceDocumentResponse(
        id=src_doc.id,
        transformation_id=src_doc.transformation_id,
        filename=src_doc.filename,
        file_type=src_doc.file_type,
        size_label=src_doc.size_label,
        status=src_doc.status,
        content_hash=src_doc.content_hash,
        raw_text_preview=src_doc.sanitized_text[:500],
        created_at=src_doc.created_at
    )

@router.post("/transformations/{transformation_id}/source/paste", response_model=SourceDocumentResponse)
def paste_source_text(
    transformation_id: str,
    payload: PasteSourceRequest,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db)
):
    transformation = get_transformation_for_user(db, transformation_id, current_user)
    require_transformation_editor(transformation, current_user)

    content_bytes = payload.text.encode("utf-8")
    try:
        raw_text, sanitized_text, content_hash = SourceParser.ingest_document(
            filename=payload.filename or "pasted_text.txt",
            content_bytes=content_bytes,
            declared_type="PASTED"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    src_doc = SourceDocument(
        transformation_id=transformation.id,
        filename=payload.filename or "pasted_text.txt",
        file_type="Pasted text",
        size_label=format_size(len(content_bytes)),
        raw_text=raw_text,
        sanitized_text=sanitized_text,
        content_hash=content_hash,
        status="parsed"
    )
    db.add(src_doc)

    # Extract facts
    facts = FactExtractor.extract_facts(sanitized_text)

    # Upsert LockedFact
    existing_fact = db.query(LockedFact).filter(LockedFact.transformation_id == transformation.id).first()
    if existing_fact:
        existing_fact.cve_ids = facts["cve_ids"]
        existing_fact.cvss_scores = facts["cvss_scores"]
        existing_fact.severity = facts["severity"]
        existing_fact.ips = facts["ips"]
        existing_fact.hashes = facts["hashes"]
        existing_fact.urls = facts["urls"]
        existing_fact.domains = facts["domains"]
        existing_fact.candidate_products = facts["candidate_products"]
        existing_fact.candidate_versions = facts["candidate_versions"]
        existing_fact.dlp_findings = facts["dlp_findings"]
    else:
        locked_fact = LockedFact(
            transformation_id=transformation.id,
            cve_ids=facts["cve_ids"],
            cvss_scores=facts["cvss_scores"],
            severity=facts["severity"],
            ips=facts["ips"],
            hashes=facts["hashes"],
            urls=facts["urls"],
            domains=facts["domains"],
            candidate_products=facts["candidate_products"],
            candidate_versions=facts["candidate_versions"],
            dlp_findings=facts["dlp_findings"]
        )
        db.add(locked_fact)

    db.add(AuditEvent(
        actor_id=current_user.id,
        action="SOURCE_UPLOADED",
        target_type="source_document",
        target_id=src_doc.id,
        transformation_id=transformation.id,
        team_id=transformation.team_id,
        summary=f"{current_user.name} ingested pasted source content ({src_doc.size_label})",
        details={
            "cves_found": len(facts["cve_ids"]),
            "ips_found": len(facts["ips"]),
            "hashes_found": len(facts["hashes"]),
            "dlp_flagged": len(facts["dlp_findings"])
        },
        content_hash=content_hash
    ))

    db.commit()
    db.refresh(src_doc)
    return SourceDocumentResponse(
        id=src_doc.id,
        transformation_id=src_doc.transformation_id,
        filename=src_doc.filename,
        file_type=src_doc.file_type,
        size_label=src_doc.size_label,
        status=src_doc.status,
        content_hash=src_doc.content_hash,
        raw_text_preview=src_doc.sanitized_text[:500],
        created_at=src_doc.created_at
    )

@router.get("/transformations/{transformation_id}/facts", response_model=LockedFactResponse)
def get_locked_facts(
    transformation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    get_transformation_for_user(db, transformation_id, current_user)
    fact = db.query(LockedFact).filter(LockedFact.transformation_id == transformation_id).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Locked facts not found for this transformation")
    return LockedFactResponse.model_validate(fact)
