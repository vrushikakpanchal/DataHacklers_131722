from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.models.user import User
from app.models.integration import Integration
from app.api.deps import get_current_user, require_admin

router = APIRouter(prefix="/integrations", tags=["integrations"])

class IntegrationResponse(BaseModel):
    id: str
    org_id: str
    name: str
    category: str
    status: str
    account: str | None = None
    permissions: list = []

    class Config:
        from_attributes = True

@router.get("", response_model=List[IntegrationResponse])
def list_integrations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    items = db.query(Integration).filter(Integration.org_id == current_user.org_id).all()
    return items

@router.post("/{id}/connect", response_model=IntegrationResponse)
def connect_integration(
    id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = db.query(Integration).filter(Integration.id == id, Integration.org_id == current_user.org_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    item.status = "connected"
    item.account = f"org-service-{item.id.replace('int-', '')}"
    db.commit()
    db.refresh(item)
    return item
