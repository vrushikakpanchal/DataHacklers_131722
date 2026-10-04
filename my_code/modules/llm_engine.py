import json
import ollama
from pydantic import BaseModel, Field
from typing import Dict, Any, List

# 1. Define Strict Pydantic Output Schema
class CanonicalFacts(BaseModel):
    title: str = Field(description="Official title or brief designation of the threat/advisory")
    severity: str = Field(description="Overall severity rating (CRITICAL, HIGH, MEDIUM, LOW)")
    cve_ids: List[str] = Field(description="List of CVE IDs identified in the text")
    affected_systems: List[str] = Field(
        description=(
            "Every platform, product, service, application, website, mobile app, software, "
            "hardware model, or named entity that the document explicitly states is affected, "
            "targeted, misused, or involved. Include brand names, website names, app names, "
            "social-media platforms, marketplaces, and service providers named in the text "
            "(e.g. Shaadi.com, Tinder, WhatsApp, UPI, Amazon). "
            "Do NOT invent names — only list what is explicitly written in the source text."
        )
    )
    summary: str = Field(description="A concise 2-3 sentence technical summary of the threat")
    recommended_actions: List[str] = Field(description="Key mitigation or remediation steps")


def extract_canonical_facts(raw_text: str, locked_params: Dict[str, Any], model_name: str = "qwen2.5:3b") -> Dict[str, Any]:
    """
    Passes raw text and locked parameters to local Ollama model to generate
    a strictly typed CanonicalFacts JSON object.
    """
    prompt = f"""
You are an expert security intelligence analyst.
Analyze the following security document and extract the structured canonical facts.

LOCKED DETERMINISTIC PARAMETERS (Do NOT omit or alter these):
- Locked CVE IDs: {locked_params.get('locked_cves', [])}
- Locked IP Addresses: {locked_params.get('locked_ips', [])}
- Locked Severity Ratings: {locked_params.get('locked_severities', [])}

SOURCE DOCUMENT TEXT:
{raw_text[:3000]}

EXTRACTION RULES:
1. For affected_systems: list EVERY platform, product, service, website, app, software, or named entity that the document explicitly states is affected, targeted, misused, or involved. This includes brand names (e.g. Shaadi.com, Tinder, WhatsApp, UPI, Google Pay), app names, social-media platforms, marketplaces, software products, hardware models, and service providers. Do NOT leave this list empty if any such names appear in the source text.
2. Ensure all locked CVE IDs are included in cve_ids.
3. Extract facts strictly from the source text — do not invent names, versions, or identifiers.
"""

    # Structured Output Request to Ollama using Pydantic JSON Schema
    response = ollama.chat(
        model=model_name,
        messages=[{'role': 'user', 'content': prompt}],
        format=CanonicalFacts.model_json_schema()
    )

    extracted_json_str = response['message']['content']
    
    # Parse and validate schema via Pydantic
    canonical_obj = CanonicalFacts.model_validate_json(extracted_json_str)
    
    # Convert to standard Python dictionary
    result_dict = canonical_obj.model_dump()

    # Attach locked IP addresses into canonical object
    result_dict["locked_ips"] = locked_params.get("locked_ips", [])

    # If the LLM returned no affected_systems, fall back to deterministically
    # extracted entity names so the field is never empty when named
    # platforms/products appear in the source text.
    if not result_dict.get("affected_systems") and locked_params.get("locked_entities"):
        result_dict["affected_systems"] = list(locked_params["locked_entities"])

    return result_dict