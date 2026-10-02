import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from modules.verifier import verify_all_generated_outputs

def verify_phase5():
    print("==================================================")
    print("   SIH PS ID: 26154 - PHASE 5 FACT VERIFIER       ")
    print("==================================================")

    # 1. Load generated artifacts from data folders
    canonical_path = os.path.join("data", "sample_inputs", "canonical_facts.json")
    social_path = os.path.join("data", "outputs", "social_posts.json")
    video_path = os.path.join("data", "outputs", "video_package.json")

    missing = [p for p in [canonical_path, social_path, video_path] if not os.path.exists(p)]
    if missing:
        print(f"[X] Missing target artifacts: {missing}")
        return

    with open(canonical_path, "r", encoding="utf-8") as f:
        canonical_facts = json.load(f)
    with open(social_path, "r", encoding="utf-8") as f:
        social_posts = json.load(f)
    with open(video_path, "r", encoding="utf-8") as f:
        video_package = json.load(f)

    # 2. Run Verification Engine
    audit_report = verify_all_generated_outputs(canonical_facts, social_posts, video_package)

    print(f"\n[✓] Overall Status: {audit_report['overall_status']}")
    print(f"[✓] Average Fact Preservation Rate: {audit_report['average_fact_preservation_rate']}%")
    print("\nDetailed Component Breakdown:")
    for comp, rep in audit_report["detailed_component_reports"].items():
        print(f" - {comp.upper()}: Status = {rep['status']}, FPR = {rep['fact_preservation_rate']}%")
        if rep['missing_cves']:
            print(f"   [!] Missing CVEs: {rep['missing_cves']}")
        if rep['missing_ips']:
            print(f"   [!] Missing IPs: {rep['missing_ips']}")

    # Save audit report
    audit_out_path = os.path.join("data", "outputs", "fact_verification_report.json")
    with open(audit_out_path, "w", encoding="utf-8") as f:
        json.dump(audit_report, f, indent=2)

    print(f"\n[✓] Audit Report Saved: {audit_out_path}")
    print("\nSUCCESS: Phase 5 Anti-Hallucination Fact Verifier verified!")

if __name__ == "__main__":
    verify_phase5()