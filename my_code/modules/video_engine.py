"""Video blueprint generation, motion-script authoring, and optional MP4 rendering.

The Ollama prompt and the normalization pass keep every scene grounded in the
supplied source facts: scene count, titles, descriptions, voiceover copy,
visuals, and timing are all derived from the input document, and no static
scene template or hardcoded metric ever reaches the output.

Each blueprint also carries a `motion_script` array (scene_id, heading, subtext,
theme_severity, active_icon, animation_style, duration_seconds) that drives the
client-side "Code-as-Motion" engine in html_frontend/05_video.html. That engine
is the primary playback path, so the heavy render stack (moviepy, pyttsx3,
numpy, Pillow) is imported lazily and the module stays importable without it.
"""

import os
import json
import tempfile
import requests
from modules.design_engine import infer_design

try:  # Optional: only the offline MP4 renderer needs these heavyweight packages.
    import pyttsx3
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips, vfx, afx
    HEAVY_RENDER_AVAILABLE = True
except ImportError:  # Blueprint + motion-script generation must keep working regardless.
    pyttsx3 = np = Image = ImageDraw = ImageFont = None
    ImageClip = AudioFileClip = concatenate_videoclips = vfx = afx = None
    HEAVY_RENDER_AVAILABLE = False

OLLAMA_API_URL = "http://localhost:11434/api/generate"
WIDTH = 1280
HEIGHT = 720


def _ordered_bbox(box):
    """Normalize Pillow bounds to left, top, right, bottom coordinates."""
    x0, y0, x1, y1 = box
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0 + 1, y1)
    return x0, y0, x1, y1


class _SafeDraw:
    """Pass through ImageDraw operations while sanitizing every rectangle box."""
    def __init__(self, draw):
        self._draw = draw

    def rectangle(self, box, *args, **kwargs):
        return self._draw.rectangle(_ordered_bbox(box), *args, **kwargs)

    def rounded_rectangle(self, box, *args, **kwargs):
        return self._draw.rounded_rectangle(_ordered_bbox(box), *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._draw, name)


def _safe_draw(draw):
    return draw if isinstance(draw, _SafeDraw) else _SafeDraw(draw)


# ---------------------------------------------------------
# GENERATOR (Ollama Blueprint Generation)
# ---------------------------------------------------------

def _pick_text(*values) -> str:
    """Return the first non-empty string among the given values."""
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _as_text_list(value) -> list:
    """Normalize a scalar or sequence into a clean list of strings."""
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple)):
        items = []
        for item in value:
            text = str(item or "").strip()
            if text:
                items.append(text)
        return items
    return []


def _estimate_narration_seconds(text: str) -> float:
    """Estimate spoken runtime (word count at ~2.5 words/second)."""
    words = len(str(text or "").split())
    return round(words / 2.5, 1) if words else 0.0


def _coerce_seconds(value) -> float:
    """Parse a declared duration into seconds; return 0.0 when absent or invalid."""
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _facts_from_text(text: str) -> dict:
    """Recover canonical fact fields when the input text is serialized facts JSON."""
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    cve_ids = _as_text_list(parsed.get("cve_ids"))
    for cve in _as_text_list(parsed.get("locked_cves")):
        if cve not in cve_ids:
            cve_ids.append(cve)
    return {
        "title": _pick_text(parsed.get("title")),
        "severity": _pick_text(parsed.get("severity")),
        "summary": _pick_text(parsed.get("summary")),
        "cve_ids": cve_ids,
        "affected_systems": _as_text_list(parsed.get("affected_systems")),
        "locked_ips": _as_text_list(parsed.get("locked_ips")),
        "recommended_actions": _as_text_list(parsed.get("recommended_actions")),
    }


def _format_facts_block(facts: dict) -> str:
    """Render canonical facts as the authoritative bullet list for the prompt."""
    lines = []
    if facts.get("title"):
        lines.append(f"- Title: {facts['title']}")
    if facts.get("severity"):
        lines.append(f"- Severity: {facts['severity']}")
    if facts.get("cve_ids"):
        lines.append(f"- CVE IDs: {', '.join(facts['cve_ids'])}")
    if facts.get("affected_systems"):
        lines.append(f"- Affected systems: {', '.join(facts['affected_systems'])}")
    if facts.get("locked_ips"):
        lines.append(f"- Locked indicator IPs: {', '.join(facts['locked_ips'])}")
    if facts.get("summary"):
        lines.append(f"- Summary: {facts['summary']}")
    if facts.get("recommended_actions"):
        lines.append("- Recommended actions:")
        lines.extend(f"  {index}. {action}" for index, action in enumerate(facts["recommended_actions"], 1))
    return "\n".join(lines)


def _normalize_metrics(value) -> list:
    """Normalize metric entries into labeled callouts, dropping anything empty."""
    if not isinstance(value, (list, tuple)):
        return []
    metrics = []
    for item in value:
        if isinstance(item, dict):
            label = _pick_text(item.get("label"), item.get("name"))
            metric_value = _pick_text(item.get("value"), item.get("detail"))
        else:
            label, metric_value = "", _pick_text(item)
        if label or metric_value:
            metrics.append({"label": label or metric_value, "value": metric_value or label})
    return metrics


# Motion-script enums shared with the client-side engine in 05_video.html.
_MOTION_SEVERITIES = ("critical", "warning", "info")
_MOTION_ICONS = ("shield", "network", "lock", "user_analyst")
_MOTION_STYLES = ("slide_in", "pulse_alert", "kinetic_zoom")


def _map_severity_to_motion(severity: str) -> str:
    """Collapse any source severity wording into the three-value motion theme enum."""
    value = str(severity or "").lower()
    if any(token in value for token in ("critical", "high", "severe")):
        return "critical"
    if any(token in value for token in ("medium", "moderate", "warning", "elevated")):
        return "warning"
    return "info"


def _infer_motion_icon(*texts) -> str:
    """Pick the scene icon from its own wording; defaults to the generic shield."""
    blob = " ".join(str(text or "").lower() for text in texts)
    if any(key in blob for key in ("credential", "password", "analyst", "operator", "account", "user")):
        return "user_analyst"
    if any(key in blob for key in ("encrypt", "ransom", "lock", "exfiltrat", "access")):
        return "lock"
    if any(key in blob for key in ("network", "traffic", "endpoint", "node", "server", "lateral", "ip")):
        return "network"
    return "shield"


def _infer_motion_style(position: int, theme_severity: str, metrics: list) -> str:
    """Deterministic animation style so scenes vary without random flicker."""
    if position == 1:
        return "slide_in"
    if theme_severity == "critical":
        return "pulse_alert"
    if metrics:
        return "kinetic_zoom"
    return "slide_in"


def _normalize_scene(raw, index: int):
    """Convert one raw LLM scene into the grounded scene schema, or None if empty."""
    if isinstance(raw, str):
        raw = {"narration": raw} if raw.strip() else {}
    if not isinstance(raw, dict):
        return None

    title = _pick_text(raw.get("title"), raw.get("on_screen_text"))
    on_screen_text = _pick_text(raw.get("on_screen_text"), title)
    narration = _pick_text(raw.get("narration"), raw.get("narration_text"), raw.get("voiceover"), raw.get("script"))
    visual_prompt = _pick_text(raw.get("visual_prompt"), raw.get("visual_description"), raw.get("visual_recommendation"))
    description = _pick_text(raw.get("description"), visual_prompt, narration)
    if not any((title, narration, visual_prompt, description)):
        return None

    duration_seconds = _coerce_seconds(raw.get("duration_seconds", raw.get("duration")))
    if duration_seconds <= 0:
        duration_seconds = _estimate_narration_seconds(narration) or _estimate_narration_seconds(description)
    duration_seconds = round(max(2.0, duration_seconds), 1)

    scene = {
        "scene_number": index,
        "title": title,
        "description": description,
        "narration": narration,
        "visual_prompt": visual_prompt,
        "duration_seconds": duration_seconds,
        "on_screen_text": on_screen_text,
    }
    intent = _pick_text(raw.get("intent"))
    if intent:
        scene["intent"] = intent
    metrics = _normalize_metrics(raw.get("metrics") or raw.get("key_metrics"))
    if metrics:
        scene["metrics"] = metrics
    actions = _as_text_list(raw.get("actions") or raw.get("key_actions") or raw.get("recommended_actions"))
    if actions:
        scene["actions"] = actions
    key_points = _as_text_list(raw.get("key_points"))
    if key_points:
        scene["key_points"] = key_points

    # Motion direction for the client-side engine; enum values are validated and
    # anything unrecognised is re-derived from this scene's own grounded copy.
    heading = _pick_text(raw.get("heading"), title, on_screen_text)
    subtext = _pick_text(raw.get("subtext"), narration, description)
    raw_theme = _pick_text(raw.get("theme_severity"), raw.get("severity")).lower()
    raw_icon = _pick_text(raw.get("active_icon"), raw.get("icon")).lower().replace("-", "_").replace(" ", "_")
    raw_style = _pick_text(raw.get("animation_style"), raw.get("animation")).lower().replace("-", "_").replace(" ", "_")
    scene["scene_id"] = index
    scene["heading"] = heading
    scene["subtext"] = subtext
    if raw_theme in _MOTION_SEVERITIES:
        scene["theme_severity"] = raw_theme
    elif raw_theme:
        scene["theme_severity"] = _map_severity_to_motion(raw_theme)
    else:
        scene["theme_severity"] = ""
    scene["active_icon"] = (
        raw_icon if raw_icon in _MOTION_ICONS
        else _infer_motion_icon(visual_prompt, description, narration, title)
    )
    scene["animation_style"] = raw_style if raw_style in _MOTION_STYLES else ""
    return scene


def _normalize_blueprint(raw, facts: dict, target_audience: str, tone: str,
                         language: str, objective: str, style: str) -> dict:
    """Validate the LLM blueprint and compose the fact-grounded output schema."""
    if isinstance(raw, dict) and not isinstance(raw.get("scenes"), list):
        # Tolerate one level of wrapping (e.g. {"blueprint": {"scenes": [...]}}).
        for value in raw.values():
            if isinstance(value, dict) and isinstance(value.get("scenes"), list):
                raw = value
                break
    if not isinstance(raw, dict):
        raise RuntimeError("Ollama returned a non-object JSON blueprint.")
    if not isinstance(raw.get("scenes"), list):
        raise RuntimeError("Ollama blueprint is missing a scenes list.")

    scenes = []
    for raw_scene in raw["scenes"]:
        scene = _normalize_scene(raw_scene, len(scenes) + 1)
        if scene:
            scenes.append(scene)
    if not scenes:
        raise RuntimeError("Ollama blueprint did not contain any usable scene content.")

    total_seconds = round(sum(scene["duration_seconds"] for scene in scenes), 1)
    voiceover_script = " ".join(scene["narration"] for scene in scenes if scene["narration"]).strip()
    # One visual prompt per scene, in order, so downstream consumers can index them against scenes.
    visual_prompts = [scene["visual_prompt"] or scene["description"] or scene["title"] for scene in scenes]

    # Client-side "Code-as-Motion" script: enum-validated per scene and backfilled
    # from the blueprint severity, so partial or legacy payloads still animate.
    fallback_theme = _map_severity_to_motion(_pick_text(raw.get("severity"), facts.get("severity")))
    motion_script = []
    for position, scene in enumerate(scenes, 1):
        theme = scene.get("theme_severity") or fallback_theme
        style = scene.get("animation_style") or _infer_motion_style(
            position, theme, scene.get("metrics") or []
        )
        scene["scene_id"] = position
        scene["theme_severity"] = theme
        scene["animation_style"] = style
        motion_script.append({
            "scene_id": position,
            "heading": _pick_text(scene.get("heading"), scene.get("title"), scene.get("on_screen_text")),
            "subtext": _pick_text(scene.get("subtext"), scene.get("narration"), scene.get("description")),
            "theme_severity": theme,
            "active_icon": _pick_text(scene.get("active_icon")) or "shield",
            "animation_style": style,
            "duration_seconds": scene["duration_seconds"],
        })

    # Variety guard. Small local models tend to emit one enum value for every
    # scene; when the reel has no variety at all, re-derive the motion direction
    # from each scene's own grounded copy so the animation still changes shape.
    # Anything the model did vary is left exactly as it chose.
    if len(motion_script) >= 3:
        if len({entry["animation_style"] for entry in motion_script}) == 1:
            for position, entry in enumerate(motion_script, 1):
                scene = scenes[position - 1]
                style = _infer_motion_style(position, entry["theme_severity"], scene.get("metrics") or [])
                entry["animation_style"] = style
                scene["animation_style"] = style
            if len({entry["animation_style"] for entry in motion_script}) == 1:
                for position, entry in enumerate(motion_script, 1):
                    style = _MOTION_STYLES[(position - 1) % len(_MOTION_STYLES)]
                    entry["animation_style"] = style
                    scenes[position - 1]["animation_style"] = style
        if len({entry["active_icon"] for entry in motion_script}) == 1:
            for position, entry in enumerate(motion_script, 1):
                scene = scenes[position - 1]
                icon = _infer_motion_icon(scene.get("visual_prompt"), scene.get("description"),
                                          scene.get("narration"), scene.get("title"))
                entry["active_icon"] = icon
                scene["active_icon"] = icon

    return {
        "title": _pick_text(raw.get("title"), facts.get("title")),
        "summary": _pick_text(raw.get("summary"), facts.get("summary")),
        "severity": _pick_text(raw.get("severity"), facts.get("severity")),
        "scenes": scenes,
        "motion_script": motion_script,
        "visual_prompts": visual_prompts,
        "voiceover_script": voiceover_script,
        "duration": f"{total_seconds:g}s",
        "metadata": {
            "source_title": _pick_text(facts.get("title"), raw.get("title")),
            "severity": _pick_text(facts.get("severity"), raw.get("severity")),
            "cve_ids": list(facts.get("cve_ids") or []),
            "locked_ips": list(facts.get("locked_ips") or []),
            "affected_systems": list(facts.get("affected_systems") or []),
            "scene_count": len(scenes),
            "total_duration_seconds": total_seconds,
            "target_audience": target_audience,
            "tone": tone,
            "language": language,
            "objective": objective,
            "visual_style": style,
        },
    }


def generate_video_blueprint(
    text: str,
    target_audience: str = "General",
    tone: str = "Informative",
    language: str = "English",
    duration: str = "auto",
    objective: str = "Summarize threat advisory",
    style: str = "Cybersecurity Technical"
) -> dict:
    """
    Sends the source facts to local Ollama (qwen2.5:3b) and returns a normalized,
    fact-grounded video blueprint.

    Scene count, titles, descriptions, voiceover copy, visuals, and timing are
    derived from the input facts only; the returned structure is validated
    before rendering so static template content never reaches the output.
    """
    text = text[:12000]
    facts = _facts_from_text(text)
    facts_block = _format_facts_block(facts)
    auto_duration = str(duration).strip().lower() in ("auto", "none", "")
    duration_guidance = (
        "derive the total runtime strictly from the facts"
        if auto_duration else f"aim for a total runtime near {duration}"
    )
    duration_rule = (
        "The total runtime must follow from the facts; never force a preset length."
        if auto_duration else f"Scale the scene plan so the total runtime lands close to {duration}."
    )

    prompt = f"""You are an expert video producer and scriptwriter.
Plan a scene-by-scene video blueprint as valid JSON, derived strictly from the authoritative facts below.

[Video Parameters]
- Target Audience: {target_audience}
- Tone: {tone}
- Language: {language}
- Duration guidance: {duration_guidance}
- Objective: {objective}
- Visual Style: {style}

[Authoritative Facts]
{facts_block or "- No structured facts were provided; ground every statement in the raw source text below."}

[Raw Source Text]
{text}

[Planning Rules]
1. Scene count is dynamic: create exactly as many scenes as the facts require, one scene per distinct fact group (for example alert context, affected scope, impact, mitigations). Never pad with filler scenes and never merge unrelated facts into one scene.
2. Every title, description, narration line, metric, action, and key point must be traceable to the authoritative facts. Never invent numbers, products, CVE IDs, IPs, or actions.
3. Quote CVE IDs, severity values, and indicator IPs verbatim in the scenes that reference them.
4. Write every field in {language}.
5. Narration is speakable voiceover copy paced at roughly 2.5 words per second; set each scene's "duration_seconds" from its narration length.
6. {duration_rule}
7. Do not emit placeholder text, generic template labels, or repeated wording across scenes.
8. If a field is not supported by the facts, omit it instead of guessing.
9. Every scene must also carry motion direction for the client-side animation engine: "scene_id" (its 1-based position), "heading" (short on-screen headline, at most 8 words), "subtext" (one supporting on-screen sentence, at most 22 words), "theme_severity" (one of "critical", "warning", "info", matching the risk this scene presents), "active_icon" (one of "shield", "network", "lock", "user_analyst"), and "animation_style" (one of "slide_in", "pulse_alert", "kinetic_zoom").
10. Pick "active_icon" from the scene subject, not from habit: "lock" for encryption, ransom, credential or access-abuse scenes; "network" for lateral movement, traffic, endpoints, servers or affected-scope scenes; "user_analyst" for human remediation, operator or recommended-action scenes; "shield" only for general defence or posture scenes. Never reuse the same "active_icon" on two consecutive scenes unless the subject is genuinely identical.
11. Pick "animation_style" from the scene shape: "pulse_alert" for the highest-risk or active-exploitation scene, "kinetic_zoom" for scenes built around metrics, counts or impact numbers, and "slide_in" for everything else. Use at least two different styles across the reel.

[Required JSON Schema]
Return ONLY this JSON object:
{{
  "title": "video title grounded in the facts",
  "summary": "executive summary grounded in the facts",
  "scenes": [
    {{
      "scene_number": 1,
      "scene_id": 1,
      "heading": "short on-screen headline for this scene",
      "subtext": "one supporting on-screen sentence",
      "theme_severity": "critical",
      "active_icon": "shield",
      "animation_style": "slide_in",
      "title": "short scene title",
      "description": "what this scene communicates and why",
      "narration": "voiceover script for this scene",
      "visual_prompt": "visual direction for this scene",
      "duration_seconds": 8,
      "metrics": [{{"label": "fact label", "value": "fact value"}}],
      "actions": ["source-backed mitigation step"],
      "key_points": ["concise source-grounded callout"]
    }}
  ]
}}
"metrics", "actions", and "key_points" are optional per scene; include them only when the facts support them. "scene_id", "heading", "subtext", "theme_severity", "active_icon", and "animation_style" are required on every scene and must use only the enum values listed above.
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
        raise RuntimeError(f"Could not connect to local Ollama API: {e}")

    if response.status_code != 200:
        try:
            error_message = response.json().get("error", "Unknown API error")
        except Exception:
            error_message = response.text

        raise RuntimeError(
            f"Ollama API returned HTTP {response.status_code}: {error_message}"
        )

    try:
        res_data = response.json()
        raw_response = res_data.get("response", "{}")
        raw_blueprint = json.loads(raw_response)
    except (json.JSONDecodeError, KeyError) as e:
        raise RuntimeError(f"Failed to parse JSON response from Ollama: {e}")

    return _normalize_blueprint(
        raw_blueprint,
        facts,
        target_audience=_pick_text(target_audience, "General"),
        tone=_pick_text(tone, "Informative"),
        language=_pick_text(language, "English"),
        objective=_pick_text(objective, "Summarize threat advisory"),
        style=_pick_text(style, "Cybersecurity Technical"),
    )


# ---------------------------------------------------------
# GRAPHICS & RENDERING UTILITIES
# ---------------------------------------------------------

def get_font(size: int, bold: bool = False):
    paths = [
        "C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def _fit_text_lines(draw, text: str, font, max_width: int, max_lines: int = 3) -> list[str]:
    """Wrap copy by measured pixel width and clamp it to the available visual area."""
    words = str(text).split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        elif current:
            lines.append(current)
            current = word
        else:
            lines.append(word)
            current = ""
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and draw.textbbox((0, 0), last + "…", font=font)[2] > max_width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return lines


def draw_wrapped_text(
    draw,
    text: str,
    position: tuple,
    font,
    max_width: int,
    fill: str = "white",
    line_spacing: int = 10
) -> int:
    draw = _safe_draw(draw)
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = current + " " + word if current else word
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    x, y = position
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((x, y), line, font=font)
        y = bbox[3] + line_spacing

    return y


# ---------------------------------------------------------
# VISUAL SCENE DRAWING FUNCTIONS
# ---------------------------------------------------------

# Layout numbers pick a drawing frame only; every embedded copy is scene-derived.
_LEGACY_INTENT_LAYOUTS = {
    "title_alert": 1, "alert": 1, "opening": 1,
    "attack_flow": 2, "data_flow": 2, "architecture": 2,
    "metrics": 3, "metric_highlights": 3, "impact_metrics": 3,
    "mitigation": 4, "actions": 4, "response_steps": 4,
    "evidence_dashboard": 5, "evidence": 5, "summary": 5,
}


def _scene_text_items(scene: dict, *keys) -> list:
    """Collect the first non-empty list of clean strings among the scene keys."""
    for key in keys:
        items = _as_text_list(scene.get(key))
        if items:
            return items
    return []


def _scene_metrics(scene: dict) -> list:
    """Collect (label, value) metric callouts from the scene, ignoring empties."""
    callouts = []
    for metric in scene.get("metrics") or scene.get("key_metrics") or []:
        if isinstance(metric, dict):
            label = _pick_text(metric.get("label"), metric.get("name"))
            value = _pick_text(metric.get("value"), metric.get("detail"))
        else:
            label, value = "", _pick_text(metric)
        if label or value:
            callouts.append((label, value or label))
    return callouts


def draw_scene_visual(draw, scene: dict):
    """Draw a scene visual frame whose layout and copy both come from the scene."""
    draw = _safe_draw(draw)
    palette = (scene.get("_design") or {}).get("palette", {})
    theme_accent = palette.get("accent")
    visual_text = " ".join(
        str(scene.get(key, "")) for key in (
            "visual_prompt", "visual_description", "visual_recommendation",
            "on_screen_text", "title", "description", "narration",
        )
    ).lower()
    accent = tuple(int(theme_accent[i:i+2], 16) for i in (1, 3, 5)) if isinstance(theme_accent, str) and len(theme_accent) == 7 else ((66, 220, 207) if any(x in visual_text for x in ("finance", "revenue", "market", "budget")) else (255, 83, 93))
    blue, panel, ink = (77, 150, 235), (19, 35, 55), (224, 236, 248)

    headline = _pick_text(scene.get("title"), scene.get("on_screen_text"))
    metrics = _scene_metrics(scene)
    actions = _scene_text_items(scene, "actions", "key_actions", "recommended_actions")
    points = _scene_text_items(scene, "key_points")
    intent = str(scene.get("intent", "")).lower().replace("-", "_").replace(" ", "_")

    # Layout priority: legacy intent hint first (older blueprints), then scene content.
    layout = _LEGACY_INTENT_LAYOUTS.get(intent)
    if layout is None:
        if metrics:
            layout = 3
        elif actions:
            layout = 4
        elif len(points) >= 2:
            layout = 2
        elif int(scene.get("scene_number", 1) or 1) == 1:
            layout = 1
        else:
            layout = 5
    if layout == 1 and not headline:
        layout = 5
    elif layout == 2 and len(points or actions) < 2:
        layout = 5
    elif layout == 3 and not metrics:
        layout = 5
    elif layout == 4 and not actions:
        layout = 5

    if layout == 1:
        # Alert/title frame with a high-contrast signal marker and the scene headline.
        draw.rounded_rectangle((760, 205, 1150, 485), radius=34, fill=(38, 24, 37), outline=accent, width=4)
        draw.polygon([(955, 242), (1095, 438), (815, 438)], fill=accent)
        draw.text((916, 300), "!", font=get_font(112, True), fill="white")
        draw.rounded_rectangle((130, 280, 665, 405), radius=24, fill=panel, outline=blue, width=3)
        headline_font = get_font(34, True)
        for line_index, line in enumerate(_fit_text_lines(draw, headline, headline_font, 470, 2)):
            draw.text((180, 312 + line_index * 40), line, font=headline_font, fill=ink)
    elif layout == 2:
        # Flow frame: one node per derived key point or action.
        nodes = (points or actions)[:3]
        span = 1080 - 275
        for i, node in enumerate(nodes):
            x = 125 + (i * span // (len(nodes) - 1) if len(nodes) > 1 else 0)
            draw.rounded_rectangle((x, 285, x + 275, 440), radius=22, fill=panel, outline=accent if i == 0 else blue, width=4)
            draw.ellipse((x + 102, 230, x + 172, 300), fill=accent if i == 0 else blue)
            node_font = get_font(24 if len(node) > 56 else 28, True)
            for line_index, line in enumerate(_fit_text_lines(draw, node, node_font, 215, 2)):
                draw.text((x + 30, 330 + line_index * 36), line, font=node_font, fill=ink)
            if i < len(nodes) - 1:
                tip = x + 275
                draw.line((tip + 8, 362, tip + 88, 362), fill=accent, width=8)
                draw.polygon([(tip + 88, 347), (tip + 118, 362), (tip + 88, 377)], fill=accent)
    elif layout == 3:
        # Metric callouts sized to the sourced values.
        for i, (label, value) in enumerate(metrics[:3]):
            x = 95 + i * 400
            draw.rounded_rectangle((x, 250, x + 350, 465), radius=28, fill=panel, outline=accent if i == 0 else blue, width=4)
            font_size = max(23, min(40, int(290 / max(1, len(value) / 18))))
            for line_index, line in enumerate(_fit_text_lines(draw, value, get_font(font_size, True), 295, 3)):
                draw.text((x + 24, 292 + line_index * 48), line, font=get_font(font_size, True), fill=accent if i == 0 else ink)
            if label and label != value:
                draw.text((x + 24, 420), label[:24].upper(), font=get_font(18, True), fill=blue)
    elif layout == 4:
        # Checklist frame: one sourced action per row.
        draw.rounded_rectangle((210, 220, 1080, 500), radius=26, fill=panel, outline=blue, width=3)
        for i, action in enumerate(actions[:4]):
            y = 265 + i * 55
            draw.ellipse((255, y, 285, y + 30), fill=accent)
            draw.line((263, y + 15, 271, y + 23, 281, y + 8), fill=(255, 255, 255), width=3)
            action_font = get_font(20 if len(action) > 74 else 23)
            for line_index, line in enumerate(_fit_text_lines(draw, action, action_font, 700, 2)):
                draw.text((315, y - 3 + line_index * 25), line, font=action_font, fill=ink)
    else:
        # Neutral dashboard frame with no embedded copy.
        draw.rounded_rectangle((170, 220, 1110, 490), radius=26, fill=panel, outline=blue, width=3)
        for i, width in enumerate((680, 500, 750, 430)):
            y = 275 + i * 48
            draw.rounded_rectangle((255, y, 255 + width, y + 18), radius=8, fill=(39, 59, 83))
            draw.rounded_rectangle((255, y, 255 + int(width * (.48 + .12 * (i % 3))), y + 18), radius=8, fill=accent if i == 0 else blue)
        draw.ellipse((920, 265, 1020, 365), fill=(29, 108, 91), outline=(76, 211, 166), width=4)
        draw.line((945, 315, 970, 338, 1001, 292), fill="white", width=9)


# ---------------------------------------------------------
# SCENE IMAGE & VIDEO RENDERING
# ---------------------------------------------------------

def create_scene_image(scene: dict, output_path: str, total_scenes: int):
    blueprint = scene.get("_design", {})
    palette = blueprint.get("palette", {})
    as_rgb = lambda value, fallback: tuple(int(value[i:i+2], 16) for i in (1, 3, 5)) if isinstance(value, str) and len(value) == 7 else fallback
    background = as_rgb(palette.get("primary"), (8, 15, 27))
    accent = as_rgb(palette.get("accent"), (40, 150, 255))
    image = Image.new("RGB", (WIDTH, HEIGHT), background)
    draw = _safe_draw(ImageDraw.Draw(image))

    # Top blue accent bar
    draw.rectangle((0, 0, WIDTH, 9), fill=accent)

    small_font = get_font(26)
    scene_number = scene["scene_number"]

    # Header section
    draw.text((60, 35), f"SCENE {scene_number} / {total_scenes}", font=small_font, fill=(120, 190, 255))

    # Visual panel container
    draw.rounded_rectangle(
        (45, 175, 1235, 505),
        radius=20,
        fill=tuple(min(255, int(channel * 1.25)) for channel in background),
        outline=accent,
        width=2
    )
    draw.text((75, 195), "VISUAL", font=small_font, fill=(100, 190, 255))

    # Contextual graphic
    draw_scene_visual(draw, scene)

    image.save(output_path)


def _animate_scene_frame(get_frame, t: float, duration: float, scene: dict,
                         accent: tuple[int, int, int], elapsed_before: float,
                         total_duration: float):
    """Add timed title/subtitle reveals and a continuous progress rail to a zoomed frame."""
    frame = np.asarray(get_frame(t), dtype=np.uint8)
    canvas = Image.fromarray(frame).convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = _safe_draw(ImageDraw.Draw(overlay))
    white = (248, 250, 252, 255)
    title = str(scene.get("on_screen_text") or scene.get("title") or f"Scene {scene.get('scene_number', 1)}")
    narration = str(scene.get("narration") or scene.get("narration_text") or "")

    # Title slides in and resolves over the opening half-second.
    title_progress = min(1.0, max(0.0, t / 0.5))
    if title_progress:
        title_y = int(92 + (1.0-title_progress) * 22)
        visible_title = title[:max(1, int(len(title) * title_progress))]
        title_size = max(26, min(42, int(1000 / max(1, len(title) / 25))))
        title_font = get_font(title_size, True)
        for index, line in enumerate(_fit_text_lines(draw, visible_title, title_font, 1150, 2)):
            draw.text((58, title_y + index * (title_size+5)), line, font=title_font, fill=white)

    # Translucent lower third eases up while narration text reveals with the voiceover.
    ease = min(1.0, max(0.0, t / 0.42))
    ease = ease * ease * (3 - 2 * ease)
    top = int(720 - 154 * ease)
    draw.rounded_rectangle((42, top, 1238, 704), radius=18,
                           fill=(7, 15, 29, 226), outline=(*accent, 235), width=2)
    draw.rounded_rectangle((65, top+17, 220, top+43), radius=13,
                           fill=(*accent, 235))
    draw.text((79, top+21), f"VOICEOVER  /  {int(scene.get('scene_number', 1)):02d}",
              font=get_font(13, True), fill=(255, 255, 255, 255))

    spoken_fraction = min(1.0, max(0.0, (t + 0.15) / max(duration, 0.1)))
    visible_narration = narration[:max(1, int(len(narration) * spoken_fraction))] if narration else ""
    subtitle_font = get_font(max(15, min(21, int(1200 / max(1, len(narration) / 55)))))
    text_top = top + 54
    if visible_narration and text_top < 685:
        for index, line in enumerate(_fit_text_lines(draw, visible_narration, subtitle_font, 1125, 3)):
            draw.text((72, text_top + index * (subtitle_font.size+3)), line, font=subtitle_font, fill=white)

    # Global progress persists across scene cuts instead of restarting per clip.
    progress = min(1.0, max(0.0, (elapsed_before + t) / max(total_duration, 0.1)))
    rail_y = 710
    draw.rectangle((0, rail_y, WIDTH, HEIGHT), fill=(30, 41, 59, 255))
    draw.rectangle((0, rail_y, int(WIDTH * progress), HEIGHT), fill=(*accent, 255))
    canvas.alpha_composite(overlay)
    return np.asarray(canvas.convert("RGB"))


def _generate_narration_audio(text: str, output_path: str) -> None:
    """Generate offline WAV narration for one scene using pyttsx3."""
    engine = pyttsx3.init()
    try:
        engine.save_to_file(text, output_path)
        engine.runAndWait()
    finally:
        engine.stop()


def create_video(blueprint: dict, output_path: str = "sample_video.mp4") -> str:
    """Render scene images, synthesize narration, and stitch an MP4 with audio."""
    if not HEAVY_RENDER_AVAILABLE:
        raise RuntimeError(
            "Local MP4 render dependencies (moviepy, pyttsx3, numpy, Pillow) are not "
            "installed. Serve the blueprint's motion_script to the client-side "
            "Code-as-Motion engine instead."
        )
    scene_dir = os.path.join("output", "video_scenes")
    os.makedirs(scene_dir, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    scenes = blueprint.get("scenes") or []
    if not scenes:
        raise ValueError("Video blueprint must contain at least one scene.")

    clips = []
    design = infer_design({"title": blueprint.get("title", ""), "summary": blueprint.get("summary", ""), "severity": blueprint.get("severity", "")})
    with tempfile.TemporaryDirectory(prefix="video_narration_") as audio_dir:
        # Synthesize first so animated captions and the global progress rail use actual voice durations.
        audio_paths = {}
        audio_durations = {}
        for scene in scenes:
            narration = str(scene.get("narration") or scene.get("narration_text") or "").strip()
            if narration:
                number = scene["scene_number"]
                audio_path = os.path.join(audio_dir, f"scene_{number}.wav")
                _generate_narration_audio(narration, audio_path)
                audio_paths[number] = audio_path
                measured = AudioFileClip(audio_path)
                audio_durations[number] = measured.duration
                measured.close()

        # Scene timing comes from declared durations, narration length, and measured audio.
        scene_durations = [
            max(
                1.0,
                _coerce_seconds(scene.get("duration_seconds")),
                _estimate_narration_seconds(scene.get("narration") or scene.get("narration_text") or ""),
                audio_durations.get(scene["scene_number"], 0.0),
            )
            for scene in scenes
        ]
        transition = min(0.45, max(0.0, min(scene_durations) / 5)) if len(scenes) > 1 else 0.0
        total_duration = sum(scene_durations) - transition * max(0, len(scenes)-1)
        elapsed_before = 0.0
        for index, scene in enumerate(scenes):
            scene_number = scene["scene_number"]
            image_path = os.path.join(scene_dir, f"scene_{scene_number}.png")
            scene_visual = dict(scene, _design=design)
            create_scene_image(scene_visual, image_path, len(scenes))

            scene_duration = scene_durations[index]
            palette_accent = design["palette"]["accent"]
            accent = tuple(int(palette_accent[i:i+2], 16) for i in (1, 3, 5))
            video_clip = ImageClip(image_path).with_duration(scene_duration)
            # Slow zoom with a gentle horizontal drift, cropped back to the 16:9 canvas.
            zoomed = video_clip.with_effects([vfx.Resize(lambda t, d=scene_duration: 1.035 + 0.025 * min(1.0, t / max(d, .1)))])
            def crop_zoom(get_frame, t, d=scene_duration):
                frame = np.asarray(get_frame(t), dtype=np.uint8)
                image = Image.fromarray(frame)
                width, height = image.size
                max_x, max_y = max(0, width-WIDTH), max(0, height-HEIGHT)
                drift = min(1.0, t / max(d, .1))
                left = int(max_x * (0.35 + .3 * drift))
                top = int(max_y * (0.45 + .1 * drift))
                return np.asarray(image.crop((left, top, left+WIDTH, top+HEIGHT)))
            video_clip = zoomed.transform(crop_zoom)
            video_clip = video_clip.transform(
                lambda get_frame, t, d=scene_duration, current_scene=scene, current_accent=accent, offset=elapsed_before: _animate_scene_frame(
                    get_frame, t, d, current_scene, current_accent, offset, total_duration
                )
            )
            video_clip = video_clip.with_effects([vfx.FadeIn(.45), vfx.FadeOut(.3)])
            if index:
                video_clip = video_clip.with_effects([vfx.CrossFadeIn(transition)])
            if scene_number in audio_paths:
                audio_clip = AudioFileClip(audio_paths[scene_number]).with_effects([
                    afx.AudioFadeIn(min(.12, scene_duration/4)),
                    afx.AudioFadeOut(min(.16, scene_duration/4)),
                ])
                video_clip = video_clip.with_audio(audio_clip)
            clips.append(video_clip)
            elapsed_before += scene_duration - transition

        final_video = concatenate_videoclips(clips, method="compose", padding=-transition)
        final_video.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac"
        )

        # Close file-backed clips after encoding to release temporary audio files.
        final_video.close()
        for clip in clips:
            if clip.audio is not None:
                clip.audio.close()
            clip.close()

    return output_path


def process_video_transformation(canonical_facts, output_dir="data/outputs"):
    """Build a fact-grounded video from canonical facts and return its blueprint and path."""
    os.makedirs(output_dir, exist_ok=True)
    if isinstance(canonical_facts, dict):
        source_text = json.dumps(canonical_facts, ensure_ascii=False, indent=2)
        target_audience = _pick_text(canonical_facts.get("target_audience"), "General Public")
        tone = _pick_text(canonical_facts.get("tone"), "Informative")
    else:
        source_text = str(canonical_facts)
        target_audience, tone = "General Public", "Informative"

    blueprint = generate_video_blueprint(
        text=source_text,
        target_audience=target_audience,
        tone=tone,
        duration="auto"
    )
    # The motion_script inside the blueprint is always returned; the MP4 is an
    # optional extra that only renders where the heavyweight stack is installed.
    video_path = None
    if HEAVY_RENDER_AVAILABLE:
        video_path = os.path.join(output_dir, "generated_advisory.mp4")
        create_video(blueprint, output_path=video_path)
    return {"blueprint": blueprint, "video_path": video_path}
