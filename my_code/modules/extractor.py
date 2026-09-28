import os
import re
import pdfplumber
from docx import Document
from typing import Dict, Any

def extract_raw_text(file_path: str) -> str:
    """
    Extracts raw text from .txt, .pdf, or .docx files.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    elif ext == ".pdf":
        extracted_pages = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_pages.append(text)
        return "\n".join(extracted_pages)

    elif ext == ".docx":
        document = Document(file_path)
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(part for part in parts if part.strip())

    else:
        raise ValueError(f"Unsupported file format: {ext}. Only .txt, .pdf, and .docx are supported.")


def lock_deterministic_parameters(text: str) -> Dict[str, Any]:
    """
    Uses deterministic regex matching to lock critical technical indicators.
    These parameters bypass LLM interpretation to prevent hallucination.
    """
    # Regex Patterns
    cve_pattern = r'CVE-\d{4}-\d{4,7}'
    ip_pattern = r'\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
    severity_pattern = r'\b(CRITICAL|HIGH|MEDIUM|LOW)\b'
    version_pattern = r'\bv?\d+\.\d+(?:\.\d+)?\b'

    cves = sorted(list(set(re.findall(cve_pattern, text, re.IGNORECASE))))
    ips = sorted(list(set(re.findall(ip_pattern, text))))
    severities = sorted(list(set(re.findall(severity_pattern, text, re.IGNORECASE))))

    return {
        "locked_cves": cves,
        "locked_ips": ips,
        "locked_severities": [s.upper() for s in severities],
        "character_count": len(text)
    }


def process_and_lock_document(file_path: str) -> Dict[str, Any]:
    """
    Full pipeline for Phase 2: Ingest file -> Extract text -> Lock parameters.
    """
    raw_text = extract_raw_text(file_path)
    locked_facts = lock_deterministic_parameters(raw_text)

    return {
        "source_file": os.path.basename(file_path),
        "raw_text": raw_text,
        "locked_parameters": locked_facts
    }