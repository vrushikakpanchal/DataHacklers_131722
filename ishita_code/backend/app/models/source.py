import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Integer
from sqlalchemy.orm import relationship
from app.core.database import Base

def gen_uuid():
    return str(uuid.uuid4())

class SourceDocument(Base):
    __tablename__ = "source_documents"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    transformation_id = Column(String(64), ForeignKey("transformations.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(32), nullable=False)  # TXT, PDF, DOCX, Pasted text
    size_label = Column(String(64), default="")
    raw_text = Column(Text, nullable=False)
    sanitized_text = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)  # SHA-256 hash
    status = Column(String(32), default="parsed")  # uploaded, parsed, failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    transformation = relationship("Transformation", back_populates="source_documents")

class LockedFact(Base):
    __tablename__ = "locked_facts"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    transformation_id = Column(String(64), ForeignKey("transformations.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Strongly structured identifiers (extracted with regex)
    cve_ids = Column(JSON, default=list)  # ["CVE-2026-12345"]
    cvss_scores = Column(JSON, default=list)  # ["8.8"]
    severity = Column(String(32), default="")  # CRITICAL, HIGH, MEDIUM, LOW
    ips = Column(JSON, default=list)  # ["192.0.2.10"]
    hashes = Column(JSON, default=list)  # ["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"]
    urls = Column(JSON, default=list)  # ["https://example.com/exploit"]
    domains = Column(JSON, default=list)

    # Candidate extractions preserving uncertainty
    candidate_products = Column(JSON, default=list)  # [{"name": "...", "confidence": "candidate"}]
    candidate_versions = Column(JSON, default=list)  # [{"version": "...", "confidence": "candidate"}]
    
    # DLP / Sensitivity findings
    dlp_findings = Column(JSON, default=list)  # [{"type": "personal_email", "value": "...", "classification": "sensitive"}]

    extracted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    transformation = relationship("Transformation", back_populates="locked_facts")
