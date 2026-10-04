import re
from typing import Dict, Any, List

class FactExtractor:
    CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
    CVSS_VECTOR_PATTERN = re.compile(r"CVSS:3\.[01]/[A-Z0-9/:]+", re.IGNORECASE)
    CVSS_SCORE_PATTERN = re.compile(r"\b(?:10(?:\.0)?|[0-9]\.[0-9])\b")
    SEVERITY_PATTERN = re.compile(r"\b(CRITICAL|HIGH|MEDIUM|LOW)\b", re.IGNORECASE)
    
    IPV4_PATTERN = re.compile(r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b")
    SHA256_PATTERN = re.compile(r"\b[a-fA-F0-9]{64}\b")
    SHA1_PATTERN = re.compile(r"\b[a-fA-F0-9]{40}\b")
    MD5_PATTERN = re.compile(r"\b[a-fA-F0-9]{32}\b")
    URL_PATTERN = re.compile(r"https?://[^\s<>'\"{}|\\^`]+[a-zA-Z0-9/]")
    DOMAIN_PATTERN = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+(?:com|org|net|gov|edu|mil|io|in|co|info|biz|net|xyz)\b", re.IGNORECASE)
    
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")

    @classmethod
    def extract_facts(cls, text: str) -> Dict[str, Any]:
        """
        Deterministic regex extraction for strongly structured identifiers.
        Preserves uncertainty for arbitrary product and version mentions.
        """
        # 1. Strongly structured identifiers
        cves = sorted(list(set(m.upper() for m in cls.CVE_PATTERN.findall(text))))
        
        cvss_vectors = cls.CVSS_VECTOR_PATTERN.findall(text)
        cvss_scores = []
        if cvss_vectors:
            cvss_scores.append(cvss_vectors[0])
        else:
            # Match numeric scores if in vicinity of 'cvss'
            for line in text.splitlines():
                if "cvss" in line.lower():
                    matches = cls.CVSS_SCORE_PATTERN.findall(line)
                    if matches:
                        cvss_scores.extend(matches)
        cvss_scores = sorted(list(set(cvss_scores)))

        # Severity
        severity = "UNKNOWN"
        for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            if re.search(rf"\b{s}\b", text, re.IGNORECASE):
                severity = s
                break

        # IPs (filter out 127.0.0.1 or 0.0.0.0 if not useful)
        raw_ips = cls.IPV4_PATTERN.findall(text)
        ips = sorted(list(set(ip for ip in raw_ips if ip not in ("0.0.0.0", "127.0.0.1", "255.255.255.255"))))

        # Hashes (prioritize SHA256 over MD5 to avoid substring overlaps)
        sha256_hashes = cls.SHA256_PATTERN.findall(text)
        text_without_sha256 = cls.SHA256_PATTERN.sub(" ", text)
        sha1_hashes = cls.SHA1_PATTERN.findall(text_without_sha256)
        text_without_sha1 = cls.SHA1_PATTERN.sub(" ", text_without_sha256)
        md5_hashes = cls.MD5_PATTERN.findall(text_without_sha1)
        all_hashes = sorted(list(set(sha256_hashes + sha1_hashes + md5_hashes)))

        # URLs & Domains
        urls = sorted(list(set(cls.URL_PATTERN.findall(text))))
        raw_domains = cls.DOMAIN_PATTERN.findall(text)
        # Exclude domain parts that already match urls
        domains = sorted(list(set(d.lower() for d in raw_domains if not any(d in u for u in urls))))

        # 2. Candidate products and versions (preserves uncertainty)
        candidate_products: List[Dict[str, Any]] = []
        candidate_versions: List[Dict[str, Any]] = []

        product_keywords = ["affected product", "affected software", "product:", "software:"]
        version_keywords = ["affected version", "affected versions", "version range", "versions:"]

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for i, line in enumerate(lines):
            line_lower = line.lower()
            for kw in product_keywords:
                if kw in line_lower:
                    val = line.split(":", 1)[-1].strip() if ":" in line else line
                    if val and len(val) < 120:
                        candidate_products.append({
                            "name": val,
                            "confidence": "candidate",
                            "line": line
                        })
            for kw in version_keywords:
                if kw in line_lower:
                    val = line.split(":", 1)[-1].strip() if ":" in line else line
                    if val and len(val) < 80:
                        candidate_versions.append({
                            "version": val,
                            "confidence": "candidate",
                            "line": line
                        })

        # 3. DLP / Sensitive Information scan
        dlp_findings: List[Dict[str, Any]] = []
        emails = cls.EMAIL_PATTERN.findall(text)
        for email in set(emails):
            dlp_findings.append({
                "type": "personal_email",
                "value": email,
                "classification": "sensitive",
                "note": "Potential personal identifier detected; verify if required for contact reference."
            })

        if cls.PRIVATE_KEY_PATTERN.search(text):
            dlp_findings.append({
                "type": "private_key",
                "value": "[REDACTED_PRIVATE_KEY_HEADER]",
                "classification": "restricted",
                "note": "Cryptographic private key block identified in source material."
            })

        return {
            "cve_ids": cves,
            "cvss_scores": cvss_scores,
            "severity": severity,
            "ips": ips,
            "hashes": all_hashes,
            "urls": urls,
            "domains": domains,
            "candidate_products": candidate_products,
            "candidate_versions": candidate_versions,
            "dlp_findings": dlp_findings,
        }
