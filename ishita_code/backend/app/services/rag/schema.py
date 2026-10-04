from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ThreatIntelRecord(BaseModel):
    """
    Canonical threat intelligence and cybersecurity advisory knowledge record.
    Supports records from CISA KEV, NVD, CERT-In, OSV, or custom vendor bulletins.
    """
    id: str
    source_name: str  # e.g., "CISA-KEV", "NVD", "CERT-In", "MITRE-ATT&CK", "Vendor"
    source_type: str = "CUSTOM"  # NVD, CISA_KEV, CERT_IN, CUSTOM
    document_type: str = "record"  # CVE, KEV, advisory, vulnerability_note
    advisory_id: Optional[str] = None
    cve_id: Optional[str] = None
    cve_ids: List[str] = Field(default_factory=list)
    title: str
    summary: str
    technical_details: Optional[str] = ""
    mitigations: List[str] = Field(default_factory=list)
    affected_products: List[str] = Field(default_factory=list)
    affected_versions: List[str] = Field(default_factory=list)
    vendor: Optional[str] = None
    cvss_score: Optional[str] = None
    cvss_vector: Optional[str] = None
    severity: Optional[str] = None
    cwes: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    published_date: Optional[str] = None
    modified_date: Optional[str] = None
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def to_searchable_chunk(self) -> str:
        """
        Produce dense, high-signal text representation for retrieval.
        """
        parts = [
            f"SOURCE: {self.source_name}",
            f"TITLE: {self.title}"
        ]
        if self.cve_id:
            parts.append(f"CVE: {self.cve_id}")
        elif self.cve_ids:
            parts.append(f"CVES: {', '.join(self.cve_ids)}")
        if self.advisory_id:
            parts.append(f"ADVISORY ID: {self.advisory_id}")
        if self.vendor:
            parts.append(f"VENDOR: {self.vendor}")
        if self.severity:
            parts.append(f"SEVERITY: {self.severity}")
        if self.cvss_score:
            parts.append(f"CVSS: {self.cvss_score}{f' ({self.cvss_vector})' if self.cvss_vector else ''}")
        if self.cwes:
            parts.append(f"CWE: {', '.join(self.cwes)}")
        if self.affected_products:
            parts.append(f"AFFECTED PRODUCTS: {', '.join(self.affected_products)}")
        if self.affected_versions:
            parts.append(f"AFFECTED VERSIONS: {', '.join(self.affected_versions)}")
        if self.summary:
            parts.append(f"SUMMARY: {self.summary}")
        if self.technical_details:
            parts.append(f"DETAILS: {self.technical_details}")
        if self.mitigations:
            parts.append(f"MITIGATIONS: {' | '.join(self.mitigations)}")
        return "\n".join(parts)

class RagQueryResult(BaseModel):
    record: ThreatIntelRecord
    relevance_score: float
    matched_by: str  # "cve_exact", "product_match", "lexical_semantic"
