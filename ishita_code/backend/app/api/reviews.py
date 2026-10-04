from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.models.user import User
from app.models.transformation import Transformation
from app.models.output import Output
from app.models.review import Review, ReviewComment
from app.models.notification import Notification
from app.models.audit import AuditEvent
from app.schemas.review import (
    ReviewResponse,
    ReviewCommentCreate,
    ReviewCommentResponse,
    ChangeRequestPayload
)
from app.schemas.transformation import TransformationResponse
from app.api.deps import get_current_user, require_reviewer, require_operator
from app.api.resources import (
    get_output_for_user,
    get_transformation_for_user,
    require_assigned_reviewer,
    require_transformation_editor,
)

router = APIRouter(tags=["reviews"])

@router.post("/outputs/{output_id}/submit-review")
def submit_for_review(
    output_id: str,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db)
):
    output = get_output_for_user(db, output_id, current_user)
    transformation = get_transformation_for_user(db, output.transformation_id, current_user)
    require_transformation_editor(transformation, current_user)
    if not transformation.reviewer_id:
        raise HTTPException(status_code=422, detail="Assign an active reviewer before submitting this output for review")

    output.review_status = "awaiting_review"
    output.status = "awaiting_review"
    transformation.status = "awaiting_review"
    transformation.updated_at = datetime.now(timezone.utc)

    # Find or create review record
    review = db.query(Review).filter(Review.output_id == output.id).first()
    if not review:
        review = Review(
            output_id=output.id,
            reviewer_id=transformation.reviewer_id,
            status="awaiting_review",
            submitted_at=datetime.now(timezone.utc)
        )
        db.add(review)
    else:
        review.status = "awaiting_review"
        review.submitted_at = datetime.now(timezone.utc)
        review.reviewer_id = transformation.reviewer_id

    # Notify reviewer if assigned
    if transformation.reviewer_id:
        db.add(Notification(
            user_id=transformation.reviewer_id,
            title="Review Requested",
            message=f"{current_user.name} submitted Security Advisory {transformation.code} for review.",
            link=f"/review/{transformation.id}",
            type="review_requested"
        ))

    db.add(AuditEvent(
        actor_id=current_user.id,
        action="SUBMITTED_FOR_REVIEW",
        target_type="output",
        target_id=output.id,
        transformation_id=transformation.id,
        team_id=transformation.team_id,
        summary=f"{current_user.name} submitted Security Advisory {transformation.code} (v{output.version}) for review",
        details={"version": output.version, "reviewer_id": transformation.reviewer_id}
    ))

    db.commit()
    return {"message": "Submitted for review successfully.", "status": "awaiting_review"}

@router.get("/reviews")
def list_review_queue(
    filter_type: str = Query("my", enum=["my", "team", "completed"]),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Transformation).filter(Transformation.org_id == current_user.org_id)
    
    if filter_type == "my":
        query = query.filter(
            Transformation.reviewer_id == current_user.id,
            Transformation.status == "awaiting_review"
        )
    elif filter_type == "team":
        # Any items awaiting review in user's teams
        team_ids = [m.team_id for m in current_user.team_memberships]
        query = query.filter(
            Transformation.team_id.in_(team_ids),
            Transformation.status == "awaiting_review"
        )
    elif filter_type == "completed":
        query = query.filter(Transformation.status.in_(["approved", "changes_requested"]))

    transformations = query.order_by(Transformation.updated_at.desc()).all()
    return [TransformationResponse.model_validate(t) for t in transformations]

@router.post("/outputs/{output_id}/comments", response_model=ReviewCommentResponse)
def add_review_comment(
    output_id: str,
    payload: ReviewCommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    output = get_output_for_user(db, output_id, current_user)
    transformation = get_transformation_for_user(db, output.transformation_id, current_user)
    require_assigned_reviewer(transformation, current_user)
    review = db.query(Review).filter(Review.output_id == output.id).first()

    comment_rec = ReviewComment(
        output_id=output.id,
        review_id=review.id if review else None,
        author_id=current_user.id,
        comment=payload.comment
    )
    db.add(comment_rec)

    db.add(AuditEvent(
        actor_id=current_user.id,
        action="REVIEW_COMMENT_ADDED",
        target_type="output",
        target_id=output.id,
        transformation_id=output.transformation_id,
        team_id=transformation.team_id if transformation else None,
        summary=f"{current_user.name} added a review comment to {transformation.code if transformation else output.id}",
        details={"comment_snippet": payload.comment[:120]}
    ))

    db.commit()
    db.refresh(comment_rec)
    
    res = ReviewCommentResponse.model_validate(comment_rec)
    res.author = current_user
    return res

@router.get("/outputs/{output_id}/comments", response_model=List[ReviewCommentResponse])
def list_review_comments(
    output_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    get_output_for_user(db, output_id, current_user)
    comments = db.query(ReviewComment).filter(ReviewComment.output_id == output_id).order_by(ReviewComment.created_at.asc()).all()
    res = []
    for c in comments:
        cr = ReviewCommentResponse.model_validate(c)
        cr.author = c.author
        res.append(cr)
    return res

@router.post("/outputs/{output_id}/request-changes")
def request_changes(
    output_id: str,
    payload: ChangeRequestPayload,
    current_user: User = Depends(require_reviewer),
    db: Session = Depends(get_db)
):
    output = get_output_for_user(db, output_id, current_user)
    transformation = get_transformation_for_user(db, output.transformation_id, current_user)
    require_assigned_reviewer(transformation, current_user)

    now = datetime.now(timezone.utc)
    output.review_status = "changes_requested"
    output.status = "changes_requested"
    transformation.status = "changes_requested"
    transformation.updated_at = now

    review = db.query(Review).filter(Review.output_id == output.id).first()
    if review:
        review.status = "changes_requested"
        review.decided_at = now
        review.decision_notes = payload.comment

    # Save as formal review comment
    comment_rec = ReviewComment(
        output_id=output.id,
        review_id=review.id if review else None,
        author_id=current_user.id,
        comment=f"[REQUESTED CHANGES]: {payload.comment}"
    )
    db.add(comment_rec)

    # Notify transformation owner (Operator)
    db.add(Notification(
        user_id=transformation.owner_id,
        title="Changes Requested",
        message=f"{current_user.name} requested changes on Security Advisory {transformation.code}: '{payload.comment[:100]}'",
        link=f"/transformations/{transformation.id}",
        type="changes_requested"
    ))

    db.add(AuditEvent(
        actor_id=current_user.id,
        action="CHANGES_REQUESTED",
        target_type="output",
        target_id=output.id,
        transformation_id=transformation.id,
        team_id=transformation.team_id,
        summary=f"{current_user.name} requested changes on Security Advisory {transformation.code}",
        details={"reason": payload.comment}
    ))

    db.commit()
    return {"message": "Changes requested recorded.", "status": "changes_requested"}

@router.post("/outputs/{output_id}/resubmit")
def resubmit_for_review(
    output_id: str,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db)
):
    output = get_output_for_user(db, output_id, current_user)
    transformation = get_transformation_for_user(db, output.transformation_id, current_user)
    require_transformation_editor(transformation, current_user)

    now = datetime.now(timezone.utc)
    output.review_status = "awaiting_review"
    output.status = "awaiting_review"
    transformation.status = "awaiting_review"
    transformation.updated_at = now

    review = db.query(Review).filter(Review.output_id == output.id).first()
    if review:
        review.status = "awaiting_review"
        review.submitted_at = now

    if transformation.reviewer_id:
        db.add(Notification(
            user_id=transformation.reviewer_id,
            title="Advisory Resubmitted",
            message=f"{current_user.name} updated and resubmitted {transformation.code} for your review.",
            link=f"/review/{transformation.id}",
            type="resubmitted"
        ))

    db.add(AuditEvent(
        actor_id=current_user.id,
        action="RESUBMITTED",
        target_type="output",
        target_id=output.id,
        transformation_id=transformation.id,
        team_id=transformation.team_id,
        summary=f"{current_user.name} resubmitted Security Advisory {transformation.code} (v{output.version}) for review",
        details={"version": output.version}
    ))

    db.commit()
    return {"message": "Resubmitted for review.", "status": "awaiting_review"}

@router.post("/outputs/{output_id}/approve")
def approve_output(
    output_id: str,
    current_user: User = Depends(require_reviewer),
    db: Session = Depends(get_db)
):
    output = get_output_for_user(db, output_id, current_user)
    transformation = get_transformation_for_user(db, output.transformation_id, current_user)
    require_assigned_reviewer(transformation, current_user)

    now = datetime.now(timezone.utc)
    output.review_status = "approved"
    output.status = "approved"
    transformation.status = "approved"
    transformation.approved_by = current_user.id
    transformation.approved_at = now
    transformation.updated_at = now

    review = db.query(Review).filter(Review.output_id == output.id).first()
    if review:
        review.status = "approved"
        review.decided_at = now

    # Notify transformation owner
    db.add(Notification(
        user_id=transformation.owner_id,
        title="Security Advisory Approved",
        message=f"Security Advisory {transformation.code} was approved by {current_user.name}.",
        link=f"/transformations/{transformation.id}",
        type="approved"
    ))

    db.add(AuditEvent(
        actor_id=current_user.id,
        action="APPROVED",
        target_type="output",
        target_id=output.id,
        transformation_id=transformation.id,
        team_id=transformation.team_id,
        summary=f"{current_user.name} approved Security Advisory {transformation.code} (v{output.version})",
        details={
            "version": output.version,
            "approved_by": current_user.id,
            "approved_at": now.isoformat(),
            "distribution_status": "authorized_internal"
        }
    ))

    db.commit()
    return {"message": "Output approved successfully. Content is now authorized internally.", "status": "approved"}
