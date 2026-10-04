import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, UniqueConstraint

from app.core.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class RagRecord(Base):
    """Persistent, source-scoped records used by the local threat-intelligence retriever."""

    __tablename__ = "rag_records"

    id = Column(String(160), primary_key=True)
    source_type = Column(String(32), nullable=False, index=True)  # NVD, CISA_KEV, CERT_IN
    document_type = Column(String(48), nullable=False, index=True)  # CVE, KEV, advisory, vulnerability_note
    source_name = Column(String(128), nullable=False)
    advisory_id = Column(String(64), nullable=True, index=True)

    cve_id = Column(String(32), nullable=True, index=True)
    cve_ids = Column(JSON, default=list, nullable=False)
    vendor = Column(String(255), nullable=True, index=True)
    product_terms = Column(Text, default="", nullable=False)

    title = Column(String(1000), nullable=False)
    summary = Column(Text, default="", nullable=False)
    technical_details = Column(Text, default="", nullable=False)
    mitigations = Column(JSON, default=list, nullable=False)
    affected_products = Column(JSON, default=list, nullable=False)
    affected_versions = Column(JSON, default=list, nullable=False)
    cwes = Column(JSON, default=list, nullable=False)
    references = Column(JSON, default=list, nullable=False)

    cvss_score = Column(String(64), nullable=True)
    cvss_vector = Column(String(512), nullable=True)
    severity = Column(String(32), nullable=True)
    published_date = Column(String(64), nullable=True)
    modified_date = Column(String(64), nullable=True)

    # A bounded, normalized corpus field for product/vendor/keyword matching. It is not sent wholesale to the LLM.
    search_text = Column(Text, default="", nullable=False)
    raw_metadata = Column(JSON, default=dict, nullable=False)
    ingested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class RagIngestion(Base):
    """Dataset-level idempotency and operational status for explicit RAG ingestions."""

    __tablename__ = "rag_ingestions"
    __table_args__ = (UniqueConstraint("source_type", "dataset_hash", name="uq_rag_ingestion_source_hash"),)

    id = Column(String(64), primary_key=True, default=gen_uuid)
    source_type = Column(String(32), nullable=False, index=True)
    dataset_hash = Column(String(64), nullable=False)
    filename = Column(String(512), nullable=False)
    status = Column(String(32), default="processing", nullable=False)
    record_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)
