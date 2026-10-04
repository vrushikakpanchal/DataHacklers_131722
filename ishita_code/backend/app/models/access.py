import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String

from app.core.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    org_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    role = Column(String(64), nullable=False, default="operator")
    team_id = Column(String(64), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    invited_by = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    status = Column(String(32), nullable=False, default="pending")  # pending, accepted, revoked, expired
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


def hash_one_time_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
