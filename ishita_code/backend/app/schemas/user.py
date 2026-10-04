from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    name: str
    email: str
    role: str  # admin, reviewer, operator, viewer
    title: Optional[str] = ""
    initials: Optional[str] = ""
    status: Optional[str] = "active"

class UserCreate(UserBase):
    password: str
    org_id: str
    team_id: Optional[str] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    title: Optional[str] = None
    team_id: Optional[str] = None
    status: Optional[str] = None

class UserResponse(UserBase):
    id: str
    org_id: str
    team_id: Optional[str] = None
    last_active: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
