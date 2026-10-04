import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

def gen_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    org_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(64), nullable=False, default="operator")  # admin, reviewer, operator, viewer
    title = Column(String(255), default="")
    initials = Column(String(8), default="")
    status = Column(String(32), default="active")  # active, invited, deactivated
    last_active = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="users")
    team_memberships = relationship("TeamMembership", back_populates="user", cascade="all, delete-orphan")
    owned_transformations = relationship("Transformation", foreign_keys="Transformation.owner_id", back_populates="owner")
    reviewed_transformations = relationship("Transformation", foreign_keys="Transformation.reviewer_id", back_populates="reviewer")
    audit_events = relationship("AuditEvent", back_populates="actor")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
