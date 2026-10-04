from typing import Dict, Any, List
from app.schemas.output import SecurityAdvisorySchema
from app.models.source import LockedFact

class AdvisoryValidator:
    @staticmethod
    def validate_against_locked_facts(
        advisory: SecurityAdvisorySchema,
        locked_fact: LockedFact
    ) -> Dict[str, Any]:
        """
        Cross-validates AI generated advisory against locked source facts.
        Flags any technical identifier present in the advisory that does not exist in locked facts.
        """
        source_cves = set(c.upper() for c in (locked_fact.cve_ids or []))
        source_ips = set(locked_fact.ips or [])
        source_hashes = set(h.lower() for h in (locked_fact.hashes or []))
        source_urls = set(locked_fact.urls or [])
        source_domains = set(d.lower() for d in (locked_fact.domains or []))

        # Check CVEs
        advisory_cves = set(c.upper() for c in (advisory.cve_ids or []))
        # Also check single 'cve' if set
        if hasattr(advisory, "cve") and advisory.cve:
            advisory_cves.add(advisory.cve.upper())
            
        unverified_cves = [c for c in advisory_cves if c not in source_cves]

        # Check indicators (IPs, hashes, domains)
        unverified_ips = []
        unverified_hashes = []
        verified_indicators = []
        unverified_indicators = []

        for ind in advisory.indicators:
            ind_clean = ind.strip()
            # Is it an IP?
            if any(char.isdigit() for char in ind_clean) and "." in ind_clean and not ind_clean.startswith("http"):
                if ind_clean in source_ips:
                    verified_indicators.append(ind_clean)
                else:
                    unverified_ips.append(ind_clean)
                    unverified_indicators.append(ind_clean)
            # Is it a hash?
            elif len(ind_clean) in (32, 40, 64) and all(c in "0123456789abcdefABCDEF" for c in ind_clean):
                if ind_clean.lower() in source_hashes:
                    verified_indicators.append(ind_clean)
                else:
                    unverified_hashes.append(ind_clean)
                    unverified_indicators.append(ind_clean)
            else:
                # URL or domain
                matched = any(ind_clean in u for u in source_urls) or any(ind_clean in d for d in source_domains)
                if matched:
                    verified_indicators.append(ind_clean)
                else:
                    unverified_indicators.append(ind_clean)

        has_discrepancies = bool(unverified_cves or unverified_ips or unverified_hashes)

        findings: List[str] = []
        if unverified_cves:
            findings.append(f"AI generated CVE(s) not found in verified source facts: {', '.join(unverified_cves)}")
        if unverified_ips:
            findings.append(f"AI generated IP indicator(s) not in source telemetry: {', '.join(unverified_ips)}")
        if unverified_hashes:
            findings.append(f"AI generated file hash(es) not present in source facts: {', '.join(unverified_hashes)}")

        return {
            "status": "discrepancies_flagged" if has_discrepancies else "valid",
            "has_discrepancies": has_discrepancies,
            "unverified_cves": unverified_cves,
            "unverified_ips": unverified_ips,
            "unverified_hashes": unverified_hashes,
            "verified_indicators": verified_indicators,
            "unverified_indicators": unverified_indicators,
            "findings": findings
        }
