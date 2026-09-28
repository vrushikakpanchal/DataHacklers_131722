"""Threat-intelligence adapter for Ishita's RAG store and bundled evidence."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[2] / "ishita_code" / "backend"
DATASET_DIR = BACKEND_DIR.parent / "datasets"
SAMPLE_STORE = BACKEND_DIR / "data" / "threat_intel_store.json"
MY_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_RAG_STORE = None
_RAG_TRIED = False
_LOCAL_RECORDS = None
_LOCAL_RAG_WARNING = ""
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)
IP_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b")
SEVERITY_RE = re.compile(r"\b(CRITICAL|HIGH|MEDIUM|LOW)\b", re.I)


def _load_ishita_store():
    """Load Ishita's indexed retriever when its optional backend dependencies exist."""
    global _RAG_STORE, _RAG_TRIED, _LOCAL_RAG_WARNING
    if _RAG_TRIED:
        return _RAG_STORE
    _RAG_TRIED = True
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    MY_DATA_DIR.mkdir(parents=True, exist_ok=True)
    db_path = (MY_DATA_DIR / "threat_intel.sqlite3").resolve().as_posix()
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
    try:
        from app.core.database import Base, engine
        from app.models.rag import RagRecord  # noqa: F401 - register RAG tables
        from app.services.rag.store import ThreatIntelVectorStore

        Base.metadata.create_all(bind=engine)
        _RAG_STORE = ThreatIntelVectorStore()
        _index_bundled_datasets(_RAG_STORE)
    except Exception as exc:
        _LOCAL_RAG_WARNING = f"Ishita's SQL-backed RAG dependencies/store unavailable: {exc}"
        _RAG_STORE = None
    return _RAG_STORE


def _index_bundled_datasets(store) -> None:
    """Idempotently index the bundled CISA KEV CSV and CERT-In PDFs."""
    csv_files = sorted(DATASET_DIR.glob("*known_exploited*.csv"))
    for path in csv_files:
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with path.open("rb") as stream:
                store.ingest_cisa_kev_csv_stream(
                    stream, dataset_hash=digest, filename=path.name
                )
        except Exception:
            continue
    for path in sorted(DATASET_DIR.glob("*.pdf")):
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with path.open("rb") as stream:
                store.ingest_cert_in_pdf_stream(
                    stream, dataset_hash=digest, filename=path.name
                )
        except Exception:
            continue


def _load_local_records() -> list[dict[str, Any]]:
    """Dependency-light fallback lookup over Ishita's bundled evidence files."""
    global _LOCAL_RECORDS
    if _LOCAL_RECORDS is not None:
        return _LOCAL_RECORDS
    records: list[dict[str, Any]] = []
    if SAMPLE_STORE.exists():
        try:
            loaded = json.loads(SAMPLE_STORE.read_text(encoding="utf-8"))
            records.extend(item for item in loaded if isinstance(item, dict))
        except (OSError, json.JSONDecodeError):
            pass
    for path in sorted(DATASET_DIR.glob("*known_exploited*.csv")):
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as source:
                for row in csv.DictReader(source):
                    cve = (row.get("cveID") or row.get("cve_id") or "").strip().upper()
                    if not cve:
                        continue
                    vendor = row.get("vendorProject", "")
                    product = row.get("product", "")
                    records.append({
                        "id": f"cisa-{cve}", "source_name": "CISA-KEV", "source_type": "CISA_KEV",
                        "cve_id": cve, "cve_ids": [cve],
                        "title": row.get("vulnerabilityName") or f"CISA KEV {cve}",
                        "summary": row.get("shortDescription", ""),
                        "technical_details": f"Vendor: {vendor}. Product: {product}. {row.get('requiredAction', '')}",
                        "severity": "", "cvss_score": "", "affected_products": [f"{vendor} {product}".strip()],
                        "affected_versions": [], "mitigations": [row.get("requiredAction", "")] if row.get("requiredAction") else [],
                        "references": [row.get("notes", "")] if row.get("notes", "").startswith("http") else [],
                        "published_date": row.get("dateAdded", ""), "matched_by": "local_cisa_csv",
                    })
        except (OSError, UnicodeError):
            continue
    try:
        import pdfplumber
        for path in sorted(DATASET_DIR.glob("*.pdf")):
            try:
                with pdfplumber.open(path) as pdf:
                    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                cves = sorted(set(match.upper() for match in CVE_RE.findall(text)))
                records.append({
                    "id": f"local-{path.stem}", "source_name": "Ishita local evidence",
                    "source_type": "CERT_IN", "title": path.stem.replace("_", " "),
                    "summary": text[:1800], "technical_details": text[:5000],
                    "cve_ids": cves, "cve_id": cves[0] if len(cves) == 1 else "",
                    "severity": next(iter(SEVERITY_RE.findall(text)), "").upper(),
                    "affected_products": [], "affected_versions": [], "mitigations": [],
                    "references": [], "matched_by": "local_pdf_text",
                })
            except Exception:
                continue
    except ImportError:
        pass
    _LOCAL_RECORDS = records
    return records


def _source_facts(source_text: str) -> dict[str, list[str]]:
    return {
        "cve_ids": sorted(set(value.upper() for value in CVE_RE.findall(source_text))),
        "ips": sorted(set(IP_RE.findall(source_text))),
        "severities": sorted(set(value.upper() for value in SEVERITY_RE.findall(source_text))),
    }


def retrieve_threat_intel(source_text: str, top_k: int = 5) -> dict[str, Any]:
    """Retrieve matching CVE/product evidence from Ishita's RAG store or local files."""
    facts = _source_facts(source_text)
    candidates = re.findall(r"(?im)^\s*(?:affected product|affected products|product|software)\s*:\s*(.+)$", source_text)
    versions = re.findall(r"(?im)^\s*(?:affected versions?|versions?)\s*:\s*(.+)$", source_text)
    store = _load_ishita_store()
    if store is not None:
        try:
            results = store.query(
                cve_ids=facts["cve_ids"], products=candidates, versions=versions,
                query_text=source_text[:6000], top_k=top_k,
            )
            matches = []
            for result in results:
                record = result.record.model_dump()
                record.update({"relevance_score": result.relevance_score, "matched_by": result.matched_by})
                matches.append(record)
            return {"matches": matches, "retrieval": "Ishita SQLite RAG", "warning": ""}
        except Exception as exc:
            warning = f"RAG query failed; using bundled-file lookup: {exc}"
    else:
        warning = _LOCAL_RAG_WARNING

    tokens = {token.lower() for token in re.findall(r"[A-Za-z0-9_.-]{4,}", source_text)}
    scored = []
    for record in _load_local_records():
        record_cves = {str(v).upper() for v in (record.get("cve_ids") or [])}
        if record.get("cve_id"):
            record_cves.add(str(record["cve_id"]).upper())
        corpus = " ".join(str(record.get(key, "")) for key in ("title", "summary", "technical_details", "affected_products"))
        record_tokens = {token.lower() for token in re.findall(r"[A-Za-z0-9_.-]{4,}", corpus)}
        exact = bool(record_cves.intersection(facts["cve_ids"]))
        overlap = len(tokens.intersection(record_tokens))
        score = 1.0 if exact else overlap / max(1, len(tokens))
        if exact or overlap >= 2:
            item = dict(record)
            item["relevance_score"] = round(score, 4)
            item["matched_by"] = "cve_exact" if exact else item.get("matched_by", "local_keyword")
            scored.append((exact, score, item))
    scored.sort(key=lambda entry: (not entry[0], -entry[1]))
    return {"matches": [item for _, _, item in scored[:top_k]], "retrieval": "Ishita bundled files", "warning": warning}


def validate_advisory_against_evidence(
    advisory_text: str,
    source_text: str,
    matches: list[dict[str, Any]],
) -> dict[str, Any]:
    """Check advisory identifiers against source locks and retrieved threat facts."""
    from modules.verifier import verify_content_against_facts

    source = _source_facts(source_text)
    evidence_cves: set[str] = set()
    evidence_severities: set[str] = set(source["severities"])
    for record in matches:
        evidence_cves.update(str(value).upper() for value in (record.get("cve_ids") or []))
        if record.get("cve_id"):
            evidence_cves.add(str(record["cve_id"]).upper())
        severity = str(record.get("severity") or "").upper()
        if severity in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
            evidence_severities.add(severity)

    generated_cves = set(value.upper() for value in CVE_RE.findall(advisory_text))
    generated_ips = set(IP_RE.findall(advisory_text))
    generated_severities = set(value.upper() for value in SEVERITY_RE.findall(advisory_text))
    trusted_cves = set(source["cve_ids"]) | evidence_cves
    unverified_cves = sorted(generated_cves - trusted_cves)
    unverified_ips = sorted(set(generated_ips) - set(source["ips"]))
    severity_conflicts = sorted(generated_severities - evidence_severities) if evidence_severities else []

    locked_params = {
        "locked_cves": sorted(set(source["cve_ids"]) | evidence_cves),
        "locked_ips": source["ips"],
        "locked_severities": sorted(evidence_severities),
    }
    fact_preservation = verify_content_against_facts(advisory_text, locked_params)
    discrepancies = bool(unverified_cves or unverified_ips or severity_conflicts)
    return {
        "status": "FLAGGED" if discrepancies or fact_preservation["status"] != "PASS" else "PASS",
        "has_discrepancies": discrepancies,
        "unverified_cves": unverified_cves,
        "unverified_ips": unverified_ips,
        "severity_conflicts": severity_conflicts,
        "trusted_cves": sorted(trusted_cves),
        "fact_preservation": fact_preservation,
    }
