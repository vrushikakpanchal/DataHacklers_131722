from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class OrganizationResponse(BaseModel):
    id: str
    name: str
    domain: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class TeamBase(BaseModel):
    name: str
    description: Optional[str] = ""

class TeamCreate(TeamBase):
    pass

class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class TeamMembershipChange(BaseModel):
    user_id: str

class TeamResponse(TeamBase):
    id: str
    org_id: str
    member_ids: List[str] = []
    active_work: int = 0
    pending_reviews: int = 0
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
