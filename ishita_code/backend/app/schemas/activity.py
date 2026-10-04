from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from app.schemas.user import UserResponse

class AuditEventResponse(BaseModel):
    id: str
    actor_id: Optional[str] = None
    actor: Optional[UserResponse] = None
    action: str
    target_type: str = "transformation"
    target_id: Optional[str] = None
    transformation_id: Optional[str] = None
    team_id: Optional[str] = None
    summary: str
    details: Dict[str, Any] = {}
    content_hash: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class TraceabilityRecord(BaseModel):
    id: str
    transformation_id: str
    code: str
    title: str
    source_hash: str
    output_hash: str
    operator_name: str
    reviewer_name: Optional[str] = None
    status: str
    updated_at: str
    steps: list = []
