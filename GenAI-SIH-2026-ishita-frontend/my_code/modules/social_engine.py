"""
Social Engine Adapter
Integrates Pallavi's local Ollama social generator & validator into the main pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Path configuration for external module imports
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PALLAVI_DIR = PROJECT_ROOT / "pallavi_code"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

if str(PALLAVI_DIR) not in sys.path:
    sys.path.append(str(PALLAVI_DIR))

# Import directly from Pallavi's generator and validator
from pallavi_code.generator import (
    generate_content,
    generate_social_content,
    extract_source_facts,
)
from pallavi_code.validator import validate_content


def process_social_transformation(
    canonical_facts: Dict[str, Any] | str,
    settings: Dict[str, Any] | None = None,
    platform: str = "both",
) -> Dict[str, Any]:
    """
    Adapter function that receives canonical facts from my_code,
    formats settings, generates LinkedIn and X/Twitter content using
    Pallavi's generator, and validates output using Pallavi's validator.
    """
    if isinstance(canonical_facts, str):
        canonical_facts = {
            "title": "Security Advisory",
            "summary": canonical_facts,
            "severity": "HIGH",
        }

    if settings is None:
        settings = {
            "audience": "Leadership & Technical Teams",
            "tone": "Executive / Formal",
            "objective": "Inform and Mitigate",
            "language": "English",
            "detail": "High",
        }

    # Normalize canonical facts into a formatted text source if needed
    source_summary_text = f"""
Title: {canonical_facts.get('title', 'Security Advisory')}
Date: {canonical_facts.get('date', 'N/A')}
Source: {canonical_facts.get('source', 'Advisory Notice')}
Summary: {canonical_facts.get('summary', '')}
Vulnerability: {canonical_facts.get('vulnerability', '')}
Severity: {canonical_facts.get('severity', '')}
Impact: {canonical_facts.get('impact', '')}
Affected Products: {', '.join(canonical_facts.get('affected_products', canonical_facts.get('affected_systems', [])))}
Key Findings: {', '.join(canonical_facts.get('key_findings', []))}
Recommendations: {', '.join(canonical_facts.get('recommendations', canonical_facts.get('mitigation_steps', [])))}
Technical Details: {', '.join(canonical_facts.get('technical_details', []))}
    """.strip()

    try:
        # Generate LinkedIn & X posts from structured facts
        generated_posts = generate_social_content(
            facts=canonical_facts,
            settings=settings,
            platform=platform,
        )
        facts_used = canonical_facts
    except Exception:
        # Fallback to direct raw text extraction if structured facts mapping fails
        generated_posts = generate_content(
            source_text=source_summary_text,
            settings=settings,
            platform=platform,
        )
        facts_used = generated_posts.get("facts", canonical_facts)

    # Prepare payload expected by Pallavi's validate_content function
    result_payload = {
        "facts": facts_used,
        "linkedin": generated_posts.get("linkedin", ""),
        "x_thread": generated_posts.get("x_thread", []),
    }

    # Execute deterministic validation check
    validation_results = validate_content(
        result=result_payload,
        platform=platform,
        grounding=None,
    )

    return {
        "posts": {
            "linkedin": result_payload["linkedin"],
            "x_thread": result_payload["x_thread"],
        },
        "validation": validation_results,
    }


def generate_social_posts(
    canonical_facts: Dict[str, Any] | str,
    settings: Dict[str, Any] | None = None,
    platform: str = "both",
) -> Dict[str, Any]:
    """
    Wrapper function matching the function name imported by app.py.
    """
    return process_social_transformation(
        canonical_facts=canonical_facts,
        settings=settings,
        platform=platform,
    )