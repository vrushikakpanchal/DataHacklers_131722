from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class InvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: Literal["admin", "reviewer", "operator", "viewer"] = "operator"
    team_id: Optional[str] = None


class InvitationResponse(BaseModel):
    id: str
    email: str
    role: str
    team_id: Optional[str] = None
    status: str
    expires_at: datetime
    delivery_status: str
    invite_url: Optional[str] = None


class InvitationAccept(BaseModel):
    token: str = Field(min_length=20)
    name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=12, max_length=256)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class PasswordResetRequestResponse(BaseModel):
    accepted: bool = True
    delivery_status: str = "email"
    reset_url: Optional[str] = None


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20)
    password: str = Field(min_length=12, max_length=256)
