import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base

def gen_uuid():
    return str(uuid.uuid4())

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    link = Column(String(255), default="")
    type = Column(String(64), default="info")  # review_requested, changes_requested, approved, assigned, etc.
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="notifications")
