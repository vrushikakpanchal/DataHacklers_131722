from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.models.transformation import Transformation
from app.models.audit import AuditEvent
from app.models.output import Output
from app.schemas.activity import AuditEventResponse, TraceabilityRecord
from app.schemas.user import UserResponse
from app.api.deps import get_current_user

router = APIRouter(tags=["activity & traceability"])

@router.get("/activity", response_model=List[AuditEventResponse])
def get_activity_log(
    transformation_id: Optional[str] = None,
    limit: int = Query(50, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Audit history is tenant data. Events without an associated transformation
    # are intentionally not exposed until they carry an organization reference.
    query = (
        db.query(AuditEvent)
        .join(Transformation, AuditEvent.transformation_id == Transformation.id)
        .filter(Transformation.org_id == current_user.org_id)
    )
    if transformation_id:
        query = query.filter(AuditEvent.transformation_id == transformation_id)
    
    events = query.order_by(AuditEvent.created_at.desc()).limit(limit).all()
    results = []
    for ev in events:
        resp = AuditEventResponse.model_validate(ev)
        if ev.actor:
            resp.actor = UserResponse.model_validate(ev.actor)
        results.append(resp)
    return results

@router.get("/traceability", response_model=List[TraceabilityRecord])
def get_traceability_records(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns database-backed audit & traceability records.
    Cryptographic SHA-256 hashes are used for document content reference and integrity tracking.
    """
    transformations = db.query(Transformation).filter(
        Transformation.org_id == current_user.org_id
    ).order_by(Transformation.updated_at.desc()).all()

    records = []
    for tr in transformations:
        # Get source hash
        source_hash = tr.source_documents[0].content_hash if tr.source_documents else "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        
        # Get latest output hash
        adv_output = next((o for o in tr.outputs if o.output_type == "SECURITY_ADVISORY"), None)
        output_hash = "N/A"
        if adv_output and adv_output.versions:
            output_hash = adv_output.versions[0].content_hash

        # Extract lifecycle steps from audit events
        audit_events = db.query(AuditEvent).filter(
            AuditEvent.transformation_id == tr.id
        ).order_by(AuditEvent.created_at.asc()).all()

        steps = [
            {
                "label": ev.action.replace("_", " ").title(),
                "at": ev.created_at.isoformat() if ev.created_at else "",
                "actor": ev.actor.name if ev.actor else "System",
                "summary": ev.summary
            }
            for ev in audit_events
        ]

        title = tr.source_documents[0].filename if tr.source_documents else tr.code
        records.append(TraceabilityRecord(
            id=f"trc-{tr.id}",
            transformation_id=tr.id,
            code=tr.code,
            title=title,
            source_hash=source_hash,
            output_hash=output_hash,
            operator_name=tr.owner.name if tr.owner else "Unknown",
            reviewer_name=tr.reviewer.name if tr.reviewer else None,
            status=tr.status,
            updated_at=tr.updated_at.isoformat() if tr.updated_at else "",
            steps=steps
        ))

    return records
