import re
import json
from typing import Dict, Any, List

def verify_content_against_facts(content_str: str, locked_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scans a generated content string to verify that all locked technical indicators
    (CVEs, IPs, Severities) are present and preserved.
    """
    required_cves = set(locked_params.get("locked_cves", []))
    required_ips = set(locked_params.get("locked_ips", []))
    required_severities = set(locked_params.get("locked_severities", []))

    # Search content string for locked facts
    found_cves = {cve for cve in required_cves if cve.lower() in content_str.lower()}
    found_ips = {ip for ip in required_ips if ip in content_str}
    found_severities = {sev for sev in required_severities if sev.lower() in content_str.lower()}

    # Calculate missing items
    missing_cves = list(required_cves - found_cves)
    missing_ips = list(required_ips - found_ips)
    missing_severities = list(required_severities - found_severities)

    total_indicators = len(required_cves) + len(required_ips) + len(required_severities)
    preserved_indicators = len(found_cves) + len(found_ips) + len(found_severities)

    fpr_score = (preserved_indicators / total_indicators * 100.0) if total_indicators > 0 else 100.0
    passed = len(missing_cves) == 0 and len(missing_ips) == 0

    return {
        "status": "PASS" if passed else "WARN_MISSING_FACTS",
        "fact_preservation_rate": round(fpr_score, 2),
        "total_locked_indicators": total_indicators,
        "preserved_indicators": preserved_indicators,
        "missing_cves": missing_cves,
        "missing_ips": missing_ips,
        "missing_severities": missing_severities
    }


def verify_all_generated_outputs(
    canonical_facts: Dict[str, Any],
    social_posts: Dict[str, Any],
    video_package: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Cross-checks canonical facts, social posts, and video script outputs against locked indicators.
    """
    locked_params = {
        "locked_cves": canonical_facts.get("cve_ids", []),
        "locked_ips": canonical_facts.get("locked_ips", []),
        "locked_severities": [canonical_facts.get("severity", "")]
    }

    results = {
        "canonical_facts": verify_content_against_facts(json.dumps(canonical_facts), locked_params),
        "social_posts": verify_content_against_facts(json.dumps(social_posts), locked_params),
        "video_package": verify_content_against_facts(json.dumps(video_package), locked_params)
    }

    # Aggregate overall status
    all_passed = all(r["status"] == "PASS" for r in results.values())
    avg_fpr = sum(r["fact_preservation_rate"] for r in results.values()) / len(results)

    return {
        "overall_status": "VERIFIED_FACTUALLY_CONSISTENT" if all_passed else "FLAGGED_FOR_REVIEW",
        "average_fact_preservation_rate": round(avg_fpr, 2),
        "detailed_component_reports": results
    }