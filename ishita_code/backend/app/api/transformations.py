from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from pydantic import BaseModel
from app.core.database import get_db
from app.models.user import User
from app.models.transformation import Transformation
from app.models.audit import AuditEvent
from app.models.notification import Notification
from app.schemas.transformation import TransformationCreate, TransformationResponse
from app.api.deps import get_current_user, require_operator
from app.api.resources import get_transformation_for_user, require_transformation_editor

router = APIRouter(prefix="/transformations", tags=["transformations"])

class AssignReviewerRequest(BaseModel):
    reviewer_id: str

@router.get("", response_model=List[TransformationResponse])
def list_transformations(
    status: Optional[str] = None,
    team_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Transformation).filter(Transformation.org_id == current_user.org_id)
    if current_user.role == "viewer":
        query = query.filter(Transformation.status.in_(["approved", "published", "verified"]))
    if status:
        query = query.filter(Transformation.status == status)
    if team_id:
        query = query.filter(Transformation.team_id == team_id)
    if owner_id:
        query = query.filter(Transformation.owner_id == owner_id)
    if search:
        query = query.filter(
            or_(
                Transformation.code.ilike(f"%{search}%"),
                Transformation.status.ilike(f"%{search}%")
            )
        )
    items = query.order_by(Transformation.updated_at.desc()).all()
    return items

@router.post("", response_model=TransformationResponse)
def create_transformation(
    payload: TransformationCreate,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db)
):
    # Derive the next code from the highest existing TR-numeric suffix, not
    # from row count. Deletions/imports must never cause a duplicate code.
    existing_codes = db.query(Transformation.code).filter(Transformation.code.like("TR-%")).all()
    existing_numbers = []
    for (code,) in existing_codes:
        try:
            existing_numbers.append(int(code.removeprefix("TR-")))
        except (TypeError, ValueError):
            continue
    next_num = max(existing_numbers, default=1042) + 1
    code = f"TR-{next_num}"

    team_id = payload.team_id
    if team_id:
        from app.models.organization import Team
        team = db.query(Team).filter(Team.id == team_id, Team.org_id == current_user.org_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
    if not team_id:
        # Default to user's first team membership
        if current_user.team_memberships:
            team_id = current_user.team_memberships[0].team_id
        else:
            team_id = None

    transformation = Transformation(
        code=code,
        org_id=current_user.org_id,
        team_id=team_id,
        owner_id=current_user.id,
        status="draft",
        priority=payload.priority,
        config=payload.config.model_dump()
    )
    db.add(transformation)
    db.flush()

    db.add(AuditEvent(
        actor_id=current_user.id,
        action="TRANSFORMATION_CREATED",
        target_type="transformation",
        target_id=transformation.id,
        transformation_id=transformation.id,
        team_id=transformation.team_id,
        summary=f"{current_user.name} created transformation workflow {transformation.code}",
        details={"config": transformation.config}
    ))

    db.commit()
    db.refresh(transformation)
    return transformation

@router.get("/{id}", response_model=TransformationResponse)
def get_transformation(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_transformation_for_user(db, id, current_user)

@router.post("/{id}/assign-reviewer", response_model=TransformationResponse)
def assign_reviewer(
    id: str,
    payload: AssignReviewerRequest,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db)
):
    transformation = get_transformation_for_user(db, id, current_user)
    require_transformation_editor(transformation, current_user)

    reviewer = db.query(User).filter(User.id == payload.reviewer_id, User.org_id == current_user.org_id).first()
    if not reviewer or reviewer.role not in {"reviewer", "admin"} or reviewer.status != "active":
        raise HTTPException(status_code=422, detail="Reviewer must be an active reviewer or administrator in this organization")

    transformation.reviewer_id = reviewer.id

    # Create notification for the reviewer
    db.add(Notification(
        user_id=reviewer.id,
        title="Reviewer Assignment",
        message=f"{current_user.name} assigned you as lead reviewer on {transformation.code}.",
        link=f"/review/{transformation.id}",
        type="assigned"
    ))

    db.add(AuditEvent(
        actor_id=current_user.id,
        action="ASSIGNMENT_CHANGED",
        target_type="transformation",
        target_id=transformation.id,
        transformation_id=transformation.id,
        team_id=transformation.team_id,
        summary=f"{current_user.name} assigned reviewer {reviewer.name} to {transformation.code}",
        details={"reviewer_id": reviewer.id, "reviewer_name": reviewer.name}
    ))

    db.commit()
    db.refresh(transformation)
    return transformation
