"""Persistent, source-aware local RAG storage for security intelligence datasets."""

import csv
import hashlib
import io
import json
import re
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional

from sqlalchemy import func, or_

from app.core.database import SessionLocal
from app.models.rag import RagIngestion, RagRecord
from app.services.rag.schema import RagQueryResult, ThreatIntelRecord


CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
CERT_IN_PATTERN = re.compile(
    r"CERT-In\s+(?P<kind>Vulnerability Note|Advisory)\s+(?P<id>(?:CIVN|CIAD)-\d{4}-\d{4})",
    re.IGNORECASE,
)


def _unique(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        clean = str(value or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _cve_ids(text: str) -> List[str]:
    return _unique(match.upper() for match in CVE_PATTERN.findall(text or ""))


def _urls(text: str) -> List[str]:
    return _unique(URL_PATTERN.findall(text or ""))


def _normalise_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _safe_string(value: Any) -> str:
    return "" if value is None else str(value).strip()


class ThreatIntelVectorStore:
    """
    SQLite-backed hybrid retriever.

    Exact CVE lookups use indexed columns, while product, vendor, version, and
    keyword matching use a bounded local corpus field. The store never loads a
    complete NVD feed into memory and never forwards the dataset wholesale to a model.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        # Retained solely for compatibility with the former JSON-store constructor.
        self.storage_path = storage_path

    # ---------- persistence ----------

    @staticmethod
    def _to_orm_values(record: ThreatIntelRecord) -> Dict[str, Any]:
        cve_ids = _unique(([record.cve_id] if record.cve_id else []) + list(record.cve_ids or []))
        cve_ids = [cve.upper() for cve in cve_ids]
        cve_id = (record.cve_id or (cve_ids[0] if len(cve_ids) == 1 else "") or "").upper() or None
        products = _unique(record.affected_products or [])
        versions = _unique(record.affected_versions or [])
        vendor = _safe_string(record.vendor) or None
        product_terms = _normalise_text(" ".join([vendor or "", *products, *versions]))
        searchable = _normalise_text(
            "\n".join(
                [
                    record.source_name,
                    record.source_type,
                    record.document_type,
                    record.advisory_id or "",
                    " ".join(cve_ids),
                    vendor or "",
                    record.title,
                    " ".join(products),
                    " ".join(versions),
                    record.summary,
                    record.technical_details or "",
                    " ".join(record.cwes or []),
                ]
            )
        )
        return {
            "id": record.id,
            "source_type": record.source_type,
            "document_type": record.document_type,
            "source_name": record.source_name,
            "advisory_id": record.advisory_id,
            "cve_id": cve_id,
            "cve_ids": cve_ids,
            "vendor": vendor,
            "product_terms": product_terms,
            "title": record.title,
            "summary": record.summary,
            "technical_details": record.technical_details or "",
            "mitigations": _unique(record.mitigations or []),
            "affected_products": products,
            "affected_versions": versions,
            "cwes": _unique(record.cwes or []),
            "references": _unique(record.references or []),
            "cvss_score": record.cvss_score,
            "cvss_vector": record.cvss_vector,
            "severity": record.severity,
            "published_date": record.published_date,
            "modified_date": record.modified_date,
            "search_text": searchable,
            "raw_metadata": record.raw_metadata or {},
        }

    @staticmethod
    def _from_orm(record: RagRecord) -> ThreatIntelRecord:
        return ThreatIntelRecord(
            id=record.id,
            source_name=record.source_name,
            source_type=record.source_type,
            document_type=record.document_type,
            advisory_id=record.advisory_id,
            cve_id=record.cve_id,
            cve_ids=record.cve_ids or [],
            vendor=record.vendor,
            title=record.title,
            summary=record.summary,
            technical_details=record.technical_details,
            mitigations=record.mitigations or [],
            affected_products=record.affected_products or [],
            affected_versions=record.affected_versions or [],
            cvss_score=record.cvss_score,
            cvss_vector=record.cvss_vector,
            severity=record.severity,
            cwes=record.cwes or [],
            references=record.references or [],
            published_date=record.published_date,
            modified_date=record.modified_date,
            raw_metadata=record.raw_metadata or {},
        )

    def _upsert_batch(self, db, records: List[ThreatIntelRecord]) -> None:
        if not records:
            return
        existing = {
            row.id: row
            for row in db.query(RagRecord).filter(RagRecord.id.in_([record.id for record in records])).all()
        }
        for record in records:
            values = self._to_orm_values(record)
            row = existing.get(record.id)
            if row is None:
                db.add(RagRecord(**values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)

    def add_record(self, record: ThreatIntelRecord) -> None:
        self.bulk_add([record])

    def bulk_add(self, records: List[ThreatIntelRecord]) -> None:
        db = SessionLocal()
        try:
            self._upsert_batch(db, records)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _ingest_records(
        self,
        records: Iterable[ThreatIntelRecord],
        *,
        source_type: str,
        dataset_hash: str,
        filename: str,
    ) -> Dict[str, Any]:
        """Batch upsert an explicit dataset ingestion and make retries idempotent."""
        db = SessionLocal()
        ingestion: Optional[RagIngestion] = None
        try:
            ingestion = (
                db.query(RagIngestion)
                .filter(RagIngestion.source_type == source_type, RagIngestion.dataset_hash == dataset_hash)
                .first()
            )
            if ingestion and ingestion.status == "completed":
                return {
                    "count": ingestion.record_count,
                    "already_ingested": True,
                    "status": ingestion.status,
                    "source_type": source_type,
                }
            if ingestion is None:
                ingestion = RagIngestion(
                    source_type=source_type,
                    dataset_hash=dataset_hash,
                    filename=filename,
                    status="processing",
                )
                db.add(ingestion)
                db.commit()
            else:
                ingestion.status = "processing"
                ingestion.error_message = None
                db.commit()

            count = 0
            batch: List[ThreatIntelRecord] = []
            for record in records:
                batch.append(record)
                if len(batch) >= 250:
                    self._upsert_batch(db, batch)
                    count += len(batch)
                    batch.clear()
                    db.commit()
            if batch:
                self._upsert_batch(db, batch)
                count += len(batch)
                db.commit()

            ingestion.record_count = count
            ingestion.status = "completed"
            ingestion.completed_at = datetime.now(timezone.utc)
            db.commit()
            return {"count": count, "already_ingested": False, "status": "completed", "source_type": source_type}
        except Exception as exc:
            db.rollback()
            if ingestion is not None:
                ingestion.status = "failed"
                ingestion.error_message = str(exc)[:2000]
                db.add(ingestion)
                db.commit()
            raise
        finally:
            db.close()

    # ---------- NVD ----------

    @staticmethod
    def _iter_nvd_vulnerabilities(stream: BinaryIO) -> Iterator[Dict[str, Any]]:
        """Incrementally decode NVD's top-level vulnerabilities array with stdlib JSON only."""
        decoder = json.JSONDecoder()
        buffer = ""
        array_started = False
        while True:
            raw_chunk = stream.read(1024 * 1024)
            if raw_chunk:
                buffer += raw_chunk.decode("utf-8") if isinstance(raw_chunk, bytes) else raw_chunk
            elif not buffer:
                return

            if not array_started:
                match = re.search(r'"vulnerabilities"\s*:\s*\[', buffer)
                if not match:
                    if raw_chunk:
                        buffer = buffer[-256:]
                        continue
                    raise ValueError("NVD JSON does not contain a vulnerabilities array.")
                buffer = buffer[match.end():]
                array_started = True

            position = 0
            needs_more = False
            while True:
                while position < len(buffer) and buffer[position] in " \t\r\n,":
                    position += 1
                if position >= len(buffer):
                    needs_more = True
                    break
                if buffer[position] == "]":
                    return
                try:
                    item, end = decoder.raw_decode(buffer, position)
                except json.JSONDecodeError:
                    needs_more = True
                    break
                if not isinstance(item, dict):
                    raise ValueError("NVD vulnerabilities array contains a non-object item.")
                yield item
                position = end

            buffer = buffer[position:]
            if not raw_chunk:
                if needs_more and buffer.strip():
                    raise ValueError("NVD JSON ended before a complete vulnerability record was decoded.")
                return

    @staticmethod
    def _nvd_metric(metrics: Dict[str, Any]) -> Dict[str, Any]:
        for name in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            entries = metrics.get(name) or []
            if entries:
                data = entries[0].get("cvssData") or {}
                if data:
                    return {
                        "score": _safe_string(data.get("baseScore")),
                        "severity": _safe_string(data.get("baseSeverity")) or _safe_string(entries[0].get("baseSeverity")),
                        "vector": _safe_string(data.get("vectorString")),
                        "version": _safe_string(data.get("version")),
                    }
        return {}

    @staticmethod
    def _nvd_products(cve: Dict[str, Any], item: Dict[str, Any]) -> tuple[List[str], List[str], List[str]]:
        products: List[str] = []
        versions: List[str] = []
        vendors: List[str] = []
        for affected in cve.get("affected") or []:
            for data in affected.get("affectedData") or []:
                vendor = _safe_string(data.get("vendor"))
                product = _safe_string(data.get("product"))
                if vendor:
                    vendors.append(vendor)
                if product:
                    products.extend([f"{vendor} {product}".strip(), product])
                for version in data.get("versions") or []:
                    value = _safe_string(version.get("version"))
                    if value:
                        versions.append(value)

        def collect_cpes(node: Dict[str, Any]) -> None:
            for match in node.get("cpeMatch") or []:
                if not match.get("vulnerable", True):
                    continue
                parts = _safe_string(match.get("criteria")).split(":")
                if len(parts) > 5:
                    vendor, product, version = parts[3], parts[4], parts[5]
                    if vendor and vendor != "*":
                        vendors.append(vendor)
                    if product and product != "*":
                        products.extend([f"{vendor} {product}".strip(), product])
                    if version and version != "*":
                        versions.append(version)
                for key, label in (("versionStartIncluding", ">="), ("versionStartExcluding", ">"), ("versionEndIncluding", "<="), ("versionEndExcluding", "<")):
                    value = _safe_string(match.get(key))
                    if value:
                        versions.append(f"{label}{value}")
            for child in node.get("nodes") or []:
                collect_cpes(child)

        for configuration in item.get("configurations") or cve.get("configurations") or []:
            collect_cpes(configuration)
        return _unique(products), _unique(versions), _unique(vendors)

    @classmethod
    def _nvd_record(cls, item: Dict[str, Any]) -> Optional[ThreatIntelRecord]:
        cve = item.get("cve") or {}
        cve_id = _safe_string(cve.get("id")).upper()
        if not cve_id:
            return None
        description = next(
            (_safe_string(entry.get("value")) for entry in cve.get("descriptions") or [] if entry.get("lang") == "en"),
            "",
        )
        metric = cls._nvd_metric(cve.get("metrics") or item.get("metrics") or {})
        products, versions, vendors = cls._nvd_products(cve, item)
        cwes = _unique(
            description.get("value")
            for weakness in (cve.get("weaknesses") or item.get("weaknesses") or [])
            for description in (weakness.get("description") or [])
            if description.get("lang") == "en"
        )
        references = _unique(
            reference.get("url")
            for reference in (cve.get("references") or item.get("references") or [])
            if reference.get("url")
        )
        return ThreatIntelRecord(
            id=f"nvd-{cve_id}",
            source_name="NVD",
            source_type="NVD",
            document_type="CVE",
            cve_id=cve_id,
            cve_ids=[cve_id],
            vendor=", ".join(vendors[:8]) or None,
            title=f"{cve_id}: {description[:180]}" if description else cve_id,
            summary=description,
            technical_details=description,
            affected_products=products,
            affected_versions=versions,
            cvss_score=metric.get("score") or None,
            cvss_vector=metric.get("vector") or None,
            severity=metric.get("severity") or "UNKNOWN",
            cwes=cwes,
            references=references,
            published_date=_safe_string(cve.get("published")) or None,
            modified_date=_safe_string(cve.get("lastModified")) or None,
            raw_metadata={
                "source_identifier": cve.get("sourceIdentifier"),
                "vuln_status": cve.get("vulnStatus"),
                "cvss": metric,
                "cwes": cwes,
                "vendor": vendors,
                "products": products,
                "versions": versions,
                "references": references,
                "published": cve.get("published"),
                "last_modified": cve.get("lastModified"),
            },
        )

    def ingest_nvd_stream(self, stream: BinaryIO, *, dataset_hash: str, filename: str) -> Dict[str, Any]:
        def records() -> Iterator[ThreatIntelRecord]:
            for item in self._iter_nvd_vulnerabilities(stream):
                record = self._nvd_record(item)
                if record:
                    yield record

        return self._ingest_records(records(), source_type="NVD", dataset_hash=dataset_hash, filename=filename)

    def ingest_nvd_json(self, json_data: Dict[str, Any]) -> int:
        """Compatibility entry point for small NVD JSON payloads used by older callers/tests."""
        serialised = json.dumps(json_data, sort_keys=True).encode("utf-8")
        result = self._ingest_records(
            (record for item in json_data.get("vulnerabilities", []) if (record := self._nvd_record(item))),
            source_type="NVD",
            dataset_hash=hashlib.sha256(serialised).hexdigest(),
            filename="nvd-inline.json",
        )
        return int(result["count"])

    # ---------- CISA KEV ----------

    @staticmethod
    def _cisa_record(row: Dict[str, Any], index: int = 0) -> Optional[ThreatIntelRecord]:
        normalised = {(key or "").strip().lower(): _safe_string(value) for key, value in row.items()}
        cve = (normalised.get("cveid") or normalised.get("cve") or normalised.get("cve_id") or "").upper()
        if not cve:
            return None
        vendor = normalised.get("vendorproject") or normalised.get("vendor") or ""
        product = normalised.get("product") or ""
        notes = normalised.get("notes") or ""
        action = normalised.get("requiredaction") or normalised.get("required_action") or ""
        ransomware = normalised.get("knownransomwarecampaignuse") or ""
        technical_details = _normalise_text(
            " ".join(
                part
                for part in [
                    f"Vendor: {vendor}." if vendor else "",
                    f"Product: {product}." if product else "",
                    "Listed by CISA as a known exploited vulnerability.",
                    f"Known ransomware campaign use: {ransomware}." if ransomware else "",
                    f"Required action: {action}" if action else "",
                    f"Forensic triage: {normalised.get('forensictriage')}" if normalised.get("forensictriage") else "",
                ]
                if part
            )
        )
        return ThreatIntelRecord(
            id=f"cisa-kev-{cve}",
            source_name="CISA-KEV",
            source_type="CISA_KEV",
            document_type="KEV",
            cve_id=cve,
            cve_ids=[cve],
            vendor=vendor or None,
            title=normalised.get("vulnerabilityname") or f"CISA KEV {cve}",
            summary=normalised.get("shortdescription") or normalised.get("description") or "",
            technical_details=technical_details,
            mitigations=[action] if action else [],
            affected_products=_unique([product, f"{vendor} {product}".strip()]),
            cwes=_unique(re.split(r"\s*[,;]\s*", normalised.get("cwes") or "")),
            references=_urls(notes),
            published_date=normalised.get("dateadded") or None,
            modified_date=normalised.get("duedate") or None,
            raw_metadata={"fields": normalised, "known_ransomware_campaign_use": ransomware},
        )

    def ingest_cisa_kev_csv_stream(self, stream: BinaryIO, *, dataset_hash: str, filename: str) -> Dict[str, Any]:
        text_stream = io.TextIOWrapper(stream, encoding="utf-8-sig", newline="")
        try:
            reader = csv.DictReader(text_stream)
            records = (record for index, row in enumerate(reader) if (record := self._cisa_record(row, index)))
            return self._ingest_records(records, source_type="CISA_KEV", dataset_hash=dataset_hash, filename=filename)
        finally:
            text_stream.detach()

    def ingest_cisa_kev(self, json_data: Dict[str, Any]) -> int:
        rows = json_data.get("vulnerabilities", [])
        serialised = json.dumps(json_data, sort_keys=True).encode("utf-8")
        converted_rows = (
            {
                "cveID": row.get("cveID"), "vendorProject": row.get("vendorProject"), "product": row.get("product"),
                "vulnerabilityName": row.get("vulnerabilityName"), "dateAdded": row.get("dateAdded"),
                "shortDescription": row.get("shortDescription"), "requiredAction": row.get("requiredAction"),
                "dueDate": row.get("dueDate"), "knownRansomwareCampaignUse": row.get("knownRansomwareCampaignUse"),
                "notes": row.get("notes"), "cwes": row.get("cwes"),
            }
            for row in rows
        )
        result = self._ingest_records(
            (record for index, row in enumerate(converted_rows) if (record := self._cisa_record(row, index))),
            source_type="CISA_KEV",
            dataset_hash=hashlib.sha256(serialised).hexdigest(),
            filename="cisa-kev-inline.json",
        )
        return int(result["count"])

    def ingest_csv(self, csv_content: str, source_name: str = "CSV-Dataset") -> int:
        """Compatibility handler; recognises CISA KEV columns and otherwise indexes generic CSV rows."""
        reader = csv.DictReader(io.StringIO(csv_content))
        fields = {field.lower() for field in (reader.fieldnames or [])}
        if {"cveid", "vendorproject", "requiredaction"}.issubset(fields):
            result = self._ingest_records(
                (record for index, row in enumerate(reader) if (record := self._cisa_record(row, index))),
                source_type="CISA_KEV",
                dataset_hash=hashlib.sha256(csv_content.encode("utf-8")).hexdigest(),
                filename="cisa-kev-inline.csv",
            )
            return int(result["count"])

        def generic_records() -> Iterator[ThreatIntelRecord]:
            for index, row in enumerate(reader):
                normalised = {(key or "").strip().lower(): _safe_string(value) for key, value in row.items()}
                cve = normalised.get("cve") or normalised.get("cve_id") or normalised.get("cveid")
                title = normalised.get("title") or normalised.get("name") or normalised.get("vulnerability_name") or f"Advisory #{index + 1}"
                product = normalised.get("product") or normalised.get("affected_product") or ""
                yield ThreatIntelRecord(
                    id=f"csv-{hashlib.sha256(source_name.encode()).hexdigest()[:10]}-{index}",
                    source_name=source_name, source_type="CUSTOM", document_type="record",
                    cve_id=cve.upper() if cve else None, cve_ids=[cve.upper()] if cve else [],
                    title=title, summary=normalised.get("summary") or normalised.get("description") or normalised.get("desc") or "",
                    mitigations=[normalised["mitigation"]] if normalised.get("mitigation") else [],
                    affected_products=[product] if product else [], raw_metadata={"fields": normalised},
                )

        result = self._ingest_records(
            generic_records(), source_type="CUSTOM", dataset_hash=hashlib.sha256(csv_content.encode("utf-8")).hexdigest(),
            filename=f"{source_name}.csv",
        )
        return int(result["count"])

    # ---------- CERT-In PDFs ----------

    @staticmethod
    def _cert_sections(content: str) -> Dict[str, str]:
        headings = [
            "Software Affected", "Overview", "Target Audience", "Risk Assessment", "Impact Assessment", "Description",
            "Tactics, Techniques, and Procedures", "TTPs", "Indicators of Compromise", "IoCs", "Solution", "Mitigation",
            "Recommendations", "Vendor Information", "References", "CVE Name",
        ]
        pattern = re.compile(r"(?m)^(" + "|".join(re.escape(heading) for heading in headings) + r")\s*$", re.IGNORECASE)
        matches = list(pattern.finditer(content))
        sections: Dict[str, str] = {}
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            sections[match.group(1).strip().lower()] = content[match.end():end].strip()
        return sections

    @classmethod
    def _cert_in_record(cls, stream: BinaryIO, filename: str) -> ThreatIntelRecord:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("CERT-In PDF ingestion requires the existing pypdf dependency.") from exc
        stream.seek(0)
        extracted = "\n".join(page.extract_text() or "" for page in PdfReader(stream).pages)
        marker = CERT_IN_PATTERN.search(extracted)
        if not marker:
            raise ValueError("PDF is not a recognised CERT-In advisory or vulnerability note.")
        # Strip navigation/sidebar text and footer boilerplate before indexing the publication body.
        content = extracted[marker.start():]
        content = re.split(r"(?mi)^Disclaimer\s*$", content, maxsplit=1)[0]
        content = re.sub(r"(?mi)^Contact Information\s*$.*\Z", "", content)
        content = re.sub(r"(?mi)^Postal address\s*$.*\Z", "", content)
        advisory_id = marker.group("id").upper()
        content = content.replace(marker.group("id"), advisory_id + "\n", 1)
        document_type = "vulnerability_note" if marker.group("kind").lower() == "vulnerability note" else "advisory"
        date_match = re.search(r"Original Issue Date:\s*([^\n]+)", content, re.IGNORECASE)
        severity_match = re.search(r"Severity Rating:\s*([^\n]+)", content, re.IGNORECASE)
        first_section = re.search(r"(?mi)^(?:Software Affected|Overview|Description)\s*$", content)
        header = content[: first_section.start() if first_section else len(content)]
        header = re.sub(r"(?is)^CERT-In\s+(?:Vulnerability Note|Advisory)\s+" + re.escape(advisory_id), "", header).strip()
        title = re.sub(r"(?is)Original Issue Date:.*\Z", "", header).strip() or f"CERT-In {advisory_id}"
        sections = cls._cert_sections(content)
        overview = sections.get("overview") or sections.get("description") or ""
        affected = sections.get("software affected") or ""
        mitigations = [
            _normalise_text(value)
            for value in (sections.get("solution", ""), sections.get("mitigation", ""), sections.get("recommendations", ""))
            if _normalise_text(value)
        ]
        technical_parts = [
            f"{heading.title()}: {sections[heading]}"
            for heading in ("overview", "risk assessment", "impact assessment", "description", "tactics, techniques, and procedures", "ttps", "indicators of compromise", "iocs", "solution", "mitigation", "recommendations")
            if sections.get(heading)
        ]
        cves = _cve_ids(content)
        urls = _urls(content)
        return ThreatIntelRecord(
            id=f"cert-in-{advisory_id.lower()}", source_name="CERT-In", source_type="CERT_IN", document_type=document_type,
            advisory_id=advisory_id, cve_id=cves[0] if len(cves) == 1 else None, cve_ids=cves,
            title=_normalise_text(title), summary=_normalise_text(overview),
            technical_details="\n\n".join(technical_parts) or _normalise_text(content), mitigations=mitigations,
            affected_products=[_normalise_text(affected)] if affected else [],
            severity=_safe_string(severity_match.group(1)) if severity_match else "UNKNOWN", references=urls,
            published_date=_safe_string(date_match.group(1)) if date_match else None,
            raw_metadata={"filename": filename, "advisory_id": advisory_id, "document_type": document_type, "sections": sections, "cve_ids": cves, "references": urls},
        )

    def ingest_cert_in_pdf_stream(self, stream: BinaryIO, *, dataset_hash: str, filename: str) -> Dict[str, Any]:
        return self._ingest_records([self._cert_in_record(stream, filename)], source_type="CERT_IN", dataset_hash=dataset_hash, filename=filename)

    # ---------- retrieval ----------

    @staticmethod
    def _source_priority(source_type: str) -> int:
        return {"NVD": 0, "CISA_KEV": 1, "CERT_IN": 2}.get(source_type, 3)

    @staticmethod
    def _match_score(source_type: str, base: float) -> float:
        return base if source_type != "CERT_IN" else min(base, 0.65)

    @staticmethod
    def _tokenise(text: str) -> List[str]:
        ignored = {
            "this", "that", "with", "from", "have", "been", "were", "will", "would", "could", "should",
            "vulnerability", "vulnerabilities", "security", "affected", "reported", "system", "systems", "software",
            "remote", "attacker", "attack", "allows", "allow", "through", "where", "which", "into", "using",
        }
        return [token for token in re.findall(r"\b[a-zA-Z0-9_.-]{3,}\b", text.lower()) if token not in ignored and not token.startswith("cve-")]

    def query(
        self, cve_ids: Optional[List[str]] = None, products: Optional[List[str]] = None,
        versions: Optional[List[str]] = None, vendors: Optional[List[str]] = None,
        query_text: str = "", top_k: int = 5,
    ) -> List[RagQueryResult]:
        """Prioritise exact CVE, product, version, vendor, then security-keyword retrieval."""
        top_k = max(1, min(top_k, 10))
        results: List[RagQueryResult] = []
        seen_ids = set()
        exact_cve_match_found = False

        def append(rows: Iterable[RagRecord], score: float, matched_by: str) -> None:
            for row in sorted(rows, key=lambda item: self._source_priority(item.source_type)):
                if row.id in seen_ids:
                    continue
                results.append(RagQueryResult(record=self._from_orm(row), relevance_score=self._match_score(row.source_type, score), matched_by=matched_by))
                seen_ids.add(row.id)
                if len(results) >= top_k:
                    return

        db = SessionLocal()
        try:
            # A CERT-In ID in a source is an explicit reference, not a broad
            # keyword. Resolve it before the lower-confidence lexical tier.
            advisory_ids = _unique(
                match.upper()
                for match in re.findall(r"\b(?:CIVN|CIAD)-\d{4}-\d{4}\b", query_text or "", re.IGNORECASE)
            )
            for advisory_id in advisory_ids:
                if len(results) >= top_k:
                    break
                append(
                    db.query(RagRecord).filter(RagRecord.advisory_id == advisory_id).all(),
                    0.90,
                    "advisory_exact",
                )
            for cve in _unique(cve_ids or []):
                if len(results) >= top_k:
                    break
                normalised = cve.upper()
                # `LIKE %CVE-...%` is not an exact lookup: it also matches
                # longer identifiers such as CVE-2026-72730. NVD/CISA retain
                # an indexed primary CVE; CERT-In's multi-CVE records are a
                # tiny separate set checked against their parsed JSON list.
                rows = db.query(RagRecord).filter(RagRecord.cve_id == normalised).all()
                rows.extend(
                    row
                    for row in db.query(RagRecord).filter(RagRecord.source_type == "CERT_IN").all()
                    if normalised in (row.cve_ids or [])
                )
                exact_cve_match_found = exact_cve_match_found or bool(rows)
                append(rows, 1.0, "cve_exact")
            # Exact CVE matches are the authoritative generation context. Do
            # not dilute them with broad product/version/vendor candidates or
            # generic security keywords; those can describe a different CVE.
            if not exact_cve_match_found:
                for product in _unique(products or []):
                    if len(results) >= top_k or len(product.strip()) < 3:
                        break
                    term = product.strip()
                    rows = db.query(RagRecord).filter(or_(RagRecord.product_terms.ilike(f"%{term}%"), RagRecord.title.ilike(f"%{term}%"))).limit(top_k * 12).all()
                    # Keep relevant CERT-In structural/contextual material in the
                    # compact result even when NVD has many product matches.
                    primary = [row for row in rows if row.source_type != "CERT_IN"]
                    cert_in = [row for row in rows if row.source_type == "CERT_IN"]
                    remaining = top_k - len(results)
                    append(primary[: min(3, remaining)], 0.85, "product_exact")
                    append(cert_in, 0.85, "product_exact")
                    append(primary[3:], 0.85, "product_exact")
                for version in _unique(versions or []):
                    if len(results) >= top_k or len(version.strip()) < 2:
                        break
                    rows = db.query(RagRecord).filter(RagRecord.product_terms.ilike(f"%{version.strip()}%")).limit(top_k * 6).all()
                    append(rows, 0.78, "version_exact")
                for vendor in _unique(vendors or []):
                    if len(results) >= top_k or len(vendor.strip()) < 3:
                        break
                    rows = db.query(RagRecord).filter(RagRecord.vendor.ilike(f"%{vendor.strip()}%")).limit(top_k * 6).all()
                    append(rows, 0.70, "vendor_match")
            # An explicit CERT-In ID is already a precise contextual lookup;
            # do not pad it with loosely related keyword hits.
            if len(results) < top_k and query_text and not advisory_ids and not exact_cve_match_found:
                tokens = self._tokenise(query_text)
                if tokens:
                    # The common terms in security advisories can match far more
                    # than a small SQL candidate window. Prefer rare/identifier
                    # terms and leave broad phrase scoring bounded.
                    ranked_tokens = sorted(tokens[:16], key=lambda token: ("-" not in token, -len(token)))
                    rows = db.query(RagRecord).filter(or_(*[RagRecord.search_text.ilike(f"%{token}%") for token in ranked_tokens])).limit(1000).all()
                    scored = []
                    for row in rows:
                        if row.id not in seen_ids:
                            matches = sum(token in (row.search_text or "").lower() for token in tokens)
                            if matches:
                                scored.append((matches / max(1, len(tokens)), row))
                    scored.sort(key=lambda item: (-item[0], self._source_priority(item[1].source_type)))
                    append((row for _, row in scored), min(0.65, scored[0][0] if scored else 0.0), "security_keywords")
        finally:
            db.close()
        return results[:top_k]

    def get_stats(self) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            source_counts = dict(db.query(RagRecord.source_type, func.count(RagRecord.id)).group_by(RagRecord.source_type).all())
            source_names = dict(db.query(RagRecord.source_name, func.count(RagRecord.id)).group_by(RagRecord.source_name).all())
            indexed_cves = db.query(func.count(func.distinct(RagRecord.cve_id))).filter(RagRecord.cve_id.isnot(None)).scalar() or 0
            ingestion_rows = db.query(RagIngestion).order_by(RagIngestion.completed_at.desc()).all()
            return {
                "total_records": sum(source_counts.values()), "indexed_cves": indexed_cves, "sources": source_names,
                "source_types": source_counts,
                "ingestions": [{"source_type": item.source_type, "filename": item.filename, "status": item.status, "record_count": item.record_count, "completed_at": item.completed_at.isoformat() if item.completed_at else None} for item in ingestion_rows],
                "status": "ready" if source_counts else "empty",
            }
        finally:
            db.close()


threat_intel_store = ThreatIntelVectorStore()
