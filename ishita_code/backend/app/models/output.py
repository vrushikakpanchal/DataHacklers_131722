import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Integer
from sqlalchemy.orm import relationship
from app.core.database import Base

def gen_uuid():
    return str(uuid.uuid4())

class Output(Base):
    __tablename__ = "outputs"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    transformation_id = Column(String(64), ForeignKey("transformations.id", ondelete="CASCADE"), nullable=False)
    output_type = Column(String(64), nullable=False)  # SECURITY_ADVISORY, etc.
    status = Column(String(32), default="draft")  # draft, generated, awaiting_review, changes_requested, approved
    
    # Current version number
    version = Column(Integer, default=1, nullable=False)
    
    # Structured content payload
    content = Column(JSON, default=dict, nullable=False)
    metadata_json = Column(JSON, default=dict)
    
    validation_status = Column(String(64), default="pending")  # pending, valid, discrepancies_flagged, failed
    validation_details = Column(JSON, default=dict)
    
    review_status = Column(String(64), default="not_submitted")  # not_submitted, awaiting_review, changes_requested, approved
    
    created_by = Column(String(64), nullable=True)
    updated_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    transformation = relationship("Transformation", back_populates="outputs")
    versions = relationship("OutputVersion", back_populates="output", cascade="all, delete-orphan", order_by="OutputVersion.version_num.desc()")
    reviews = relationship("Review", back_populates="output", cascade="all, delete-orphan")

class OutputVersion(Base):
    __tablename__ = "output_versions"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    output_id = Column(String(64), ForeignKey("outputs.id", ondelete="CASCADE"), nullable=False)
    version_num = Column(Integer, nullable=False)
    content = Column(JSON, nullable=False)
    author_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    changelog = Column(String(500), default="")
    content_hash = Column(String(64), nullable=False)  # SHA-256 for reference & integrity check
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    output = relationship("Output", back_populates="versions")
    author = relationship("User")
