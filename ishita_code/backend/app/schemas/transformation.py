from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.schemas.source import SourceDocumentResponse, LockedFactResponse
from app.schemas.output import OutputResponse
from app.schemas.user import UserResponse

class TransformationConfigSchema(BaseModel):
    audience: str = "Security Operations"
    tone: str = "Formal"
    language: str = "English"
    detail: int = 70
    objective: str = "Alert"
    style: str = "Technical"
    outputTypes: List[str] = ["advisory"]

class TransformationCreate(BaseModel):
    title: Optional[str] = None
    team_id: Optional[str] = None
    priority: str = "high"
    config: TransformationConfigSchema = TransformationConfigSchema()

class TransformationResponse(BaseModel):
    id: str
    code: str
    org_id: str
    team_id: Optional[str] = None
    owner_id: str
    reviewer_id: Optional[str] = None
    status: str
    priority: str
    config: Dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    
    owner: Optional[UserResponse] = None
    reviewer: Optional[UserResponse] = None
    source_documents: List[SourceDocumentResponse] = []
    locked_facts: Optional[LockedFactResponse] = None
    outputs: List[OutputResponse] = []

    model_config = ConfigDict(from_attributes=True)
