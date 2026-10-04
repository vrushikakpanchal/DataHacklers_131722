import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base

def gen_uuid():
    return str(uuid.uuid4())

class Review(Base):
    __tablename__ = "reviews"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    output_id = Column(String(64), ForeignKey("outputs.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(64), default="awaiting_review")  # awaiting_review, changes_requested, approved
    decision_notes = Column(Text, default="")
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    decided_at = Column(DateTime, nullable=True)

    output = relationship("Output", back_populates="reviews")
    reviewer = relationship("User")
    comments = relationship("ReviewComment", back_populates="review", cascade="all, delete-orphan")

class ReviewComment(Base):
    __tablename__ = "review_comments"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    output_id = Column(String(64), ForeignKey("outputs.id", ondelete="CASCADE"), nullable=False)
    review_id = Column(String(64), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=True)
    author_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    comment = Column(Text, nullable=False)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    review = relationship("Review", back_populates="comments")
    author = relationship("User")
