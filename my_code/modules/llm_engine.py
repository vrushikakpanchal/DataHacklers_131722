import json
import ollama
from pydantic import BaseModel, Field
from typing import Dict, Any, List

# 1. Define Strict Pydantic Output Schema
class CanonicalFacts(BaseModel):
    title: str = Field(description="Official title or brief designation of the threat/advisory")
    severity: str = Field(description="Overall severity rating (CRITICAL, HIGH, MEDIUM, LOW)")
    cve_ids: List[str] = Field(description="List of CVE IDs identified in the text")
    affected_systems: List[str] = Field(description="Affected software, versions, or infrastructure")
    summary: str = Field(description="A concise 2-3 sentence technical summary of the threat")
    recommended_actions: List[str] = Field(description="Key mitigation or remediation steps")


def extract_canonical_facts(raw_text: str, locked_params: Dict[str, Any], model_name: str = "qwen2.5:3b") -> Dict[str, Any]:
    """
    Passes raw text and locked parameters to local Ollama model to generate
    a strictly typed CanonicalFacts JSON object.
    """
    prompt = f"""
You are an expert cybersecurity intelligence analyst.
Analyze the following security document and extract the structured canonical facts.

LOCKED DETERMINISTIC PARAMETERS (Do NOT omit or alter these):
- Locked CVE IDs: {locked_params.get('locked_cves', [])}
- Locked IP Addresses: {locked_params.get('locked_ips', [])}
- Locked Severity Ratings: {locked_params.get('locked_severities', [])}

SOURCE DOCUMENT TEXT:
{raw_text[:3000]}

Extract the facts strictly according to the requested JSON schema.
Ensure all locked CVE IDs are included in the cve_ids list.
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
    
    return result_dict