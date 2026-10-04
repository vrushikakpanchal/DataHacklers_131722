from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class IndicatorsOfCompromiseSchema(BaseModel):
    ips: List[str] = Field(default_factory=list, description="IP addresses")
    domains: List[str] = Field(default_factory=list, description="Domain names and hostnames")
    urls: List[str] = Field(default_factory=list, description="Malicious or reconnaissance URLs")
    hashes: List[str] = Field(default_factory=list, description="File hashes (SHA256, SHA1, MD5)")
    other: List[str] = Field(default_factory=list, description="Other indicators, registry keys, mutexes")

class SecurityAdvisorySchema(BaseModel):
    """
    Canonical standardized schema for Security Advisories.
    Captures all verified technical security facts independent of presentation templates.
    """
    title: str = Field(description="Advisory title clearly stating the vulnerability")
    advisory_id: Optional[str] = Field(default=None, description="Canonical or organizational advisory ID, e.g. ADV-2026-094")
    date: Optional[str] = Field(default=None, description="Advisory publication or revision date")
    severity: str = Field(default="UNKNOWN", description="CRITICAL, HIGH, MEDIUM, LOW, or UNKNOWN")
    cve_ids: List[str] = Field(default_factory=list, description="Extracted CVE identifiers from source")
    cvss: str = Field(default="", description="CVSS base score and vector if provided")
    affected_products: List[str] = Field(default_factory=list, description="Software or hardware products affected")
    affected_versions: List[str] = Field(default_factory=list, description="Specific version ranges affected")
    vulnerability_description: Optional[str] = Field(default=None, description="Detailed breakdown of vulnerability mechanics")
    summary: str = Field(description="Executive / high-level summary of the advisory")
    technical_details: str = Field(description="Deep technical analysis of vulnerability mechanics and attack vectors")
    impact: str = Field(description="Operational, confidentiality, and integrity impact")
    exploitation_status: Optional[str] = Field(default="UNKNOWN", description="Observed exploitation status in the wild or PoC availability")
    indicators: List[str] = Field(default_factory=list, description="Flat list of IOCs for backward compatibility")
    indicators_of_compromise: Optional[IndicatorsOfCompromiseSchema] = Field(default=None, description="Structured categorized IOCs")
    mitigation: str = Field(description="Immediate steps, patches, workarounds, or configuration changes")
    recommendations: List[str] = Field(default_factory=list, description="Specific tactical and strategic recommendations")
    references: List[str] = Field(default_factory=list, description="Authoritative external references, vendor bulletins, or RFCs")
    classification: str = Field(default="TLP:CLEAR", description="Traffic Light Protocol (TLP) or classification level")
    source_references: List[str] = Field(default_factory=list, description="Fact lineage or source document references")
    fact_lineage: List[Dict[str, Any]] = Field(default_factory=list, description="Lineage tracing facts back to source text spans")

class OutputUpdateRequest(BaseModel):
    content: Dict[str, Any]
    changelog: Optional[str] = "Edited by user"

class OutputVersionResponse(BaseModel):
    id: str
    output_id: str
    version_num: int
    content: Dict[str, Any]
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    changelog: str = ""
    content_hash: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class OutputResponse(BaseModel):
    id: str
    transformation_id: str
    output_type: str
    status: str
    version: int
    content: Dict[str, Any]
    metadata_json: Dict[str, Any] = {}
    validation_status: str
    validation_details: Dict[str, Any] = {}
    review_status: str
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class AdvisoryTemplateBase(BaseModel):
    name: str
    description: str = ""
    is_default: bool = False
    required_sections: List[str] = Field(default_factory=list)
    optional_sections: List[str] = Field(default_factory=list)
    section_order: List[str] = Field(default_factory=list)
    field_labels: Dict[str, str] = Field(default_factory=dict)
    branding: Dict[str, Any] = Field(default_factory=dict)
    required_reference_links: List[str] = Field(default_factory=list)
    disclaimers: str = ""
    classification_tlp: str = "TLP:CLEAR"
    custom_fields: List[Dict[str, Any]] = Field(default_factory=list)

class AdvisoryTemplateCreate(AdvisoryTemplateBase):
    org_id: Optional[str] = None

class AdvisoryTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None
    required_sections: Optional[List[str]] = None
    optional_sections: Optional[List[str]] = None
    section_order: Optional[List[str]] = None
    field_labels: Optional[Dict[str, str]] = None
    branding: Optional[Dict[str, Any]] = None
    required_reference_links: Optional[List[str]] = None
    disclaimers: Optional[str] = None
    classification_tlp: Optional[str] = None
    custom_fields: Optional[List[Dict[str, Any]]] = None

class AdvisoryTemplateResponse(AdvisoryTemplateBase):
    id: str
    org_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
