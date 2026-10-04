import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from app.core.database import Base

def gen_uuid():
    return str(uuid.uuid4())

class Integration(Base):
    __tablename__ = "integrations"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    org_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(64), nullable=False)  # publishing, storage, cms
    status = Column(String(32), default="not_connected")  # connected, not_connected
    account = Column(String(255), nullable=True)
    last_used = Column(DateTime, nullable=True)
    permissions = Column(JSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
