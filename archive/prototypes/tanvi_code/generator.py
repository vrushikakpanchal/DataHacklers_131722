import json
import requests

OLLAMA_API_URL = "http://localhost:11434/api/generate"


def generate_video_blueprint(
    text,
    target_audience,
    tone,
    language,
    duration,
    objective,
    style
):
    """
    Sends the source document and video metadata to local Ollama (qwen2.5:3b)
    to generate a structured video script JSON blueprint.
    """

    # Keep source text within reasonable bounds
    text = text[:12000]

    # Construct the prompt expected by Ollama to return structured video JSON
    prompt = f"""You are an expert video producer and scriptwriter.
Generate a structured video blueprint in valid JSON format based on the following input parameters and content.

[Video Parameters]
- Target Audience: {target_audience}
- Tone: {tone}
- Language: {language}
- Duration: {duration}
- Objective: {objective}
- Visual Style: {style}

[Source Document Content]
{text}

[JSON Format Requirements]
Return ONLY a valid JSON object containing:
1. "title": Video title string
2. "summary": Brief executive summary string
3. "scenes": A list of scene objects, where each scene object contains:
   - "scene_number": Integer
   - "visual_description": Visual cues string
   - "narration": Voiceover/narration text string
   - "duration_seconds": Estimated duration integer
"""

    payload = {
        "model": "qwen2.5:3b",
        "prompt": prompt,
        "format": "json",
        "stream": False
    }

    try:
        response = requests.post(
            OLLAMA_API_URL,
            json=payload,
            timeout=600
        )
    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Could not connect to local Ollama API: {e}"
        )

    if response.status_code != 200:
        try:
            error_message = response.json().get(
                "error",
                "Unknown API error"
            )
        except Exception:
            error_message = response.text

        raise RuntimeError(
            f"Ollama API returned HTTP {response.status_code}: "
            f"{error_message}"
        )

    try:
        res_data = response.json()
        raw_response = res_data.get("response", "{}")
        result = json.loads(raw_response)
    except (json.JSONDecodeError, KeyError) as e:
        raise RuntimeError(
            f"Failed to parse JSON response from Ollama: {e}"
        )

    return result