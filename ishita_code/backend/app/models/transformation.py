import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base

def gen_uuid():
    return str(uuid.uuid4())

class Transformation(Base):
    __tablename__ = "transformations"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    code = Column(String(32), nullable=False, unique=True, index=True)
    org_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    team_id = Column(String(64), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    owner_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # status: draft, processing, awaiting_review, changes_requested, approved, failed
    status = Column(String(64), default="draft", nullable=False, index=True)
    priority = Column(String(32), default="high", nullable=False)  # high, medium, low
    
    # config: audience, tone, language, detail, objective, style, outputTypes
    config = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String(64), nullable=True)

    organization = relationship("Organization", back_populates="transformations")
    team = relationship("Team", back_populates="transformations")
    owner = relationship("User", foreign_keys=[owner_id], back_populates="owned_transformations")
    reviewer = relationship("User", foreign_keys=[reviewer_id], back_populates="reviewed_transformations")
    
    source_documents = relationship("SourceDocument", back_populates="transformation", cascade="all, delete-orphan")
    locked_facts = relationship("LockedFact", back_populates="transformation", uselist=False, cascade="all, delete-orphan")
    outputs = relationship("Output", back_populates="transformation", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="transformation", cascade="all, delete-orphan")
