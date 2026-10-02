import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from modules.extractor import process_and_lock_document

def verify_phase2():
    print("==================================================")
    print("   SIH PS ID: 26154 - PHASE 2 INGESTION & LOCKER  ")
    print("==================================================")
    
    sample_file = os.path.join("data", "sample_inputs", "sample_advisory.txt")
    
    if not os.path.exists(sample_file):
        print(f"[X] Missing sample file at: {sample_file}")
        return

    result = process_and_lock_document(sample_file)
    locked = result["locked_parameters"]

    print(f"[✓] File Processed: {result['source_file']}")
    print(f"[✓] Character Count: {locked['character_count']}")
    print(f"[✓] Locked CVEs: {locked['locked_cves']}")
    print(f"[✓] Locked IPs: {locked['locked_ips']}")
    print(f"[✓] Locked Severities: {locked['locked_severities']}")

    # Validation Assertions
    assert "CVE-2026-1234" in locked["locked_cves"], "CVE-2026-1234 extraction failed"
    assert "CVE-2026-5678" in locked["locked_cves"], "CVE-2026-5678 extraction failed"
    assert "192.168.1.105" in locked["locked_ips"], "IP 192.168.1.105 extraction failed"
    assert "CRITICAL" in locked["locked_severities"], "Severity extraction failed"

    print("\nSUCCESS: Phase 2 Ingestion and Deterministic Locker verified!")

if __name__ == "__main__":
    verify_phase2()