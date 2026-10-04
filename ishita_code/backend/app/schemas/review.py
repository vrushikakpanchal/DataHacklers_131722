from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from app.schemas.user import UserResponse

class ReviewCommentCreate(BaseModel):
    comment: str

class ReviewCommentResponse(BaseModel):
    id: str
    output_id: str
    review_id: Optional[str] = None
    author_id: str
    author: Optional[UserResponse] = None
    comment: str
    resolved: bool = False
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ChangeRequestPayload(BaseModel):
    comment: str

class ReviewResponse(BaseModel):
    id: str
    output_id: str
    reviewer_id: Optional[str] = None
    reviewer: Optional[UserResponse] = None
    status: str
    decision_notes: Optional[str] = ""
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    comments: List[ReviewCommentResponse] = []

    model_config = ConfigDict(from_attributes=True)
