import hashlib
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_operator
from app.models.user import User
from app.services.rag.schema import ThreatIntelRecord
from app.services.rag.store import threat_intel_store


router = APIRouter(tags=["rag"])


class RagQueryPayload(BaseModel):
    cve_ids: List[str] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)
    versions: List[str] = Field(default_factory=list)
    vendors: List[str] = Field(default_factory=list)
    query: str = ""
    top_k: int = 5


def _stream_sha256(stream) -> str:
    """Hash an uploaded dataset without materialising it in application memory."""
    stream.seek(0)
    digest = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    stream.seek(0)
    return digest.hexdigest()


def _peek_text(stream, size: int = 64 * 1024) -> str:
    stream.seek(0)
    data = stream.read(size)
    stream.seek(0)
    return data.decode("utf-8", errors="replace")


@router.get("/rag/stats")
def get_rag_knowledge_stats(current_user: User = Depends(get_current_user)):
    """Return persisted RAG record and explicit-ingestion status by source."""
    return threat_intel_store.get_stats()


@router.post("/rag/ingest")
async def ingest_dataset_file(
    file: UploadFile = File(...),
    source_name: Optional[str] = Form("Custom-Advisory"),
    current_user: User = Depends(require_operator),
):
    """
    Explicitly ingest a local threat-intelligence dataset. NVD is decoded in
    bounded chunks; normal application startup performs no automatic ingestion.
    """
    filename = file.filename or "dataset"
    lower_name = filename.lower()
    stream = file.file
    dataset_hash = _stream_sha256(stream)
    preview = _peek_text(stream)

    try:
        if lower_name.endswith(".pdf"):
            result = threat_intel_store.ingest_cert_in_pdf_stream(
                stream, dataset_hash=dataset_hash, filename=filename
            )
            return {
                "message": "CERT-In PDF ingestion completed.",
                "source": "CERT-In",
                **result,
            }

        if lower_name.endswith(".csv"):
            header = preview.splitlines()[0].lower() if preview.splitlines() else ""
            if not {"cveid", "vendorproject", "requiredaction"}.issubset(set(header.replace("\ufeff", "").split(","))):
                # Generic CSV remains supported for compatibility; it is intentionally not selected for KEV data.
                content = stream.read().decode("utf-8", errors="replace")
                count = threat_intel_store.ingest_csv(content, source_name=source_name or "CSV-Dataset")
                return {"message": f"Successfully ingested {count} CSV records.", "source": source_name, "count": count}
            result = threat_intel_store.ingest_cisa_kev_csv_stream(
                stream, dataset_hash=dataset_hash, filename=filename
            )
            return {
                "message": "CISA KEV CSV ingestion completed.",
                "source": "CISA-KEV",
                **result,
            }

        if lower_name.endswith(".json"):
            # NVD API 2.0 exports identify themselves before the large array.
            if '"format"' in preview and "NVD_CVE" in preview and '"vulnerabilities"' in preview:
                result = threat_intel_store.ingest_nvd_stream(
                    stream, dataset_hash=dataset_hash, filename=filename
                )
                return {"message": "NVD streaming ingestion completed.", "source": "NVD", **result}

            # Legacy/small JSON inputs remain supported without changing the NVD streaming path.
            data = json.load(stream)
            if isinstance(data, dict) and "vulnerabilities" in data:
                first_item = data["vulnerabilities"][0] if data["vulnerabilities"] else {}
                if "cveID" in first_item:
                    count = threat_intel_store.ingest_cisa_kev(data)
                    return {"message": f"Successfully ingested {count} CISA KEV records.", "source": "CISA-KEV", "count": count}
                if "cve" in first_item:
                    count = threat_intel_store.ingest_nvd_json(data)
                    return {"message": f"Successfully ingested {count} NVD CVE records.", "source": "NVD", "count": count}
                raise ValueError("Unrecognised vulnerabilities JSON schema.")
            if isinstance(data, list):
                records = [ThreatIntelRecord.model_validate(item) for item in data]
                threat_intel_store.bulk_add(records)
                return {"message": f"Successfully ingested {len(records)} custom threat-intel records.", "count": len(records)}
            raise ValueError("JSON must be an NVD/CISA object or a list of threat-intelligence records.")

        if lower_name.endswith(".jsonl"):
            records = [
                ThreatIntelRecord.model_validate(json.loads(line))
                for line in stream.read().decode("utf-8").splitlines()
                if line.strip()
            ]
            threat_intel_store.bulk_add(records)
            return {"message": f"Successfully ingested {len(records)} JSONL records.", "count": len(records)}

        raise HTTPException(status_code=400, detail="Supported formats: .csv, .json, .jsonl, .pdf")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to ingest dataset: {str(exc)}") from exc
    finally:
        await file.close()


@router.post("/rag/query")
def query_threat_intel(
    payload: RagQueryPayload,
    current_user: User = Depends(get_current_user),
):
    """Test exact and ranked retrieval without exposing the complete local corpus."""
    results = threat_intel_store.query(
        cve_ids=payload.cve_ids,
        products=payload.products,
        versions=payload.versions,
        vendors=payload.vendors,
        query_text=payload.query,
        top_k=payload.top_k,
    )
    return {
        "count": len(results),
        "results": [
            {
                "id": result.record.id,
                "source": result.record.source_name,
                "source_type": result.record.source_type,
                "document_type": result.record.document_type,
                "advisory_id": result.record.advisory_id,
                "cve_id": result.record.cve_id,
                "cve_ids": result.record.cve_ids,
                "title": result.record.title,
                "summary": result.record.summary,
                "mitigations": result.record.mitigations,
                "affected_products": result.record.affected_products,
                "affected_versions": result.record.affected_versions,
                "cvss_score": result.record.cvss_score,
                "severity": result.record.severity,
                "cwes": result.record.cwes,
                "references": result.record.references,
                "published_date": result.record.published_date,
                "modified_date": result.record.modified_date,
                "relevance_score": result.relevance_score,
                "matched_by": result.matched_by,
            }
            for result in results
        ],
    }
