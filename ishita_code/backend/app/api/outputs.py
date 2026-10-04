from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.models.transformation import Transformation
from app.models.source import SourceDocument, LockedFact
from app.models.output import Output, OutputVersion
from app.models.audit import AuditEvent
from app.schemas.output import (
    OutputResponse,
    OutputUpdateRequest,
    OutputVersionResponse,
    SecurityAdvisorySchema
)
from app.modules.advisory.generator import advisory_generator
from app.modules.advisory.validator import AdvisoryValidator
from app.modules.advisory.pdf import AdvisoryPdfGenerator
from app.api.deps import get_current_user, require_operator
from app.api.resources import get_output_for_user, get_transformation_for_user, require_transformation_editor
from app.core.hashing import canonical_sha256

router = APIRouter(tags=["outputs"])

def compute_hash(data: Any) -> str:
    return canonical_sha256(data)

@router.post("/transformations/{transformation_id}/generate", response_model=OutputResponse)
async def generate_security_advisory(
    transformation_id: str,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db)
):
    transformation = get_transformation_for_user(db, transformation_id, current_user)
    require_transformation_editor(transformation, current_user)

    source_doc = db.query(SourceDocument).filter(SourceDocument.transformation_id == transformation.id).first()
    if not source_doc:
        raise HTTPException(status_code=400, detail="No source document found. Please upload or paste a report first.")

    locked_fact = db.query(LockedFact).filter(LockedFact.transformation_id == transformation.id).first()
    if not locked_fact:
        raise HTTPException(status_code=400, detail="No extracted locked facts found for this transformation.")

    # Update transformation status to processing
    transformation.status = "processing"
    db.commit()

    try:
        advisory, validation_report = await advisory_generator.generate_advisory(
            source_text=source_doc.sanitized_text,
            locked_fact=locked_fact,
            config=transformation.config or {}
        )
    except RuntimeError as e:
        transformation.status = "draft"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        transformation.status = "draft"
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Generation failed: {str(e)}"
        )

    # Format advisory content dict with compatibility keys for frontend
    advisory_dict = advisory.model_dump()
    advisory_dict["cve"] = advisory.cve_ids[0] if advisory.cve_ids else ""
    advisory_dict["affectedProduct"] = advisory.affected_products[0] if advisory.affected_products else ""
    advisory_dict["affectedProducts"] = advisory.affected_products
    advisory_dict["affectedVersions"] = advisory.affected_versions[0] if advisory.affected_versions else ""
    advisory_dict["technicalDetails"] = advisory.technical_details

    content_hash = compute_hash(advisory_dict)

    # Upsert Output
    output = db.query(Output).filter(
        Output.transformation_id == transformation.id,
        Output.output_type == "SECURITY_ADVISORY"
    ).first()

    if not output:
        output = Output(
            transformation_id=transformation.id,
            output_type="SECURITY_ADVISORY",
            status="generated",
            version=1,
            content=advisory_dict,
            metadata_json={
                "model": advisory_generator.client.model,
                "generator": "remote_ollama",
                "rag_retrieval": validation_report.get("rag_retrieval", []),
            },
            validation_status=validation_report["status"],
            validation_details=validation_report,
            review_status="not_submitted",
            created_by=current_user.id,
            updated_by=current_user.id
        )
        db.add(output)
        db.flush()
    else:
        output.version += 1
        output.content = advisory_dict
        output.status = "generated"
        output.validation_status = validation_report["status"]
        output.validation_details = validation_report
        output.metadata_json = {
            **(output.metadata_json or {}),
            "model": advisory_generator.client.model,
            "generator": "remote_ollama",
            "rag_retrieval": validation_report.get("rag_retrieval", []),
        }
        output.updated_by = current_user.id

    # Create new OutputVersion
    version_rec = OutputVersion(
        output_id=output.id,
        version_num=output.version,
        content=advisory_dict,
        author_id=current_user.id,
        changelog=f"Version {output.version}: AI generated advisory",
        content_hash=content_hash
    )
    db.add(version_rec)

    transformation.status = "draft"

    # Audit event
    db.add(AuditEvent(
        actor_id=current_user.id,
        action="GENERATION_COMPLETED",
        target_type="output",
        target_id=output.id,
        transformation_id=transformation.id,
        team_id=transformation.team_id,
        summary=f"{current_user.name} generated Security Advisory ({output.validation_status})",
        details={
            "output_id": output.id,
            "version": output.version,
            "validation_findings": validation_report.get("findings", [])
        },
        content_hash=content_hash
    ))

    db.commit()
    db.refresh(output)
    return output

@router.get("/outputs/{output_id}", response_model=OutputResponse)
def get_output(
    output_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_output_for_user(db, output_id, current_user)

@router.patch("/outputs/{output_id}", response_model=OutputResponse)
def update_output(
    output_id: str,
    payload: OutputUpdateRequest,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db)
):
    output = get_output_for_user(db, output_id, current_user)
    transformation = get_transformation_for_user(db, output.transformation_id, current_user)
    require_transformation_editor(transformation, current_user)
    locked_fact = db.query(LockedFact).filter(LockedFact.transformation_id == output.transformation_id).first()

    # Bump version and save
    output.version += 1
    output.content = payload.content
    output.updated_by = current_user.id

    # Cross-validate edited content against locked facts
    if locked_fact:
        try:
            adv_schema = SecurityAdvisorySchema(
                title=payload.content.get("title", ""),
                severity=payload.content.get("severity", "UNKNOWN"),
                cve_ids=payload.content.get("cve_ids") or ([payload.content.get("cve")] if payload.content.get("cve") else []),
                cvss=payload.content.get("cvss", ""),
                affected_products=payload.content.get("affected_products") or ([payload.content.get("affectedProduct")] if payload.content.get("affectedProduct") else []),
                affected_versions=payload.content.get("affected_versions") or ([payload.content.get("affectedVersions")] if payload.content.get("affectedVersions") else []),
                summary=payload.content.get("summary", ""),
                technical_details=payload.content.get("technicalDetails") or payload.content.get("technical_details", ""),
                impact=payload.content.get("impact", ""),
                indicators=payload.content.get("indicators", []),
                mitigation=payload.content.get("mitigation", ""),
                recommendations=payload.content.get("recommendations", []),
                references=payload.content.get("references", [])
            )
            report = AdvisoryValidator.validate_against_locked_facts(adv_schema, locked_fact)
            output.validation_status = report["status"]
            output.validation_details = report
        except Exception:
            pass

    content_hash = compute_hash(output.content)

    # Add OutputVersion record
    version_rec = OutputVersion(
        output_id=output.id,
        version_num=output.version,
        content=output.content,
        author_id=current_user.id,
        changelog=payload.changelog or f"Version {output.version}: Operator edited advisory",
        content_hash=content_hash
    )
    db.add(version_rec)

    # Audit event
    db.add(AuditEvent(
        actor_id=current_user.id,
        action="OUTPUT_EDITED",
        target_type="output",
        target_id=output.id,
        transformation_id=output.transformation_id,
        team_id=transformation.team_id if transformation else None,
        summary=f"{current_user.name} edited Security Advisory (saved as v{output.version})",
        details={"version": output.version, "changelog": payload.changelog},
        content_hash=content_hash
    ))

    db.commit()
    db.refresh(output)
    return output

@router.get("/outputs/{output_id}/versions", response_model=List[OutputVersionResponse])
def list_output_versions(
    output_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    get_output_for_user(db, output_id, current_user)
    versions = db.query(OutputVersion).filter(OutputVersion.output_id == output_id).order_by(OutputVersion.version_num.desc()).all()
    results = []
    for v in versions:
        vr = OutputVersionResponse.model_validate(v)
        if v.author:
            vr.author_name = v.author.name
        results.append(vr)
    return results

@router.get("/outputs/{output_id}/versions/{version_num}", response_model=OutputVersionResponse)
def get_output_version(
    output_id: str,
    version_num: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    get_output_for_user(db, output_id, current_user)
    v = db.query(OutputVersion).filter(OutputVersion.output_id == output_id, OutputVersion.version_num == version_num).first()
    if not v:
        raise HTTPException(status_code=404, detail=f"Version {version_num} not found")
    vr = OutputVersionResponse.model_validate(v)
    if v.author:
        vr.author_name = v.author.name
    return vr

@router.get("/outputs/{output_id}/pdf")
def export_output_pdf(
    output_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    output = get_output_for_user(db, output_id, current_user)
    
    transformation = db.query(Transformation).filter(Transformation.id == output.transformation_id).first()
    metadata = {
        "advisory_id": output.content.get("advisory_id") or (transformation.code if transformation else output.id),
        "created_at": output.created_at.strftime("%Y-%m-%d %H:%M UTC") if output.created_at else "",
        "version": output.version,
        "classification": output.content.get("classification") or "TLP:AMBER"
    }

    try:
        pdf_bytes = AdvisoryPdfGenerator.generate_pdf(output.content, metadata)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    filename = f"Advisory_{metadata['advisory_id']}_v{output.version}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

@router.get("/outputs/{output_id}/versions/{version_num}/pdf")
def export_version_pdf(
    output_id: str,
    version_num: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    output = get_output_for_user(db, output_id, current_user)

    version_rec = db.query(OutputVersion).filter(
        OutputVersion.output_id == output_id,
        OutputVersion.version_num == version_num
    ).first()
    if not version_rec:
        raise HTTPException(status_code=404, detail=f"Version {version_num} not found")

    transformation = db.query(Transformation).filter(Transformation.id == output.transformation_id).first()
    metadata = {
        "advisory_id": version_rec.content.get("advisory_id") or (transformation.code if transformation else output.id),
        "created_at": version_rec.created_at.strftime("%Y-%m-%d %H:%M UTC") if version_rec.created_at else "",
        "version": version_rec.version_num,
        "classification": version_rec.content.get("classification") or "TLP:AMBER"
    }

    try:
        pdf_bytes = AdvisoryPdfGenerator.generate_pdf(version_rec.content, metadata)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    filename = f"Advisory_{metadata['advisory_id']}_v{version_rec.version_num}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )
