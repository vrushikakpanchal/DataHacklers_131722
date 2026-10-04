import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

def gen_uuid():
    return str(uuid.uuid4())

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    teams = relationship("Team", back_populates="organization", cascade="all, delete-orphan")
    transformations = relationship("Transformation", back_populates="organization", cascade="all, delete-orphan")
    advisory_templates = relationship("AdvisoryTemplate", back_populates="organization", cascade="all, delete-orphan")

class Team(Base):
    __tablename__ = "teams"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    org_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="teams")
    memberships = relationship("TeamMembership", back_populates="team", cascade="all, delete-orphan")
    transformations = relationship("Transformation", back_populates="team")

class TeamMembership(Base):
    __tablename__ = "team_memberships"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    team_id = Column(String(64), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    team = relationship("Team", back_populates="memberships")
    user = relationship("User", back_populates="team_memberships")
