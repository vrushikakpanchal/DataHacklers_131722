import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base

def gen_uuid():
    return str(uuid.uuid4())

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    actor_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(64), nullable=False)  # SOURCE_UPLOADED, SOURCE_PARSED, ANALYSIS_COMPLETED, GENERATION_STARTED, GENERATION_COMPLETED, OUTPUT_EDITED, VERSION_CREATED, SUBMITTED_FOR_REVIEW, REVIEW_COMMENT_ADDED, CHANGES_REQUESTED, RESUBMITTED, APPROVED, EXPORT_CREATED, ASSIGNMENT_CHANGED
    target_type = Column(String(64), default="transformation")
    target_id = Column(String(64), nullable=True)
    transformation_id = Column(String(64), ForeignKey("transformations.id", ondelete="CASCADE"), nullable=True)
    team_id = Column(String(64), nullable=True)
    
    # Human-readable summary and structured details
    summary = Column(Text, nullable=False)
    details = Column(JSON, default=dict)
    
    # Cryptographic SHA-256 hash for document content tracking & reference
    content_hash = Column(String(64), nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    actor = relationship("User", back_populates="audit_events")
    transformation = relationship("Transformation", back_populates="audit_events")
