import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base

def gen_uuid():
    return str(uuid.uuid4())

class AdvisoryTemplate(Base):
    """
    Configurable presentation template for Security Advisories.
    Enables organizations and admins to customize section order, field labels,
    branding, disclaimers, and TLP levels while keeping canonical security facts independent.
    """
    __tablename__ = "advisory_templates"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    org_id = Column(String(64), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    is_default = Column(Boolean, default=False, nullable=False)
    
    # Structural configuration
    required_sections = Column(JSON, default=list)
    optional_sections = Column(JSON, default=list)
    section_order = Column(JSON, default=list)
    
    # Presentation customization
    field_labels = Column(JSON, default=dict)
    branding = Column(JSON, default=dict)  # {"header": "...", "logo_text": "...", "badge_style": "..."}
    required_reference_links = Column(JSON, default=list)
    disclaimers = Column(Text, default="")
    classification_tlp = Column(String(32), default="TLP:CLEAR")
    custom_fields = Column(JSON, default=list)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="advisory_templates")
