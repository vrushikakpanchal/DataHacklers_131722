import os
import re
import logging
import pdfplumber
from docx import Document
from typing import Dict, Any

logger = logging.getLogger(__name__)


def build_fallback_canonical_facts(text: str, locked_params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a deterministic facts object when the local LLM is unavailable."""
    source    = (text or "").strip()
    sentences = re.split(r"(?<=[.!?])\s+", source)
    summary   = " ".join(sentences[:2]).strip() or "No readable text could be extracted from the source document."
    severities = locked_params.get("locked_severities", [])

    # Seed affected_systems from deterministically extracted entity names so the
    # fallback path never returns an empty list when platforms/products are named
    # in the source text.
    locked_entities = locked_params.get("locked_entities", [])

    return {
        "title": "Security Advisory Briefing",
        "severity": severities[0] if severities else "UNKNOWN",
        "cve_ids": list(locked_params.get("locked_cves", [])),
        "affected_systems": list(locked_entities),
        "summary": summary[:1000],
        "recommended_actions": ["Review the source document and confirm appropriate mitigation actions."],
        "locked_ips": list(locked_params.get("locked_ips", [])),
    }

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


def _extract_named_entities(text: str) -> list:
    """
    Deterministically extract platforms, products, services, and entities that
    the source document explicitly identifies as affected, targeted, misused,
    or exploited — strictly from the document text, never from hardcoded lists.

    Extraction is document-grounded: every name must appear in a context that
    signals it is the subject of the advisory (enumeration lines, "Affected …:",
    TLD-bearing names, names followed by "users/victims/accounts", multi-word
    proper-noun products).  Generic brand-list matching is intentionally absent
    to prevent cross-document contamination.

    Returns a deduplicated list (original casing), capped at 20 items.
    """
    found: list = []
    seen: set = set()

    _NOISE_WORDS = {
        "platform", "app", "website", "portal", "service", "system",
        "application", "marketplace", "network", "site", "official", "crime",
        "cyber", "sebi", "user", "victim", "account", "client", "customer",
        "broker", "register", "advisory", "report", "notice", "bulletin",
        "alert", "note", "multiple", "vulnerability", "technical", "critical",
        "high", "medium", "low", "the", "and", "for", "with", "from",
    }
    _GENERIC_STARTS = {
        "The", "This", "These", "Those", "Such", "Each", "All", "Any",
        "Some", "New", "Old", "First", "Last", "Next", "Both", "Many",
        "Only", "Just", "Also", "More", "Most", "Other", "National",
        "Central", "State", "Ministry", "Department", "Bureau", "Government",
        "Indian", "Advisory", "Security", "Cyber", "Report", "Notice",
        "Bulletin", "Alert", "Version", "Update", "Release", "Service",
        "Internet", "January", "February", "March", "April", "June", "July",
        "August", "September", "October", "November", "December",
        "In", "Vulnerability", "Note", "Cert", "Affected", "Impacted",
        "Targeted", "Exploited", "Recommended", "Required",
    }

    def add(name: str) -> None:
        # Strip leading articles and punctuation
        clean = re.sub(r'^(?:the|a|an)\s+', '', name.strip(), flags=re.IGNORECASE)
        clean = clean.strip(".,;:()")
        # Collapse embedded newlines from multi-line regex spans
        clean = re.split(r'[\r\n]', clean)[0].strip()
        if len(clean) < 4:           # raise minimum length to 4 to drop "Pay", "App" etc.
            return
        if clean.lower() in _NOISE_WORDS:
            return
        if not re.search(r'[A-Z0-9.]', clean):
            return
        # Drop strings that look like sentence fragments (contain a space and start
        # with a generic word, e.g. "Time Passwords", "Investment Scams")
        if ' ' in clean:
            first = clean.split()[0]
            _FRAGMENT_STARTS = {
                "Time","One","Two","Three","Four","Five","Six","Seven","Eight",
                "Nine","Ten","Investment","Financial","Online","Fake","Real",
                "New","Old","Any","All","Some","Such","This","That",
            }
            if first in _FRAGMENT_STARTS:
                return
        # Drop bare ALL-CAPS tokens that look like document labels (CIVN, TAU, ADV …)
        # Allow well-known regulatory/financial acronyms that ARE product identifiers
        _KEEP_ACRONYMS = {
            "AWS", "GCP", "SAP", "UPI", "VPN", "IoT", "SDK", "CRM", "ERP",
            "RBI", "NSE", "BSE", "IRDAI", "NPCI", "OTP", "KYC", "API",
        }
        if re.match(r'^[A-Z0-9/\-]{2,10}$', clean) and clean not in _KEEP_ACRONYMS:
            return
        key = clean.lower()
        if key not in seen:
            seen.add(key)
            found.append(clean)

    # ── 1. Explicit enumeration lines ────────────────────────────────────────
    # "Affected platforms: Shaadi.com, Tinder"  /  "Targeted systems: Apache, Nginx"
    # This is the highest-confidence signal — the document is explicitly listing them.
    for m in re.finditer(
        r'(?:Affected|Impacted|Targeted|Exploited|Vulnerable|Compromised)'
        r'\s+[\w\s]*?:\s*([^\n]{3,200})',
        text, re.IGNORECASE
    ):
        for token in re.split(r'[,;]\s*', m.group(1)):
            t = token.strip().rstrip('.')
            if t and t.lower() not in _NOISE_WORDS:
                add(t)

    # ── 2. Domain names with common TLDs ─────────────────────────────────────
    # shaadi.com, cybercrime.gov.in, truecaller.in — these are document-specific.
    for m in re.finditer(
        r'\b([A-Za-z0-9][\w.-]{1,40}'
        r'\.(?:com|in|org|net|io|co|gov|app|ai|edu|int))\b',
        text
    ):
        name = m.group(1)
        # Skip pure IP-like patterns (already covered by locked_ips)
        if not re.match(r'^[\d.]+$', name):
            add(name)

    # ── 3. "X users / X victims / X accounts" ────────────────────────────────
    # "Tinder victims", "WhatsApp users" — the noun directly precedes "users/victims"
    # which signals it is the service being abused, not a passing mention.
    for m in re.finditer(
        r'\b([A-Z][A-Za-z0-9][\w.-]{1,30})'
        r'\s+(?:users?|victims?|accounts?|customers?|subscribers?|members?)\b',
        text
    ):
        add(m.group(1))

    # ── 4. Named as the medium/channel in a prepositional phrase ─────────────
    # "through WhatsApp", "via Telegram", "on Shaadi.com" where the NEXT token is
    # a suffix word confirming it is a platform.  The captured name must be
    # ≥ 5 chars to avoid splitting compound words (e.g. "Whats" from "WhatsApp").
    ctx_pattern = (
        r'(?:through|via|on|using|across|exploiting|abusing|targeting)\s+'
        r'([A-Z][A-Za-z0-9][\w.-]{3,35})\s+'          # ≥ 5 total chars (1+1+3)
        r'(?:app|platform|website|portal|service|marketplace|network|'
        r'site|application|system|exchange|messenger|channel)\b'
    )
    for m in re.finditer(ctx_pattern, text, re.IGNORECASE):
        add(m.group(1).strip())

    # ── 5. Multi-word proper product/platform names ───────────────────────────
    # "Apache HTTP Server 2.4.x", "Windows Server 2019", "Microsoft Azure",
    # "Google Cloud Platform", "Red Hat Enterprise Linux 8"
    multi_word_pat = (
        r'\b([A-Z][a-zA-Z0-9]+'
        r'(?:\s+[A-Z][a-zA-Z0-9]+){1,4}'
        r'(?:\s+\d[\d.x]*)?)\b'
    )
    for m in re.finditer(multi_word_pat, text):
        candidate = m.group(1).strip()
        first_word = candidate.split()[0]
        if first_word in _GENERIC_STARTS:
            continue
        if re.search(
            r'\b(?:Scam|Fraud|Advisory|Note|Report|Bulletin|Notice|Warning)\b',
            candidate, re.IGNORECASE
        ):
            continue
        if len(candidate.split()) >= 2:
            add(candidate)

    # ── 6. CamelCase tokens (≥ 2 case transitions, each part ≥ 3 chars) ────────
    # "BharatMatrimony", "GrowthInvestPro", "PhonePe"
    # Require each segment to be ≥ 3 chars to exclude "Whats"+"App" artefacts.
    for m in re.finditer(r'\b([A-Z][a-z]{2,}(?:[A-Z][a-z0-9]{2,})+)\b', text):
        token = m.group(1)
        if token not in _GENERIC_STARTS:
            add(token)

    return found[:20]


def lock_deterministic_parameters(text: str) -> Dict[str, Any]:
    """
    Uses deterministic regex matching to lock critical technical indicators.
    These parameters bypass LLM interpretation to prevent hallucination.
    """
    cve_pattern      = r'CVE-\d{4}-\d{4,7}'
    ip_pattern       = r'\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
    severity_pattern = r'\b(CRITICAL|HIGH|MEDIUM|LOW)\b'

    cves       = sorted(list(set(re.findall(cve_pattern, text, re.IGNORECASE))))
    ips        = sorted(list(set(re.findall(ip_pattern, text))))
    severities = sorted(list(set(re.findall(severity_pattern, text, re.IGNORECASE))))
    entities   = _extract_named_entities(text)

    return {
        "locked_cves":      cves,
        "locked_ips":       ips,
        "locked_severities":[s.upper() for s in severities],
        "locked_entities":  entities,
        "character_count":  len(text),
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
