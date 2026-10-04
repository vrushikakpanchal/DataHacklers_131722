from typing import Any, Dict, List, Optional, Tuple

from app.services.rag.schema import RagQueryResult
from app.services.rag.store import threat_intel_store


class ThreatIntelGroundingService:
    """Retrieve a small, provenance-labelled context block for Qwen 2.5:14b."""

    @staticmethod
    def _label(result: RagQueryResult) -> str:
        record = result.record
        if record.source_type == "NVD":
            return "NVD"
        if record.source_type == "CISA_KEV":
            return "CISA-KEV Known Exploited"
        if record.document_type == "vulnerability_note":
            return "CERT-In Vulnerability Note"
        return "CERT-In Advisory"

    @classmethod
    def retrieve(
        cls,
        cve_ids: Optional[List[str]] = None,
        products: Optional[List[str]] = None,
        versions: Optional[List[str]] = None,
        vendors: Optional[List[str]] = None,
        query_text: str = "",
    ) -> List[RagQueryResult]:
        return threat_intel_store.query(
            cve_ids=cve_ids,
            products=products,
            versions=versions,
            vendors=vendors,
            query_text=query_text,
            top_k=5,
        )

    @classmethod
    def format_context(cls, results: List[RagQueryResult]) -> str:
        if not results:
            return ""
        blocks = []
        for result in results:
            record = result.record
            fields = [
                f"[{cls._label(result)}]",
                f"Provenance: {record.source_name}; document_type={record.document_type}; record_id={record.id}",
                f"Identifier: {record.advisory_id or record.cve_id or ', '.join(record.cve_ids) or 'N/A'}",
                f"Title: {record.title}",
            ]
            if record.source_type == "CERT_IN":
                fields.append("Use only as structural/contextual reference; it must not overwrite user-source or matched NVD/CISA technical values.")
            if record.severity:
                fields.append(f"Severity: {record.severity}")
            if record.cvss_score:
                fields.append(f"CVSS: {record.cvss_score}{f' ({record.cvss_vector})' if record.cvss_vector else ''}")
            if record.cwes:
                fields.append(f"CWE: {', '.join(record.cwes[:12])}")
            if record.affected_products:
                fields.append(f"Affected products: {'; '.join(record.affected_products[:12])}")
            if record.affected_versions:
                fields.append(f"Affected versions: {'; '.join(record.affected_versions[:12])}")
            if record.published_date:
                fields.append(f"Published: {record.published_date}")
            if record.modified_date:
                fields.append(f"Modified/due: {record.modified_date}")
            if record.summary:
                fields.append(f"Summary: {record.summary[:1600]}")
            if record.mitigations:
                fields.append(f"Mitigation: {' '.join(record.mitigations)[:1200]}")
            if record.references:
                fields.append(f"References: {'; '.join(record.references[:8])}")
            blocks.append("\n".join(fields))

        return (
            "<AUTHORITATIVE_GROUNDING_DATABASE>\n"
            "Only the following small, retrieved records may supplement the source. "
            "Do not infer any missing technical fact or silently merge conflicts.\n\n"
            + "\n\n".join(blocks)
            + "\n</AUTHORITATIVE_GROUNDING_DATABASE>"
        )

    @staticmethod
    def provenance(results: List[RagQueryResult]) -> List[Dict[str, Any]]:
        return [
            {
                "record_id": result.record.id,
                "source_name": result.record.source_name,
                "source_type": result.record.source_type,
                "document_type": result.record.document_type,
                "advisory_id": result.record.advisory_id,
                "cve_ids": result.record.cve_ids,
                "matched_by": result.matched_by,
                "relevance_score": result.relevance_score,
            }
            for result in results
        ]

    @classmethod
    def get_grounding_bundle(
        cls,
        cve_ids: Optional[List[str]] = None,
        products: Optional[List[str]] = None,
        versions: Optional[List[str]] = None,
        vendors: Optional[List[str]] = None,
        query_text: str = "",
    ) -> Tuple[str, List[Dict[str, Any]]]:
        results = cls.retrieve(cve_ids, products, versions, vendors, query_text)
        return cls.format_context(results), cls.provenance(results)

    @classmethod
    def get_grounding_context(
        cls,
        cve_ids: Optional[List[str]] = None,
        products: Optional[List[str]] = None,
        query_text: str = "",
    ) -> str:
        context, _ = cls.get_grounding_bundle(cve_ids=cve_ids, products=products, query_text=query_text)
        return context


grounding_service = ThreatIntelGroundingService()
