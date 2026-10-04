"""Central tenant-aware resource lookups and workflow authorization."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.output import Output
from app.models.transformation import Transformation
from app.models.user import User


def get_transformation_for_user(db: Session, transformation_id: str, user: User) -> Transformation:
    transformation = (
        db.query(Transformation)
        .filter(Transformation.id == transformation_id, Transformation.org_id == user.org_id)
        .first()
    )
    if not transformation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transformation not found")
    return transformation


def get_output_for_user(db: Session, output_id: str, user: User) -> Output:
    output = (
        db.query(Output)
        .join(Transformation, Output.transformation_id == Transformation.id)
        .filter(Output.id == output_id, Transformation.org_id == user.org_id)
        .first()
    )
    if not output:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output not found")
    return output


def require_transformation_editor(transformation: Transformation, user: User) -> None:
    """Allow administrators or the workflow owner to mutate source/output state."""
    if user.role == "admin" or transformation.owner_id == user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the transformation owner or an administrator can modify this workflow.")


def require_assigned_reviewer(transformation: Transformation, user: User) -> None:
    if user.role == "admin" or (user.role == "reviewer" and transformation.reviewer_id == user.id):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned reviewer or an administrator can perform this review action.")
