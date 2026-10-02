"""Fast deterministic checks for generated social-media content."""

from __future__ import annotations

import ipaddress
import re
from typing import Any, Optional


EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

IP_PATTERN = re.compile(
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
)

SECRET_PATTERN = re.compile(
    r"\b(?:password|passwd|api[_-]?key|secret|token|credential)"
    r"\s*[:=]\s*\S+",
    re.IGNORECASE,
)

KNOWN_KEY_PATTERN = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}"
    r"|AKIA[0-9A-Z]{12,}"
    r"|gh[pousr]_[A-Za-z0-9_]{20,})\b"
)

INTERNAL_HOST_PATTERN = re.compile(
    r"\b(?:localhost|[\w.-]+\.(?:internal|corp|local))\b",
    re.IGNORECASE,
)


def _masked(
    value: str,
    finding_type: str,
) -> str:
    if finding_type in {"SECRET", "API_KEY"}:
        return "[redacted]"

    if finding_type == "EMAIL":
        local, _, domain = value.partition("@")
        return f"{local[:1]}***@{domain}"

    return value


def _valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def find_sensitive_information(
    text: str,
) -> list[dict[str, str]]:
    """
    Finds obvious sensitive or internal-looking values.
    Values are masked in the validation output.
    """

    if not text:
        return []

    findings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_finding(
        finding_type: str,
        value: str,
        message: str,
    ) -> None:
        key = (finding_type, value)

        if key in seen:
            return

        findings.append(
            {
                "type": finding_type,
                "value": _masked(
                    value,
                    finding_type,
                ),
                "message": message,
            }
        )

        seen.add(key)

    for match in EMAIL_PATTERN.finditer(text):
        add_finding(
            "EMAIL",
            match.group(),
            "Email address detected.",
        )

    for match in IP_PATTERN.finditer(text):
        value = match.group()

        if _valid_ip(value):
            add_finding(
                "IP_ADDRESS",
                value,
                "IP address detected.",
            )

    for match in SECRET_PATTERN.finditer(text):
        add_finding(
            "SECRET",
            match.group(),
            "Possible credential or secret detected.",
        )

    for match in KNOWN_KEY_PATTERN.finditer(text):
        add_finding(
            "API_KEY",
            match.group(),
            "API-key-shaped value detected.",
        )

    for match in INTERNAL_HOST_PATTERN.finditer(text):
        add_finding(
            "INTERNAL_HOST",
            match.group(),
            "Internal-looking hostname detected.",
        )

    return findings


def validate_x_thread(
    thread: list[str],
) -> dict[str, Any]:
    """
    Checks each X post against the 280-character limit
    and checks for sensitive information.
    """

    if not thread:
        return {
            "valid": False,
            "status": "FLAG",
            "issues": ["X thread is empty."],
            "posts": [],
        }

    posts: list[dict[str, Any]] = []
    issues: list[str] = []

    for index, post in enumerate(thread, start=1):
        text = str(post or "").strip()
        post_issues: list[str] = []

        if not text:
            post_issues.append("Post is empty.")

        if len(text) > 280:
            post_issues.append(
                f"Post exceeds 280 characters by "
                f"{len(text) - 280}."
            )

        sensitive = find_sensitive_information(text)

        post_issues.extend(
            finding["message"]
            for finding in sensitive
        )

        if post_issues:
            issues.append(
                f"Post {index}: "
                + " ".join(post_issues)
            )

        posts.append(
            {
                "post_number": index,
                "length": len(text),
                "limit": 280,
                "status": (
                    "FLAG"
                    if post_issues
                    else "PASS"
                ),
                "issues": post_issues,
            }
        )

    return {
        "valid": not issues,
        "status": (
            "FLAG"
            if issues
            else "PASS"
        ),
        "issues": issues,
        "posts": posts,
    }


def validate_linkedin(
    post: str,
) -> dict[str, Any]:
    """
    Checks that LinkedIn content exists and has
    no obvious sensitive information.
    """

    issues: list[str] = []

    if not post or not post.strip():
        issues.append(
            "LinkedIn post is empty."
        )

    issues.extend(
        finding["message"]
        for finding in find_sensitive_information(post)
    )

    return {
        "valid": not issues,
        "status": (
            "FLAG"
            if issues
            else "PASS"
        ),
        "issues": issues,
    }


def validate_source_facts(
    facts: dict[str, Any],
) -> dict[str, Any]:
    """
    Ensures that useful facts were extracted.
    """

    meaningful_values = [
        facts.get("title"),
        facts.get("summary"),
        facts.get("vulnerability"),
        facts.get("impact"),
        facts.get("affected_products"),
        facts.get("recommendations"),
    ]

    if facts and any(meaningful_values):
        issues: list[str] = []
    else:
        issues = [
            "No useful source facts were extracted."
        ]

    return {
        "valid": not issues,
        "status": (
            "FLAG"
            if issues
            else "PASS"
        ),
        "issues": issues,
    }


def validate_content(
    result: dict[str, Any],
    platform: str = "both",
    grounding: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Validates only the platforms requested by the user.

    This function intentionally accepts all three arguments
    used by app.py:
        result
        platform
        grounding
    """

    selected_platform = (
        platform.lower().strip()
    )

    facts = result.get("facts") or {}
    linkedin = result.get("linkedin", "")
    x_thread = result.get("x_thread") or []

    facts_validation = validate_source_facts(
        facts
    )

    if selected_platform in {
        "linkedin",
        "both",
    }:
        linkedin_validation = validate_linkedin(
            linkedin
        )
    else:
        linkedin_validation = {
            "valid": True,
            "status": "SKIP",
            "issues": ["Not requested."],
        }

    if selected_platform in {
        "x",
        "both",
    }:
        x_validation = validate_x_thread(
            x_thread
        )
    else:
        x_validation = {
            "valid": True,
            "status": "SKIP",
            "issues": ["Not requested."],
        }

    checks = [
        facts_validation,
        linkedin_validation,
        x_validation,
    ]

    if grounding is not None:
        grounding_status = grounding.get(
            "status",
            "FLAG",
        )

        grounding_validation = {
            "valid": grounding_status == "PASS",
            "status": grounding_status,
            "issues": grounding.get(
                "unsupported_claims",
                [],
            ),
        }

        checks.append(grounding_validation)

    overall_valid = all(
        check["valid"]
        for check in checks
    )

    return {
        "valid": overall_valid,
        "status": (
            "PASS"
            if overall_valid
            else "FLAG"
        ),
        "facts": facts_validation,
        "linkedin": linkedin_validation,
        "x_thread": x_validation,
        "grounding": grounding,
    }