import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from modules.security import compute_sha256, redact_sensitive_pii, log_transformation_audit_event

def verify_phase6():
    print("==================================================")
    print("   SIH PS ID: 26154 - PHASE 6 SECURITY & AUDIT    ")
    print("==================================================")

    # Test Sample Text with Sensitive Data
    sensitive_sample = """
    CERT-In Incident Report.
    Contact Lead: analyst.john@ntro.gov.in
    System Auth API Key: api_key = "secret_token_abc1234567890xyz"
    Vulnerability details: CVE-2026-1234 active on 192.168.1.105.
    """

    # 1. Test SHA-256 Computation
    content_hash = compute_sha256(sensitive_sample)
    print(f"[✓] SHA-256 Digest Computed: {content_hash}")
    assert len(content_hash) == 64, "SHA-256 Hash length invalid"

    # 2. Test Redaction
    clean_text, redaction_stats = redact_sensitive_pii(sensitive_sample)
    print(f"[✓] PII Redaction Complete: {redaction_stats}")
    print("\nSanitized Sample Snippet:")
    print("--------------------------------------------------")
    print(clean_text.strip())
    print("--------------------------------------------------")

    assert "[REDACTED_EMAIL]" in clean_text, "Email redaction failed"
    assert "[REDACTED_SECRET]" in clean_text, "API key redaction failed"

    # 3. Test Audit Event Logging
    audit_event = log_transformation_audit_event(
        source_file="sample_advisory.txt",
        source_hash=content_hash,
        operator_config={"tone": "Professional", "detail": "High"},
        verification_score=80.0,
        status="FLAGGED_FOR_REVIEW"
    )

    audit_log_path = os.path.join("data", "outputs", "audit.log")
    assert os.path.exists(audit_log_path), "Audit log file missing"
    print(f"[✓] Audit Trail Entry Written to: {audit_log_path}")

    print("\nSUCCESS: Phase 6 Local Security & Auditability verified!")

if __name__ == "__main__":
    verify_phase6()