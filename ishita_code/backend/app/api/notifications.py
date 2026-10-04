from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("", response_model=List[NotificationResponse])
def list_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    items = db.query(Notification).filter(Notification.user_id == current_user.id).order_by(Notification.created_at.desc()).limit(50).all()
    return items

@router.patch("/{id}/read", response_model=NotificationResponse)
def mark_notification_read(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    item = db.query(Notification).filter(Notification.id == id, Notification.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")
    item.read = True
    db.commit()
    db.refresh(item)
    return item

@router.post("/mark-all-read")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db.query(Notification).filter(Notification.user_id == current_user.id, Notification.read == False).update({"read": True})
    db.commit()
    return {"message": "All notifications marked as read."}
