import os
import re
import hashlib
from datetime import datetime
from typing import Dict, Any, Tuple
from loguru import logger

# Configure Loguru to record local audit trails
LOG_FILE_PATH = os.path.join("data", "outputs", "audit.log")
os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
logger.add(LOG_FILE_PATH, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", level="INFO")


def compute_sha256(file_path_or_content: str) -> str:
    """
    Computes a SHA-256 cryptographic hash for a file path or raw string content.
    Used to guarantee data integrity and audit provenance.
    """
    hasher = hashlib.sha256()
    
    if os.path.exists(file_path_or_content):
        with open(file_path_or_content, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
    else:
        hasher.update(file_path_or_content.encode("utf-8"))
        
    return hasher.hexdigest()


def redact_sensitive_pii(text: str) -> Tuple[str, Dict[str, int]]:
    """
    Scans and redacts sensitive PII and secrets (Email addresses, AWS/API keys, Secret tokens)
    before sending text to downstream components or models.
    """
    # Regex patterns for sensitive data
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    secret_key_pattern = r'(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{16,})["\']?'
    
    redacted_text = text
    stats = {"emails_redacted": 0, "secrets_redacted": 0}

    # Redact Emails
    emails = re.findall(email_pattern, redacted_text)
    if emails:
        stats["emails_redacted"] = len(emails)
        redacted_text = re.sub(email_pattern, "[REDACTED_EMAIL]", redacted_text)

    # Redact API Keys / Tokens
    secrets = re.findall(secret_key_pattern, redacted_text)
    if secrets:
        stats["secrets_redacted"] = len(secrets)
        redacted_text = re.sub(secret_key_pattern, r'\1: [REDACTED_SECRET]', redacted_text)

    return redacted_text, stats


def log_transformation_audit_event(
    source_file: str,
    source_hash: str,
    operator_config: Dict[str, Any],
    verification_score: float,
    status: str
) -> Dict[str, Any]:
    """
    Writes an immutable, structured audit entry into the local system log.
    """
    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source_file": source_file,
        "source_sha256": source_hash,
        "operator_config": operator_config,
        "fact_preservation_score": verification_score,
        "status": status
    }

    logger.info(
        f"AUDIT_EVENT | File: {source_file} | Hash: {source_hash[:12]}... | "
        f"Score: {verification_score}% | Status: {status}"
    )

    return event