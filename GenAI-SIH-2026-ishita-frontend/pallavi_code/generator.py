"""Fast, source-grounded generation through the local Ollama HTTP API."""

from __future__ import annotations

import json
import os
import re
from json import JSONDecodeError
from typing import Any, Optional

import requests


DEFAULT_MODEL = "qwen2.5:1.5b"

OLLAMA_HOST = os.getenv(
    "OLLAMA_HOST",
    "http://127.0.0.1:11434",
).rstrip("/")

MODEL_NAME = os.getenv(
    "OLLAMA_MODEL",
    DEFAULT_MODEL,
)

OLLAMA_TIMEOUT_SECONDS = float(
    os.getenv(
        "OLLAMA_TIMEOUT_SECONDS",
        "180",
    )
)

MAX_SOURCE_CHARS = int(
    os.getenv(
        "SMC_MAX_SOURCE_CHARS",
        "28000",
    )
)


FACT_FIELDS = (
    "title",
    "date",
    "source",
    "summary",
    "vulnerability",
    "affected_products",
    "key_findings",
    "severity",
    "impact",
    "recommendations",
    "technical_details",
    "references",
)

LIST_FIELDS = {
    "affected_products",
    "key_findings",
    "recommendations",
    "technical_details",
    "references",
}


class OllamaError(RuntimeError):
    """Ollama connection or model error."""


class ModelResponseError(RuntimeError):
    """Ollama returned an invalid or incomplete response."""


def clean_response(
    text: str,
) -> str:
    """Remove common model wrappers."""

    cleaned = (text or "").strip()

    if "</think>" in cleaned:
        cleaned = cleaned.split(
            "</think>",
            1,
        )[1].strip()

    cleaned = cleaned.replace(
        "<think>",
        "",
    ).strip()

    cleaned = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```\s*$",
        "",
        cleaned,
    )

    return cleaned.strip()


def _friendly_ollama_error(
    response: requests.Response,
) -> str:
    body = response.text.strip()

    if (
        response.status_code == 404
        and "model" in body.lower()
    ):
        return (
            f"Ollama does not have model '{MODEL_NAME}'. "
            f"Run: ollama pull {MODEL_NAME}"
        )

    if body:
        return (
            f"Ollama returned HTTP "
            f"{response.status_code}: {body[:300]}"
        )

    return (
        f"Ollama returned HTTP "
        f"{response.status_code}."
    )


def call_ollama(
    prompt: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 500,
    expect_json: bool = False,
) -> str:
    """Call Ollama once."""

    payload: dict[str, Any] = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "10m",
        "think": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": 4096,
        },
    }

    if expect_json:
        payload["format"] = "json"

    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=(
                5,
                OLLAMA_TIMEOUT_SECONDS,
            ),
        )

        response.raise_for_status()

    except requests.ConnectionError as exc:
        raise OllamaError(
            f"Could not connect to Ollama at "
            f"{OLLAMA_HOST}. Start Ollama or run "
            "'ollama serve'."
        ) from exc

    except requests.Timeout as exc:
        raise OllamaError(
            f"Ollama did not finish within "
            f"{OLLAMA_TIMEOUT_SECONDS:g} seconds. "
            "Try a smaller model or increase "
            "OLLAMA_TIMEOUT_SECONDS."
        ) from exc

    except requests.HTTPError as exc:
        raise OllamaError(
            _friendly_ollama_error(response)
        ) from exc

    except requests.RequestException as exc:
        raise OllamaError(
            f"Ollama request failed: {exc}"
        ) from exc

    try:
        data = response.json()

    except ValueError as exc:
        raise OllamaError(
            "Ollama returned an invalid HTTP response."
        ) from exc

    text = data.get("response")

    if not isinstance(text, str) or not text.strip():
        raise ModelResponseError(
            "Ollama returned an empty model response."
        )

    return clean_response(text)


def extract_json(
    text: str,
) -> Optional[dict[str, Any]]:
    """Extract one JSON object from a model response."""

    cleaned = clean_response(text)

    if not cleaned:
        return None

    decoder = json.JSONDecoder()

    for index, character in enumerate(cleaned):
        if character != "{":
            continue

        try:
            value, _ = decoder.raw_decode(
                cleaned[index:]
            )

        except JSONDecodeError:
            continue

        if isinstance(value, dict):
            return value

    return None


def _require_json(
    text: str,
    label: str,
) -> dict[str, Any]:
    parsed = extract_json(text)

    if parsed is None:
        raise ModelResponseError(
            f"Ollama returned invalid JSON for "
            f"{label}. Try the recommended model."
        )

    return parsed


def _as_text(
    value: Any,
) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    return str(value).strip()


def _as_list(
    value: Any,
) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [
            _as_text(item)
            for item in value
            if _as_text(item)
        ]

    if isinstance(value, str) and value.strip():
        return [value.strip()]

    return []

def _extract_x_thread(
    value: Any,
) -> list[str]:
    """
    Accept the common key names that small local models
    may return for an X thread.
    """

    if not isinstance(value, dict):
        return []

    for key in (
        "x_thread",
        "thread",
        "posts",
        "x",
    ):
        posts = _as_list(
            value.get(key)
        )

        if posts:
            return posts

    return []

def normalize_facts(
    raw_facts: dict[str, Any],
) -> dict[str, Any]:
    """Return a predictable source-facts schema."""

    facts: dict[str, Any] = {}

    for field in FACT_FIELDS:
        if field in LIST_FIELDS:
            facts[field] = _as_list(
                raw_facts.get(field)
            )
        else:
            facts[field] = _as_text(
                raw_facts.get(field)
            )

    return facts


def _source_for_prompt(
    source_text: str,
) -> str:
    """Keep large documents within the model context."""

    if len(source_text) <= MAX_SOURCE_CHARS:
        return source_text

    first_size = int(
        MAX_SOURCE_CHARS * 0.68
    )

    last_size = (
        MAX_SOURCE_CHARS
        - first_size
    )

    return (
        source_text[:first_size]
        + "\n\n[Middle of source omitted "
        "to fit the local model context.]\n\n"
        + source_text[-last_size:]
    )


def extract_source_facts(
    source_text: str,
) -> dict[str, Any]:
    """Extract structured facts from the source document."""

    if not source_text or not source_text.strip():
        raise ValueError(
            "Cannot extract facts from an empty source."
        )

    schema = {
        "title": "",
        "date": "",
        "source": "",
        "summary": "",
        "vulnerability": "",
        "affected_products": [],
        "key_findings": [],
        "severity": "",
        "impact": "",
        "recommendations": [],
        "technical_details": [],
        "references": [],
    }

    prompt = f"""
You extract source facts for a social-media editor.

Use ONLY the document.
Never guess, infer, exaggerate, or fill missing facts.

Return ONLY valid JSON matching this schema.
Use empty strings or empty arrays when information is absent.

Preserve exact:
- Names
- Dates
- CVEs
- Product versions
- Severity wording
- Recommendations
- Technical details

SCHEMA:
{json.dumps(schema, ensure_ascii=False)}

DOCUMENT:
{_source_for_prompt(source_text)}
"""

    response = call_ollama(
        prompt,
        temperature=0.0,
        max_tokens=650,
        expect_json=True,
    )

    return normalize_facts(
        _require_json(
            response,
            "source facts",
        )
    )


def _settings_text(
    settings: dict[str, Any],
) -> str:
    return "\n".join(
        [
            f"Audience: {settings.get('audience', 'General public')}",
            f"Tone: {settings.get('tone', 'Professional')}",
            f"Objective: {settings.get('objective', 'Inform')}",
            f"Language: {settings.get('language', 'English')}",
            f"Detail: {settings.get('detail', 'Medium')}",
        ]
    )


def _build_linkedin_post(
    value: Any,
) -> str:
    """
    Build a consistent LinkedIn post from
    structured model sections.
    """

    if isinstance(value, str):
        return value.strip()

    if not isinstance(value, dict):
        return ""

    headline = _as_text(
        value.get("headline")
    )

    opening = _as_text(
        value.get("opening")
    )

    highlights = _as_list(
        value.get("key_highlights")
        or value.get("highlights")
    )

    recommendation = _as_text(
        value.get("recommendation")
    )

    hashtags = _as_list(
        value.get("hashtags")
    )

    sections: list[str] = []

    if headline:
        sections.append(headline)

    if opening:
        sections.append(opening)

    if highlights:
        sections.append(
            "Key highlights:\n"
            + "\n".join(
                f"• {item}"
                for item in highlights
            )
        )

    if recommendation:
        sections.append(recommendation)

    if hashtags:
        clean_hashtags = []

        for hashtag in hashtags:
            hashtag = hashtag.strip()

            if hashtag and not hashtag.startswith("#"):
                hashtag = f"#{hashtag}"

            if hashtag:
                clean_hashtags.append(hashtag)

        if clean_hashtags:
            sections.append(
                " ".join(clean_hashtags)
            )

    return "\n\n".join(
        sections
    ).strip()

def _recover_x_thread(
    facts: dict[str, Any],
    settings: dict[str, Any],
) -> list[str]:
    """
    Retry X generation with a simpler JSON structure.

    This is used when a combined LinkedIn + X request
    returns LinkedIn content but no X thread.
    """

    schema = {
        "x_thread": []
    }

    prompt = f"""
Create an X/Twitter thread using ONLY the structured facts below.

Do not invent:
- Facts
- Dates
- Products
- CVEs
- Statistics
- Recommendations

Return ONLY valid JSON with exactly one key:

{{
  "x_thread": []
}}

The value of x_thread must be an array of 2 to 5 separate strings.

Do not number the strings.
Keep every string at or below 250 characters.

Use a clear first post, useful facts in the middle,
and a supported recommendation in the final post when one exists.

SETTINGS:
{_settings_text(settings)}

OUTPUT SCHEMA:
{json.dumps(schema, ensure_ascii=False)}

STRUCTURED SOURCE FACTS:
{json.dumps(
    normalize_facts(facts),
    ensure_ascii=False,
)}
"""

    response = call_ollama(
        prompt,
        temperature=0.1,
        max_tokens=500,
        expect_json=True,
    )

    parsed = _require_json(
        response,
        "X thread recovery",
    )

    return _extract_x_thread(parsed)

def generate_social_content(
    facts: dict[str, Any],
    settings: dict[str, Any],
    platform: str = "both",
) -> dict[str, Any]:
    """Generate one or both platform outputs."""

    selected = platform.lower().strip()

    if selected not in {
        "linkedin",
        "x",
        "both",
    }:
        raise ValueError(
            "Platform must be linkedin, x, or both."
        )

    schema: dict[str, Any] = {}

    if selected in {
        "linkedin",
        "both",
    }:
        schema["linkedin"] = {
            "headline": "",
            "opening": "",
            "key_highlights": [],
            "recommendation": "",
            "hashtags": [],
        }

    if selected in {
        "x",
        "both",
    }:
        schema["x_thread"] = []

    prompt = f"""
You are a careful social-media editor.

Use ONLY the structured source facts below.

Do not invent:
- Facts
- Dates
- Statistics
- CVEs
- Products
- Exploitation status
- Recommendations
- Unsupported claims

If a fact is missing, leave it out.

SETTINGS:
{_settings_text(settings)}

RULES:

- LinkedIn must look ready for a professional cybersecurity page.
- LinkedIn must use this structure:
  1. A concise headline in one line. It may start with one relevant emoji.
  2. An opening paragraph of two or three clear sentences explaining what
     happened and why it matters.
  3. Three to five concise key highlights using exact names, products,
     versions, severity, identifiers, or impacts present in the facts.
  4. A short recommendation paragraph only when the source provides one.
  5. Three to five relevant hashtags based only on the source topic.
- Do not write labels such as "Headline:" or "Opening:" inside the post.
- Use the exact label "Key highlights:" before the bullet list.
- Keep the tone informative, direct, and trustworthy.
- Do not use hype.
- LinkedIn fields must be returned as structured JSON.
- X thread items must be separate strings with no numbering.
- Every X item must be at most 250 characters.
- Include a call to action only when supported by recommendations.
- Do not include unsupported hashtags.
- Do not expose secrets or personal data.

REQUESTED OUTPUT SCHEMA:
{json.dumps(schema, ensure_ascii=False)}

STRUCTURED SOURCE FACTS:
{json.dumps(normalize_facts(facts), ensure_ascii=False)}
"""

    response = call_ollama(
        prompt,
        temperature=0.15,
        max_tokens=1000,
        expect_json=True,
    )

    parsed = _require_json(
        response,
        "social content",
    )

    result: dict[str, Any] = {}

    if "linkedin" in schema:
        linkedin = _build_linkedin_post(
            parsed.get("linkedin")
        )

        if not linkedin:
            raise ModelResponseError(
                "Ollama returned an empty LinkedIn post."
            )

        result["linkedin"] = linkedin

    else:
        result["linkedin"] = ""

    if "x_thread" in schema:
        x_thread = _extract_x_thread(parsed)

        if not x_thread:
            x_thread = _recover_x_thread(
                facts,
                settings,
            )

        if not x_thread:
            raise ModelResponseError(
                "Ollama returned an empty X thread, "
                "including its retry."
            )

        result["x_thread"] = x_thread

    else:
        result["x_thread"] = []

    return result

def generate_linkedin(
    facts: dict[str, Any],
    settings: dict[str, Any],
) -> str:
    """Generate only a LinkedIn post."""

    return generate_social_content(
        facts,
        settings,
        "linkedin",
    )["linkedin"]


def generate_x_thread(
    facts: dict[str, Any],
    settings: dict[str, Any],
) -> list[str]:
    """Generate only an X thread."""

    return generate_social_content(
        facts,
        settings,
        "x",
    )["x_thread"]


def validate_grounding(
    facts: dict[str, Any],
    linkedin: str = "",
    x_thread: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Optional slower claim review."""

    content = {
        "linkedin": linkedin,
        "x_thread": x_thread or [],
    }

    prompt = f"""
Compare the social-media content with the structured source facts.

Identify only clear factual claims in the content
that are unsupported by the source facts.

Do not penalize:
- Style
- Paraphrasing
- Omitted facts

Return ONLY JSON:

{{
  "status": "PASS",
  "unsupported_claims": []
}}

Use status "FLAG" when unsupported_claims is not empty.

FACTS:
{json.dumps(
    normalize_facts(facts),
    ensure_ascii=False,
)}

CONTENT:
{json.dumps(
    content,
    ensure_ascii=False,
)}
"""

    response = call_ollama(
        prompt,
        temperature=0.0,
        max_tokens=300,
        expect_json=True,
    )

    parsed = _require_json(
        response,
        "grounding review",
    )

    claims = _as_list(
        parsed.get("unsupported_claims")
    )

    status = (
        "FLAG"
        if claims
        else "PASS"
    )

    return {
        "status": status,
        "unsupported_claims": claims,
    }


def generate_content(
    source_text: str,
    settings: dict[str, Any],
    platform: Optional[str] = None,
) -> dict[str, Any]:
    """Run the facts and content generation pipeline."""

    selected_platform = (
        platform
        or settings.get(
            "platform",
            "both",
        )
    )

    facts = extract_source_facts(
        source_text
    )

    content = generate_social_content(
        facts,
        settings,
        selected_platform,
    )

    return {
        "facts": facts,
        **content,
    }