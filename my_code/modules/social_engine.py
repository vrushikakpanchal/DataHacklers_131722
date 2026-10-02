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
from modules.generators import generate_social_content, select_social_strategy
from pallavi_code.validator import validate_content


def process_social_transformation(
    canonical_facts: Dict[str, Any] | str,
    settings: Dict[str, Any] | None = None,
    platform: str = "both",
    tone: str | None = None,
    target_audience: str | None = None,
    detail_level: str | None = None,
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

    settings = dict(settings or {})
    settings.setdefault("objective", "Inform and Mitigate")
    settings.setdefault("language", "English")
    settings["audience"] = (
        target_audience
        if target_audience is not None
        else settings.get("audience", "Leadership & Technical Teams")
    )
    operator_tone = (
        tone if tone is not None else settings.get("tone", "Executive / Formal")
    )
    settings["operator_tone"] = operator_tone
    settings["detail"] = (
        detail_level if detail_level is not None else settings.get("detail", "High")
    )

    # Keep the extracted facts intact while adding names accepted by the
    # teammate generator's source-facts schema.
    generator_facts = dict(canonical_facts)
    if "affected_products" not in generator_facts and "affected_systems" in generator_facts:
        generator_facts["affected_products"] = generator_facts["affected_systems"]
    if "recommendations" not in generator_facts and "recommended_actions" in generator_facts:
        generator_facts["recommendations"] = generator_facts["recommended_actions"]
    if "references" not in generator_facts and generator_facts.get("cve_ids"):
        generator_facts["references"] = generator_facts["cve_ids"]

    strategy = select_social_strategy(generator_facts, settings)
    settings["content_archetype"] = strategy["content_archetype"]
    settings["tone"] = strategy["target_tone"]
    generated_posts = generate_social_content(
        generator_facts,
        model_name="qwen2.5:3b",
        strategy=strategy,
        settings=settings,
        platform=platform,
    )
    facts_used = generator_facts

    # Prepare payload expected by Pallavi's validate_content function
    result_payload = {
        "facts": facts_used,
        "linkedin": generated_posts.get("linkedin_post", generated_posts.get("linkedin", "")),
        "x_post": generated_posts.get("x_post", ""),
        "x_thread": generated_posts.get("x_thread", generated_posts.get("twitter_thread", [])),
    }

    # Execute deterministic validation check
    validation_results = validate_content(
        result=result_payload,
        platform=platform,
        grounding=None,
    )

    return {
        "posts": {
            "linkedin_post": result_payload["linkedin"],
            "linkedin": result_payload["linkedin"],
            "x_post": result_payload["x_post"],
            "x_thread": result_payload["x_thread"],
        },
        "validation": validation_results,
    }


def generate_social_posts(
    canonical_facts: Dict[str, Any] | str,
    settings: Dict[str, Any] | None = None,
    platform: str = "both",
    tone: str | None = None,
    target_audience: str | None = None,
    detail_level: str | None = None,
) -> Dict[str, Any]:
    """
    Wrapper function matching the function name imported by app.py.
    """
    return process_social_transformation(
        canonical_facts=canonical_facts,
        settings=settings,
        platform=platform,
        tone=tone,
        target_audience=target_audience,
        detail_level=detail_level,
    )
