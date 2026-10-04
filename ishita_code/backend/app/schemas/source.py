from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class CandidateEntity(BaseModel):
    value: str
    confidence: str = "candidate"  # "high", "candidate", "uncertain"
    context: Optional[str] = None

class DlpFinding(BaseModel):
    type: str  # personal_email, credential_pattern, internal_secret
    value: str
    classification: str  # sensitive, restricted
    line_number: Optional[int] = None

class LockedFactResponse(BaseModel):
    id: str
    transformation_id: str
    cve_ids: List[str] = []
    cvss_scores: List[str] = []
    severity: str = ""
    ips: List[str] = []
    hashes: List[str] = []
    urls: List[str] = []
    domains: List[str] = []
    candidate_products: List[Dict[str, Any]] = []
    candidate_versions: List[Dict[str, Any]] = []
    dlp_findings: List[Dict[str, Any]] = []
    extracted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class SourceDocumentResponse(BaseModel):
    id: str
    transformation_id: str
    filename: str
    file_type: str
    size_label: str
    status: str
    content_hash: str
    raw_text_preview: str = ""
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
