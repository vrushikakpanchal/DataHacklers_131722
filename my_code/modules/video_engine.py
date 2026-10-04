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
import logging
import math
import tempfile
from pathlib import Path

import requests
from modules.design_engine import infer_design

logger = logging.getLogger(__name__)

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
RENDER_FPS = 30
NEURAL_INTERNAL_FPS = 10
NEURAL_CROP_SIZE = 256
_MY_CODE_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _MY_CODE_ROOT.parent
DEFAULT_CHARACTER_PLACEMENT = {
    "x_rel": 0.05,
    "y_rel": 0.50,
    "width_rel": 0.30,
    "height_rel": 0.45,
    "opacity": 1.0,
}
_LAST_RENDER_ENGINE = "uninitialized"

try:  # Optional: neural character animation (never required for blueprints).
    import onnxruntime as ort
    ONNX_RUNTIME_AVAILABLE = True
except ImportError:
    ort = None
    ONNX_RUNTIME_AVAILABLE = False

try:
    import cv2
except ImportError:
    cv2 = None


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

# ---------------------------------------------------------------------------
# SCENE VISUAL-TYPE SYSTEM
# Each value maps to a fundamentally distinct SVG composition + animation
# in the Code-as-Motion frontend renderer AND in the offline Pillow renderer.
# ---------------------------------------------------------------------------
_SCENE_VISUAL_TYPES = (
    "title_splash",        # Full-bleed title card, animated ring / badge
    "alert_card",          # High-contrast severity callout with pulse ring
    "stat_blocks",         # 2-4 metric tiles (source-grounded data only)
    "steps_flow",          # Numbered sequential steps / animated checklist
    "network_diagram",     # Animated node-link graph (systems / actors)
    "timeline",            # Horizontal chronological event strip
    "bar_chart",           # Horizontal bar chart (source-grounded values only)
    "text_reveal",         # Cinematic full-width text / quote reveal
    "comparison_split",    # Two-column before/after or A-vs-B layout
    "document_excerpt",    # Framed document / advisory excerpt card
    "recommendation_list", # Staggered actionable bullet recommendations
    "summary_card",        # Closing key-takeaway card
)

# Doc-type -> preferred interior visual-type sequence.
# Scene 1 is always title_splash; last scene is summary_card when ≥3 scenes.
_DOCTYPE_VISUAL_AFFINITY: dict = {
    "cyber_advisory":   ("alert_card", "network_diagram", "steps_flow",    "stat_blocks",    "recommendation_list"),
    "threat_report":    ("alert_card", "stat_blocks",     "timeline",       "network_diagram","recommendation_list"),
    "cyber_incident":   ("alert_card", "timeline",        "network_diagram","stat_blocks",    "steps_flow"),
    "news_article":     ("text_reveal","timeline",        "document_excerpt","comparison_split","summary_card"),
    "research_paper":   ("stat_blocks","bar_chart",       "text_reveal",    "comparison_split","summary_card"),
    "policy_document":  ("document_excerpt","steps_flow", "recommendation_list","text_reveal","summary_card"),
    "announcement":     ("text_reveal","recommendation_list","comparison_split","stat_blocks","summary_card"),
    "general":          ("text_reveal","steps_flow",      "stat_blocks",    "recommendation_list","summary_card"),
}


def _classify_document_type(text: str, facts: dict) -> str:
    """Keyword-heuristic document classifier. Never calls the LLM."""
    corpus = " ".join([
        str(text or "")[:3000],
        str(facts.get("title") or ""),
        str(facts.get("summary") or ""),
        str(facts.get("severity") or ""),
        " ".join(facts.get("cve_ids") or []),
        " ".join(facts.get("affected_systems") or []),
    ]).lower()

    if any(t in corpus for t in ("breach", "intrusion", "ransomware", "malware", "exfiltrat",
                                  "lateral movement", "attack chain", "compromised", "incident report")):
        return "cyber_incident"
    if any(t in corpus for t in ("civn-", "advisory", "vulnerability note", "cert-in", "cert in",
                                  "cve-", "cvss", "vulnerability", "patch")):
        return "cyber_advisory"
    if any(t in corpus for t in ("threat report", "threat intelligence", "threat actor", "apt",
                                  "campaign", "indicator of compromise", "mitre att&ck")):
        return "threat_report"
    if any(t in corpus for t in ("abstract", "methodology", "conclusion", "literature review",
                                  "hypothesis", "experiment", "findings", "research paper")):
        return "research_paper"
    if any(t in corpus for t in ("policy", "regulation", "compliance", "framework", "mandate",
                                  "guideline", "directive", "nist", "iso 27001")):
        return "policy_document"
    if any(t in corpus for t in ("we are pleased", "we are proud", "launch", "announce",
                                  "introducing", "partnership", "new release", "press release")):
        return "announcement"
    if any(t in corpus for t in ("reported", "according to", "journalist", "breaking", "exclusive")):
        return "news_article"
    return "general"


def _infer_scene_visual_type(scene_index: int, total_scenes: int,
                              doc_type: str, scene: dict) -> str:
    """
    Assign one scene_visual_type per scene.
    Priority: valid LLM value → content heuristics → positional affinity table.
    """
    # 1. LLM-supplied (pass-through)
    raw = str(scene.get("scene_visual_type") or scene.get("visual_type") or "").lower().strip()
    if raw in _SCENE_VISUAL_TYPES:
        return raw

    # 2. Content heuristics
    metrics = scene.get("metrics") or []
    actions = _as_text_list(scene.get("actions") or scene.get("key_actions") or
                            scene.get("recommended_actions") or [])
    points  = _as_text_list(scene.get("key_points") or [])
    blob    = " ".join(str(scene.get(k, "")) for k in (
        "visual_prompt", "description", "narration", "title", "heading")).lower()

    if scene_index == 1:
        return "title_splash"
    if scene_index == total_scenes and total_scenes >= 3:
        return "summary_card"
    if any(t in blob for t in ("alert", "critical", "breach", "incident", "exploit", "cve", "vulnerability")):
        return "alert_card"
    if metrics and len(metrics) >= 2:
        return "stat_blocks"
    if any(t in blob for t in ("timeline", "chronolog", "sequence of events")):
        return "timeline"
    if any(t in blob for t in ("network", "lateral", "infrastructure", "server", "node", "endpoint", "topology")):
        return "network_diagram"
    if any(t in blob for t in ("step", "procedure", "patch", "mitigat", "remediat", "deploy", "how to")):
        return "steps_flow"
    if actions and len(actions) >= 2:
        return "recommendation_list"
    if any(t in blob for t in ("comparison", "before", "after", " vs ", "versus", "contrast")):
        return "comparison_split"
    if len(points) >= 2:
        return "text_reveal"

    # 3. Positional affinity
    affinity = _DOCTYPE_VISUAL_AFFINITY.get(doc_type, _DOCTYPE_VISUAL_AFFINITY["general"])
    interior = [t for t in affinity if t not in ("title_splash", "summary_card")]
    if interior:
        return interior[(scene_index - 2) % len(interior)]
    return "text_reveal"


def _build_visual_data(scene: dict, visual_type: str) -> dict:
    """
    Extract source-grounded structured data for the given visual_type.
    Never invents numbers, names, or relationships.
    Falls back gracefully when required data is absent — the returned dict's
    'type' key is the effective (possibly downgraded) visual type.
    """
    vd: dict = {"type": visual_type}

    if visual_type in ("stat_blocks", "bar_chart"):
        metrics = scene.get("metrics") or []
        items: list = []
        for m in metrics[:4]:
            if isinstance(m, dict):
                label = _pick_text(m.get("label"), m.get("name"))
                value = _pick_text(m.get("value"), m.get("detail"))
                if label or value:
                    items.append({"label": label or value, "value": value or label})
        if items:
            vd["items"] = items
        else:
            vd["type"] = "text_reveal"
            vd["text"] = _pick_text(scene.get("narration"), scene.get("description"),
                                    scene.get("title"), scene.get("heading"))

    elif visual_type == "steps_flow":
        raw = (scene.get("actions") or scene.get("key_actions") or
               scene.get("recommended_actions") or scene.get("key_points") or [])
        steps = _as_text_list(raw)[:6]
        if steps:
            vd["steps"] = steps
        else:
            vd["type"] = "text_reveal"
            vd["text"] = _pick_text(scene.get("narration"), scene.get("description"),
                                    scene.get("title"), scene.get("heading"))

    elif visual_type == "recommendation_list":
        raw = (scene.get("actions") or scene.get("key_actions") or
               scene.get("recommended_actions") or scene.get("key_points") or [])
        items = _as_text_list(raw)[:7]
        if items:
            vd["items"] = items
        else:
            vd["type"] = "text_reveal"
            vd["text"] = _pick_text(scene.get("narration"), scene.get("description"))

    elif visual_type == "timeline":
        raw = (scene.get("key_points") or scene.get("actions") or [])
        events = _as_text_list(raw)[:6]
        if events:
            vd["events"] = events
        else:
            vd["type"] = "text_reveal"
            vd["text"] = _pick_text(scene.get("narration"), scene.get("description"))

    elif visual_type == "network_diagram":
        nodes: list = []
        for item in _as_text_list(scene.get("affected_systems") or []):
            nodes.append(str(item)[:30])
        for cve in _as_text_list(scene.get("cve_ids") or []):
            nodes.append(str(cve))
        if not nodes:
            words = (scene.get("title") or scene.get("heading") or "").split()
            nodes = [" ".join(words[i:i+2]) for i in range(0, min(len(words), 8), 2)]
        vd["nodes"] = [n for n in nodes if n][:6]
        if not vd["nodes"]:
            vd["type"] = "alert_card"
            vd["text"] = _pick_text(scene.get("narration"), scene.get("description"))

    elif visual_type == "comparison_split":
        vd["left_label"]  = _pick_text(scene.get("comparison_before"), "Before")
        vd["right_label"] = _pick_text(scene.get("comparison_after"),  "After")
        vd["text"] = _pick_text(scene.get("narration"), scene.get("description"))

    elif visual_type == "document_excerpt":
        excerpt = _pick_text(scene.get("narration"), scene.get("description"), scene.get("visual_prompt"))
        vd["text"] = excerpt[:500] if excerpt else ""
        if not vd["text"]:
            vd["type"] = "text_reveal"
            vd["text"] = _pick_text(scene.get("title"), scene.get("heading"))

    else:
        # title_splash, alert_card, text_reveal, summary_card
        vd["text"] = _pick_text(scene.get("narration"), scene.get("description"),
                                scene.get("title"), scene.get("heading"))

    return vd


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
    affected_systems = _as_text_list(raw.get("affected_systems"))
    if affected_systems:
        scene["affected_systems"] = affected_systems
    cve_ids = _as_text_list(raw.get("cve_ids") or raw.get("cves") or [])
    if cve_ids:
        scene["cve_ids"] = cve_ids

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

    # Classify the source document so visual-type affinity can vary by category.
    source_text_hint = _pick_text(facts.get("summary"), facts.get("title"))
    doc_type = _classify_document_type(source_text_hint, facts)

    # Client-side "Code-as-Motion" script: enum-validated per scene and backfilled
    # from the blueprint severity, so partial or legacy payloads still animate.
    fallback_theme = _map_severity_to_motion(_pick_text(raw.get("severity"), facts.get("severity")))
    motion_script = []
    total_scenes = len(scenes)
    for position, scene in enumerate(scenes, 1):
        theme = scene.get("theme_severity") or fallback_theme
        anim_style = scene.get("animation_style") or _infer_motion_style(
            position, theme, scene.get("metrics") or []
        )
        scene["scene_id"] = position
        scene["theme_severity"] = theme
        scene["animation_style"] = anim_style

        # --- NEW: visual type + data ---
        vtype = _infer_scene_visual_type(position, total_scenes, doc_type, scene)
        vdata = _build_visual_data(scene, vtype)
        # vdata["type"] may have been downgraded inside _build_visual_data
        effective_vtype = vdata.get("type", vtype)
        scene["scene_visual_type"] = effective_vtype
        scene["visual_data"]       = vdata

        motion_script.append({
            "scene_id": position,
            "heading": _pick_text(scene.get("heading"), scene.get("title"), scene.get("on_screen_text")),
            "subtext": _pick_text(scene.get("subtext"), scene.get("narration"), scene.get("description")),
            "theme_severity": theme,
            "active_icon": _pick_text(scene.get("active_icon")) or "shield",
            "animation_style": anim_style,
            "duration_seconds": scene["duration_seconds"],
            # New fields consumed by the upgraded Code-as-Motion renderer
            "scene_visual_type": effective_vtype,
            "visual_data": vdata,
        })

    # Variety guard. Small local models tend to emit one enum value for every
    # scene; when the reel has no variety at all, re-derive the motion direction
    # from each scene's own grounded copy so the animation still changes shape.
    # Anything the model did vary is left exactly as it chose.
    if len(motion_script) >= 3:
        if len({entry["animation_style"] for entry in motion_script}) == 1:
            for position, entry in enumerate(motion_script, 1):
                scene = scenes[position - 1]
                anim_style = _infer_motion_style(position, entry["theme_severity"], scene.get("metrics") or [])
                entry["animation_style"] = anim_style
                scene["animation_style"] = anim_style
            if len({entry["animation_style"] for entry in motion_script}) == 1:
                for position, entry in enumerate(motion_script, 1):
                    anim_style = _MOTION_STYLES[(position - 1) % len(_MOTION_STYLES)]
                    entry["animation_style"] = anim_style
                    scenes[position - 1]["animation_style"] = anim_style
        if len({entry["active_icon"] for entry in motion_script}) == 1:
            for position, entry in enumerate(motion_script, 1):
                scene = scenes[position - 1]
                icon = _infer_motion_icon(scene.get("visual_prompt"), scene.get("description"),
                                          scene.get("narration"), scene.get("title"))
                entry["active_icon"] = icon
                scene["active_icon"] = icon
        # Visual-type variety guard: if every scene got the same type, force rotation
        if len({entry["scene_visual_type"] for entry in motion_script}) == 1:
            affinity = _DOCTYPE_VISUAL_AFFINITY.get(doc_type, _DOCTYPE_VISUAL_AFFINITY["general"])
            for position, entry in enumerate(motion_script, 1):
                forced = affinity[(position - 1) % len(affinity)]
                scene = scenes[position - 1]
                vdata = _build_visual_data(scene, forced)
                effective = vdata.get("type", forced)
                entry["scene_visual_type"] = effective
                entry["visual_data"]       = vdata
                scene["scene_visual_type"] = effective
                scene["visual_data"]       = vdata

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
            "doc_type": doc_type,
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
12. When a scene covers facts that involve a sequence of steps, actions, or mitigations, populate "actions" as a numbered list of concise source-backed items (max 6).
13. When a scene references specific measurable facts (counts, percentages, CVE scores, system counts, etc.), populate "metrics" with those exact source-grounded values as {{"label":"...", "value":"..."}} pairs.
14. When a scene presents key factual callouts or timeline events, populate "key_points" as a list of short, source-grounded phrases.
15. For scenes covering affected systems or network scope, populate the "affected_systems" list with the specific named systems from the source.
16. Ensure every scene contains the richest possible set of structured fields (actions, metrics, key_points, affected_systems) that the source facts support — these drive distinct visual layouts.

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
      "affected_systems": ["System A", "System B"],
      "metrics": [{{"label": "fact label", "value": "fact value"}}],
      "actions": ["source-backed mitigation step"],
      "key_points": ["concise source-grounded callout"]
    }}
  ]
}}
"metrics", "actions", "key_points", and "affected_systems" are optional per scene; include them only when the facts support them. "scene_id", "heading", "subtext", "theme_severity", "active_icon", and "animation_style" are required on every scene and must use only the enum values listed above.
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
    """
    Draw a scene visual frame. Dispatches on scene_visual_type when present;
    falls back to the legacy layout-number system for backward compatibility.
    All text and data come exclusively from the scene dict — nothing is invented.
    """
    draw = _safe_draw(draw)
    palette = (scene.get("_design") or {}).get("palette", {})
    theme_accent = palette.get("accent")
    visual_text = " ".join(str(scene.get(key, "")) for key in (
        "visual_prompt", "visual_description", "on_screen_text", "title", "description", "narration",
    )).lower()
    # Derive accent colour: palette → content-based → severity
    if isinstance(theme_accent, str) and len(theme_accent) == 7:
        accent = tuple(int(theme_accent[i:i+2], 16) for i in (1, 3, 5))
    elif scene.get("theme_severity") == "critical":
        accent = (255, 83, 93)
    elif scene.get("theme_severity") == "warning":
        accent = (255, 176, 32)
    else:
        accent = (66, 220, 207)
    blue, panel, ink = (77, 150, 235), (19, 35, 55), (224, 236, 248)

    vtype   = str(scene.get("scene_visual_type") or "").strip()
    vdata   = scene.get("visual_data") or {}
    # If visual_data has a downgraded type, use that
    if isinstance(vdata, dict) and vdata.get("type"):
        vtype = vdata["type"]

    # -----------------------------------------------------------------------
    # Dispatch on scene_visual_type (new path)
    # -----------------------------------------------------------------------
    if vtype == "title_splash":
        _draw_title_splash(draw, scene, accent, blue, panel, ink)
    elif vtype == "alert_card":
        _draw_alert_card(draw, scene, accent, blue, panel, ink)
    elif vtype in ("stat_blocks", "bar_chart"):
        items = vdata.get("items") if isinstance(vdata, dict) else None
        if items:
            _draw_stat_blocks(draw, items, accent, blue, panel, ink)
        else:
            _draw_text_reveal(draw, scene, accent, blue, panel, ink)
    elif vtype == "steps_flow":
        steps = vdata.get("steps") if isinstance(vdata, dict) else None
        if steps:
            _draw_steps_flow(draw, steps, accent, blue, panel, ink)
        else:
            _draw_text_reveal(draw, scene, accent, blue, panel, ink)
    elif vtype == "recommendation_list":
        items = vdata.get("items") if isinstance(vdata, dict) else None
        if items:
            _draw_recommendation_list(draw, items, accent, blue, panel, ink)
        else:
            _draw_text_reveal(draw, scene, accent, blue, panel, ink)
    elif vtype == "timeline":
        events = vdata.get("events") if isinstance(vdata, dict) else None
        if events:
            _draw_timeline(draw, events, accent, blue, panel, ink)
        else:
            _draw_text_reveal(draw, scene, accent, blue, panel, ink)
    elif vtype == "network_diagram":
        nodes = vdata.get("nodes") if isinstance(vdata, dict) else None
        if nodes:
            _draw_network_diagram(draw, nodes, scene.get("heading", ""), accent, blue, panel, ink)
        else:
            _draw_text_reveal(draw, scene, accent, blue, panel, ink)
    elif vtype == "comparison_split":
        _draw_comparison_split(draw, vdata or {}, accent, blue, panel, ink)
    elif vtype == "document_excerpt":
        _draw_document_excerpt(draw, vdata or {}, accent, blue, panel, ink)
    elif vtype in ("text_reveal", "summary_card"):
        _draw_text_reveal(draw, scene, accent, blue, panel, ink)
    else:
        # -----------------------------------------------------------------------
        # Legacy path (blueprints without scene_visual_type)
        # -----------------------------------------------------------------------
        headline = _pick_text(scene.get("title"), scene.get("on_screen_text"))
        metrics  = _scene_metrics(scene)
        actions  = _scene_text_items(scene, "actions", "key_actions", "recommended_actions")
        points   = _scene_text_items(scene, "key_points")
        intent   = str(scene.get("intent", "")).lower().replace("-", "_").replace(" ", "_")
        layout   = _LEGACY_INTENT_LAYOUTS.get(intent)
        if layout is None:
            if metrics:           layout = 3
            elif actions:         layout = 4
            elif len(points) >= 2:layout = 2
            elif int(scene.get("scene_number", 1) or 1) == 1: layout = 1
            else:                 layout = 5
        if layout == 1 and not headline: layout = 5
        elif layout == 2 and len(points or actions) < 2: layout = 5
        elif layout == 3 and not metrics: layout = 5
        elif layout == 4 and not actions: layout = 5

        if layout == 1:
            draw.rounded_rectangle((760, 205, 1150, 485), radius=34, fill=(38, 24, 37), outline=accent, width=4)
            draw.polygon([(955, 242), (1095, 438), (815, 438)], fill=accent)
            draw.text((916, 300), "!", font=get_font(112, True), fill="white")
            draw.rounded_rectangle((130, 280, 665, 405), radius=24, fill=panel, outline=blue, width=3)
            headline_font = get_font(34, True)
            for li, line in enumerate(_fit_text_lines(draw, headline, headline_font, 470, 2)):
                draw.text((180, 312 + li * 40), line, font=headline_font, fill=ink)
        elif layout == 2:
            nodes2 = (points or actions)[:3]
            span = 1080 - 275
            for i, node in enumerate(nodes2):
                x = 125 + (i * span // (len(nodes2) - 1) if len(nodes2) > 1 else 0)
                draw.rounded_rectangle((x, 285, x + 275, 440), radius=22, fill=panel, outline=accent if i == 0 else blue, width=4)
                draw.ellipse((x + 102, 230, x + 172, 300), fill=accent if i == 0 else blue)
                nf = get_font(24 if len(node) > 56 else 28, True)
                for li, line in enumerate(_fit_text_lines(draw, node, nf, 215, 2)):
                    draw.text((x + 30, 330 + li * 36), line, font=nf, fill=ink)
                if i < len(nodes2) - 1:
                    tip = x + 275
                    draw.line((tip + 8, 362, tip + 88, 362), fill=accent, width=8)
                    draw.polygon([(tip + 88, 347), (tip + 118, 362), (tip + 88, 377)], fill=accent)
        elif layout == 3:
            for i, (label, value) in enumerate(metrics[:3]):
                x = 95 + i * 400
                draw.rounded_rectangle((x, 250, x + 350, 465), radius=28, fill=panel, outline=accent if i == 0 else blue, width=4)
                fs = max(23, min(40, int(290 / max(1, len(value) / 18))))
                for li, line in enumerate(_fit_text_lines(draw, value, get_font(fs, True), 295, 3)):
                    draw.text((x + 24, 292 + li * 48), line, font=get_font(fs, True), fill=accent if i == 0 else ink)
                if label and label != value:
                    draw.text((x + 24, 420), label[:24].upper(), font=get_font(18, True), fill=blue)
        elif layout == 4:
            draw.rounded_rectangle((210, 220, 1080, 500), radius=26, fill=panel, outline=blue, width=3)
            for i, action in enumerate(actions[:4]):
                y = 265 + i * 55
                draw.ellipse((255, y, 285, y + 30), fill=accent)
                af = get_font(20 if len(action) > 74 else 23)
                for li, line in enumerate(_fit_text_lines(draw, action, af, 700, 2)):
                    draw.text((315, y - 3 + li * 25), line, font=af, fill=ink)
        else:
            draw.rounded_rectangle((170, 220, 1110, 490), radius=26, fill=panel, outline=blue, width=3)
            for i, w in enumerate((680, 500, 750, 430)):
                y = 275 + i * 48
                draw.rounded_rectangle((255, y, 255 + w, y + 18), radius=8, fill=(39, 59, 83))
                draw.rounded_rectangle((255, y, 255 + int(w * (.48 + .12 * (i % 3))), y + 18), radius=8, fill=accent if i == 0 else blue)
            draw.ellipse((920, 265, 1020, 365), fill=(29, 108, 91), outline=(76, 211, 166), width=4)
            draw.line((945, 315, 970, 338, 1001, 292), fill="white", width=9)


# --- New visual-type draw helpers (MP4 offline path) ---

def _draw_title_splash(draw, scene, accent, blue, panel, ink):
    """Full-bleed title with large ring accent."""
    title = _pick_text(scene.get("title"), scene.get("heading"), scene.get("on_screen_text"))
    sub   = _pick_text(scene.get("subtext"), scene.get("description"))
    # Large decorative ring
    draw.ellipse((900, 160, 1200, 560), outline=accent, width=6)
    draw.ellipse((940, 200, 1160, 520), outline=(*accent[:3],), width=2)
    # Title text — font size adapts to length, y advances after every line
    tf = get_font(min(52, max(28, int(900 / max(1, len(title) / 20)))), True)
    line_h = tf.size + 10          # consistent line-height for this font size
    y = 230
    for line in _fit_text_lines(draw, title, tf, 760, 3):
        draw.text((90, y), line, font=tf, fill=ink)
        y += line_h
    # Sub text starts below the last title line with a fixed gap
    if sub:
        sf = get_font(22)
        sub_y = y + 18             # clear gap below title
        for line in _fit_text_lines(draw, sub, sf, 760, 2):
            draw.text((90, sub_y), line, font=sf, fill=blue)
            sub_y += sf.size + 6


def _draw_alert_card(draw, scene, accent, blue, panel, ink):
    """High-contrast alert card with severity ring."""
    title = _pick_text(scene.get("heading"), scene.get("title"))
    sev   = str(scene.get("theme_severity") or "info").upper()
    desc  = _pick_text(scene.get("subtext"), scene.get("description"), scene.get("narration"))
    # Severity band
    draw.rectangle((0, 185, WIDTH, 210), fill=accent)
    draw.text((60, 188), sev, font=get_font(16, True), fill=(8, 15, 27))
    # Card
    draw.rounded_rectangle((60, 225, 1220, 490), radius=20, fill=panel, outline=accent, width=3)
    # Alert icon area
    draw.ellipse((80, 240, 140, 300), fill=accent)
    draw.text((104, 250), "!", font=get_font(36, True), fill=(8, 15, 27))
    # Title
    tf = get_font(min(36, max(22, int(700 / max(1, len(title) / 22)))), True)
    y = 255
    for line in _fit_text_lines(draw, title, tf, 1040, 2):
        draw.text((160, y), line, font=tf, fill=ink); y += tf.size + 6
    # Description
    if desc:
        df = get_font(20)
        for line in _fit_text_lines(draw, desc, df, 1040, 4):
            draw.text((160, y + 8), line, font=df, fill=(180, 200, 220)); y += df.size + 4


def _draw_stat_blocks(draw, items, accent, blue, panel, ink):
    """2-4 metric tiles side by side."""
    n = min(4, len(items))
    tile_w, tile_h = (1100 // n) - 20, 220
    x0 = (WIDTH - (n * (tile_w + 20))) // 2
    for i, item in enumerate(items[:n]):
        x = x0 + i * (tile_w + 20)
        y = 245
        col = accent if i == 0 else blue
        draw.rounded_rectangle((x, y, x + tile_w, y + tile_h), radius=18,
                                fill=panel, outline=col, width=3)
        val   = str(item.get("value", ""))
        label = str(item.get("label", ""))
        fs = max(20, min(44, int(330 / max(1, len(val) / 12))))
        vf = get_font(fs, True)
        for li, line in enumerate(_fit_text_lines(draw, val, vf, tile_w - 24, 2)):
            draw.text((x + 12, y + 28 + li * (fs + 4)), line, font=vf, fill=col)
        if label:
            lf = get_font(16, True)
            draw.text((x + 12, y + tile_h - 36), label[:28].upper(), font=lf, fill=blue)


def _draw_steps_flow(draw, steps, accent, blue, panel, ink):
    """Numbered sequential steps / checklist."""
    draw.rounded_rectangle((70, 200, 1210, 510), radius=20, fill=panel, outline=blue, width=2)
    n = min(5, len(steps))
    row_h = min(56, (280 // max(1, n)))
    for i, step in enumerate(steps[:n]):
        y = 225 + i * (row_h + 8)
        num = str(i + 1)
        # Circle number badge
        draw.ellipse((88, y, 88 + 34, y + 34), fill=accent if i == 0 else blue)
        draw.text((88 + 9, y + 5), num, font=get_font(18, True), fill=(8, 15, 27))
        # Step text
        sf = get_font(19 if len(step) > 80 else 22)
        for li, line in enumerate(_fit_text_lines(draw, step, sf, 1050, 2)):
            draw.text((136, y + li * 24), line, font=sf, fill=ink)
        # Connector line (not after last)
        if i < n - 1:
            mid_x = 88 + 17
            draw.line((mid_x, y + 34, mid_x, y + 34 + 8), fill=accent, width=2)


def _draw_recommendation_list(draw, items, accent, blue, panel, ink):
    """Staggered bullet recommendation list."""
    draw.rounded_rectangle((70, 195, 1210, 510), radius=20, fill=panel, outline=blue, width=2)
    n = min(6, len(items))
    row_h = min(50, 280 // max(1, n))
    for i, item in enumerate(items[:n]):
        y = 220 + i * (row_h + 6)
        col = accent if i % 2 == 0 else blue
        # Bullet diamond
        mid_y = y + 12
        draw.polygon([(88, mid_y), (100, mid_y - 8), (112, mid_y), (100, mid_y + 8)], fill=col)
        rf = get_font(19 if len(item) > 85 else 22)
        for li, line in enumerate(_fit_text_lines(draw, item, rf, 1040, 2)):
            draw.text((124, y + li * 23), line, font=rf, fill=ink)


def _draw_timeline(draw, events, accent, blue, panel, ink):
    """Horizontal timeline strip."""
    n = min(5, len(events))
    if n == 0:
        return
    rail_y = 360
    x0, x1 = 100, 1180
    draw.line((x0, rail_y, x1, rail_y), fill=blue, width=3)
    span = (x1 - x0) // max(1, n - 1) if n > 1 else 0
    for i, event in enumerate(events[:n]):
        x = x0 + i * span if n > 1 else (x0 + x1) // 2
        col = accent if i == 0 else blue
        draw.ellipse((x - 10, rail_y - 10, x + 10, rail_y + 10), fill=col)
        # Alternating above/below
        text_y = rail_y - 90 if i % 2 == 0 else rail_y + 22
        tf = get_font(16 if len(event) > 50 else 18)
        for li, line in enumerate(_fit_text_lines(draw, event, tf, 210, 3)):
            draw.text((x - 105, text_y + li * 20), line, font=tf, fill=ink)
        # Tick
        draw.line((x, rail_y - 10, x, rail_y + 10), fill=col, width=2)


def _draw_network_diagram(draw, nodes, heading, accent, blue, panel, ink):
    """Simple hub-and-spoke node diagram."""
    n = min(5, len(nodes))
    cx, cy = 640, 355
    # Hub
    draw.ellipse((cx - 44, cy - 44, cx + 44, cy + 44), fill=accent, outline=ink, width=2)
    hub_label = (heading[:12] + "…") if len(heading) > 12 else heading
    draw.text((cx - 38, cy - 10), hub_label, font=get_font(14, True), fill=(8, 15, 27))
    # Spokes
    import math as _math
    for i, node in enumerate(nodes[:n]):
        angle = (2 * _math.pi * i / n) - _math.pi / 2
        r = 230
        nx = int(cx + r * _math.cos(angle))
        ny = int(cy + r * _math.sin(angle))
        draw.line((cx, cy, nx, ny), fill=blue, width=2)
        draw.ellipse((nx - 30, ny - 22, nx + 30, ny + 22), fill=panel, outline=blue, width=2)
        nf = get_font(13 if len(node) > 16 else 15, True)
        for li, line in enumerate(_fit_text_lines(draw, node, nf, 52, 2)):
            draw.text((nx - 26, ny - 10 + li * 16), line, font=nf, fill=ink)


def _draw_comparison_split(draw, vdata, accent, blue, panel, ink):
    """Two-column before/after layout."""
    left  = str(vdata.get("left_label",  "Before"))
    right = str(vdata.get("right_label", "After"))
    body  = str(vdata.get("text", ""))
    mid   = WIDTH // 2
    draw.rounded_rectangle((55,  215, mid - 15, 490), radius=16, fill=panel, outline=blue,   width=3)
    draw.rounded_rectangle((mid + 15, 215, 1225, 490), radius=16, fill=panel, outline=accent, width=3)
    lf = get_font(28, True)
    draw.text((90,  228), left[:20],  font=lf, fill=blue)
    draw.text((mid + 50, 228), right[:20], font=lf, fill=accent)
    if body:
        bf = get_font(18)
        half = len(body) // 2
        for li, line in enumerate(_fit_text_lines(draw, body[:half], bf, mid - 100, 5)):
            draw.text((90, 275 + li * 26), line, font=bf, fill=ink)
        for li, line in enumerate(_fit_text_lines(draw, body[half:], bf, mid - 100, 5)):
            draw.text((mid + 50, 275 + li * 26), line, font=bf, fill=ink)
    # Divider
    draw.line((mid, 230, mid, 480), fill=(55, 75, 100), width=1)


def _draw_document_excerpt(draw, vdata, accent, blue, panel, ink):
    """Framed document/report excerpt."""
    text = str(vdata.get("text", ""))[:400]
    # Page frame
    draw.rounded_rectangle((140, 190, 1140, 510), radius=8, fill=(14, 26, 42), outline=blue, width=2)
    # Header bar
    draw.rectangle((140, 190, 1140, 218), fill=blue)
    draw.text((155, 196), "DOCUMENT EXCERPT", font=get_font(14, True), fill="white")
    # Three fake ruled lines at top for paper feel
    for i in range(3):
        draw.line((168, 230 + i * 4, 1120, 230 + i * 4), fill=(30, 50, 70), width=1)
    # Body text
    tf = get_font(18)
    y = 240
    for line in _fit_text_lines(draw, text, tf, 940, 10):
        if y > 490:
            break
        draw.text((168, y), line, font=tf, fill=(200, 218, 236)); y += 24


def _draw_text_reveal(draw, scene, accent, blue, panel, ink):
    """Cinematic full-width text / quote card."""
    text = _pick_text(scene.get("narration"), scene.get("description"),
                      scene.get("title"), scene.get("heading"))
    # Accent side bar
    draw.rectangle((55, 210, 72, 490), fill=accent)
    draw.rounded_rectangle((90, 210, 1220, 490), radius=14, fill=panel, outline=(40, 60, 80), width=1)
    tf_size = max(18, min(34, int(800 / max(1, len(text) / 40))))
    tf = get_font(tf_size)
    y = 248
    for line in _fit_text_lines(draw, text, tf, 1080, 8):
        if y > 470:
            break
        draw.text((108, y), line, font=tf, fill=ink); y += tf_size + 6


# ---------------------------------------------------------
# LOCAL ONNX NEURAL CHARACTER ANIMATION
# ---------------------------------------------------------

def _first_existing_dir(*candidates):
    for candidate in candidates:
        path = Path(candidate)
        if path.is_dir():
            return path
    return Path(candidates[0])


def _asset_roots():
    """Resolve model, motion, and character directories under my_code or the repo."""
    models = _first_existing_dir(
        _MY_CODE_ROOT / "models" / "liveportrait_onnx",
        _REPO_ROOT / "models" / "liveportrait_onnx",
        _MY_CODE_ROOT / "models" / "tpsmm_onnx",
        _REPO_ROOT / "models" / "tpsmm_onnx",
    )
    tpsmm = _first_existing_dir(
        _MY_CODE_ROOT / "models" / "tpsmm_onnx",
        _REPO_ROOT / "models" / "tpsmm_onnx",
    )
    motion = _first_existing_dir(
        _MY_CODE_ROOT / "assets" / "motion",
        _REPO_ROOT / "assets" / "motion",
    )
    characters = _first_existing_dir(
        _MY_CODE_ROOT / "assets" / "characters",
        _REPO_ROOT / "assets" / "characters",
    )
    for path in (models, tpsmm, motion, characters):
        path.mkdir(parents=True, exist_ok=True)
    return {"liveportrait": models, "tpsmm": tpsmm, "motion": motion, "characters": characters}


def _character_placement(scene=None, blueprint=None):
    placement = dict(DEFAULT_CHARACTER_PLACEMENT)
    for source in (blueprint or {}, scene or {}):
        blob = source.get("character_placement") or source.get("character") or {}
        if isinstance(blob, dict):
            for key in DEFAULT_CHARACTER_PLACEMENT:
                if key in blob:
                    try:
                        placement[key] = float(blob[key])
                    except (TypeError, ValueError):
                        pass
    return placement


def resolve_motion_template(scene, motion_dir=None):
    """Map scene severity / intent onto a local driving-motion video."""
    roots = _asset_roots()
    motion_dir = Path(motion_dir or roots["motion"])
    blob = " ".join(
        str((scene or {}).get(key) or "")
        for key in ("theme_severity", "severity", "animation_style", "intent", "title")
    ).lower()
    if any(token in blob for token in ("alert", "warning", "critical", "pulse", "urgent")):
        preferred = motion_dir / "alert_explain.mp4"
    else:
        preferred = motion_dir / "idle_talk.mp4"
    if preferred.is_file():
        return str(preferred)
    for fallback in sorted(motion_dir.glob("*.mp4")):
        return str(fallback)
    return str(preferred)


def _write_default_presenter_png(path):
    """Create a front-facing presenter crop so the neural layer has a source avatar."""
    if Image is None:
        return False
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    size = 512
    image = Image.new("RGB", (size, size), (18, 32, 48))
    draw = ImageDraw.Draw(image)
    draw.ellipse((40, 330, 472, 620), fill=(28, 58, 92))
    draw.ellipse((118, 70, 394, 390), fill=(232, 196, 164))
    draw.pieslice((108, 40, 404, 280), 180, 0, fill=(42, 32, 28))
    draw.ellipse((168, 168, 228, 218), fill=(250, 250, 250))
    draw.ellipse((284, 168, 344, 218), fill=(250, 250, 250))
    draw.ellipse((186, 180, 216, 210), fill=(40, 70, 110))
    draw.ellipse((302, 180, 332, 210), fill=(40, 70, 110))
    draw.polygon([(256, 210), (238, 268), (274, 268)], fill=(214, 164, 132))
    draw.arc((198, 270, 314, 338), 20, 160, fill=(168, 70, 80), width=6)
    image.save(path)
    return True


def _write_default_motion_clip(path, mode="idle"):
    """Write a short driving video with blinking and head-like motion for ONNX control extraction."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if cv2 is None or np is None:
        return False
    fps, seconds = 30, 3
    frames = fps * seconds
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (NEURAL_CROP_SIZE, NEURAL_CROP_SIZE))
    if not writer.isOpened():
        return False
    amplitude = 18 if mode == "alert" else 8
    for index in range(frames):
        t = index / fps
        canvas = np.full((NEURAL_CROP_SIZE, NEURAL_CROP_SIZE, 3), 28, dtype=np.uint8)
        dx = int(amplitude * math.sin(2 * math.pi * t / (0.8 if mode == "alert" else 1.6)))
        dy = int((amplitude // 2) * math.sin(2 * math.pi * t / (1.1 if mode == "alert" else 2.2)))
        cx, cy = 128 + dx, 118 + dy
        cv2.circle(canvas, (cx, cy + 40), 70, (40, 70, 110), -1)
        cv2.circle(canvas, (cx, cy), 54, (210, 180, 150), -1)
        blink = 1 if (t % (1.4 if mode == "alert" else 2.8)) < 0.12 else 8
        cv2.ellipse(canvas, (cx - 18, cy - 8), (10, blink), 0, 0, 360, (30, 30, 30), -1)
        cv2.ellipse(canvas, (cx + 18, cy - 8), (10, blink), 0, 0, 360, (30, 30, 30), -1)
        mouth = 4 + int(6 * abs(math.sin(2 * math.pi * t * (5 if mode == "alert" else 3))))
        cv2.ellipse(canvas, (cx, cy + 22), (16, mouth), 0, 0, 360, (90, 50, 70), -1)
        writer.write(canvas)
    writer.release()
    return path.is_file() and path.stat().st_size > 0


def ensure_neural_assets():
    """Create default presenter and driving-motion files when they are missing."""
    roots = _asset_roots()
    presenter = roots["characters"] / "presenter.png"
    idle = roots["motion"] / "idle_talk.mp4"
    alert = roots["motion"] / "alert_explain.mp4"
    if not presenter.is_file():
        _write_default_presenter_png(presenter)
    if not idle.is_file():
        _write_default_motion_clip(idle, "idle")
    if not alert.is_file():
        _write_default_motion_clip(alert, "alert")
    return {
        "presenter": str(presenter) if presenter.is_file() else None,
        "idle_talk": str(idle) if idle.is_file() else None,
        "alert_explain": str(alert) if alert.is_file() else None,
    }


def _onnx_providers():
    """Prefer DirectML on Windows, then CPU. Never require CUDA."""
    if not ONNX_RUNTIME_AVAILABLE:
        return []
    available = set(ort.get_available_providers())
    providers = []
    for name in ("DmlExecutionProvider", "DirectMLExecutionProvider"):
        if name in available:
            providers.append(name)
            break
    if "CPUExecutionProvider" in available:
        providers.append("CPUExecutionProvider")
    return providers or ["CPUExecutionProvider"]


def _image_to_nchw(image):
    rgb = image.convert("RGB").resize((NEURAL_CROP_SIZE, NEURAL_CROP_SIZE), Image.Resampling.BILINEAR)
    array = np.asarray(rgb, dtype=np.float32) / 255.0
    return np.transpose(array, (2, 0, 1))[None, ...]


def _nchw_to_uint8(batch):
    frame = np.clip(batch[0], 0.0, 1.0)
    frame = np.transpose(frame, (1, 2, 0))
    return (frame * 255.0).astype(np.uint8)


def _load_driving_frames(video_path, limit=90):
    frames = []
    if not video_path or not os.path.isfile(video_path) or cv2 is None:
        return frames
    capture = cv2.VideoCapture(str(video_path))
    try:
        while len(frames) < limit:
            ok, frame = capture.read()
            if not ok:
                break
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (NEURAL_CROP_SIZE, NEURAL_CROP_SIZE))
            frames.append(frame)
    finally:
        capture.release()
    return frames


def _controls_from_driving_frames(frames, count):
    """Convert driving-video motion into LivePortrait-distilled pose/expression vectors."""
    poses = []
    expressions = []
    if frames:
        gray0 = np.mean(frames[0], axis=2)
        yy, xx = np.mgrid[0:NEURAL_CROP_SIZE, 0:NEURAL_CROP_SIZE]
        for index in range(count):
            frame = frames[index % len(frames)]
            gray = np.mean(frame, axis=2)
            weight = gray + 1.0
            cx = float(np.average(xx, weights=weight))
            cy = float(np.average(yy, weights=weight))
            cx0 = float(np.average(xx, weights=gray0 + 1.0))
            cy0 = float(np.average(yy, weights=gray0 + 1.0))
            yaw = np.clip((cx - cx0) / 20.0, -1.0, 1.0)
            pitch = np.clip((cy0 - cy) / 14.0, -1.0, 1.0)
            eye = float(np.mean(gray[70:110, 90:166]))
            mouth = float(np.mean(gray[150:200, 96:160]))
            expr = np.zeros((30,), dtype=np.float32)
            blink = np.clip((90.0 - eye) / 40.0, -1.0, 1.0)
            talk = np.clip((mouth - 70.0) / 50.0, -1.0, 1.0)
            expr[7:12] = blink
            expr[14:21] = talk
            poses.append(np.array([yaw, pitch, 0.15 * yaw], dtype=np.float32))
            expressions.append(expr)
        return poses, expressions
    for index in range(count):
        t = index / max(NEURAL_INTERNAL_FPS, 1)
        yaw = 0.35 * math.sin(2 * math.pi * t / 2.4)
        pitch = 0.18 * math.sin(2 * math.pi * t / 3.1)
        blink = 1.0 if (t % 3.2) < 0.12 else 0.0
        talk = 0.55 * abs(math.sin(2 * math.pi * t * 3.5))
        expr = np.zeros((30,), dtype=np.float32)
        expr[7:12] = blink
        expr[14:21] = talk
        poses.append(np.array([yaw, pitch, 0.08 * yaw], dtype=np.float32))
        expressions.append(expr)
    return poses, expressions


class NeuralAnimationEngine:
    """Load a local LivePortrait/TPSMM ONNX graph and animate a cropped avatar only."""

    def __init__(self, model_dir=None):
        self.available = False
        self.provider = None
        self.unavailable_reason = "not initialized"
        self._extractor = None
        self._generator = None
        self._tpsmm = None
        self.kind = None
        roots = _asset_roots()
        self.model_dir = Path(model_dir) if model_dir else roots["liveportrait"]
        self.tpsmm_dir = roots["tpsmm"]
        self._initialize()

    def _initialize(self):
        if not ONNX_RUNTIME_AVAILABLE:
            self.unavailable_reason = "onnxruntime is not installed"
            return
        if np is None or Image is None:
            self.unavailable_reason = "numpy/Pillow are required to run the neural layer"
            return
        providers = _onnx_providers()
        live_gen = self.model_dir / "LP-Distilled0.1.onnx"
        live_ext = self.model_dir / "appearance_feature_extractor.onnx"
        tpsmm = None
        for candidate in (
            self.tpsmm_dir / "tpsmm.onnx",
            self.tpsmm_dir / "generator.onnx",
            self.model_dir / "tpsmm.onnx",
        ):
            if candidate.is_file():
                tpsmm = candidate
                break
        try:
            so = ort.SessionOptions()
            so.log_severity_level = 3
            if live_gen.is_file() and live_ext.is_file():
                self._extractor = ort.InferenceSession(str(live_ext), sess_options=so, providers=providers)
                self._generator = ort.InferenceSession(str(live_gen), sess_options=so, providers=providers)
                self.kind = "liveportrait_distilled"
                self.provider = (self._generator.get_providers() or providers)[0]
                self.available = True
                self.unavailable_reason = ""
                return
            if tpsmm is not None:
                self._tpsmm = ort.InferenceSession(str(tpsmm), sess_options=so, providers=providers)
                self.kind = "tpsmm"
                self.provider = (self._tpsmm.get_providers() or providers)[0]
                self.available = True
                self.unavailable_reason = ""
                return
            self.unavailable_reason = f"no ONNX checkpoints in {self.model_dir} or {self.tpsmm_dir}"
        except Exception as exc:
            self.unavailable_reason = str(exc)
            self.available = False

    def animate(self, source_avatar_path, driving_motion_path, frame_count):
        """Return RGB uint8 frames for the cropped character region only."""
        if not self.available:
            raise RuntimeError(self.unavailable_reason or "neural animation is unavailable")
        if not source_avatar_path or not os.path.isfile(source_avatar_path):
            raise RuntimeError("character avatar asset is missing")
        frame_count = max(1, int(frame_count))
        source = Image.open(source_avatar_path)
        source_nchw = _image_to_nchw(source)
        driving = _load_driving_frames(driving_motion_path)
        if self._generator is not None and self._extractor is not None:
            feature = self._extractor.run(None, {"img": source_nchw})[0]
            poses, expressions = _controls_from_driving_frames(driving, frame_count)
            frames = []
            for pose, expr in zip(poses, expressions):
                rgb = self._generator.run(None, {
                    "feature_3d": feature,
                    "pose_control_vector": pose.reshape(1, 3),
                    "input_rgb": source_nchw,
                    "expression_control_vector": expr.reshape(1, 30),
                })[0]
                frames.append(_nchw_to_uint8(rgb))
            return frames
        if self._tpsmm is not None:
            inputs = self._tpsmm.get_inputs()
            frames = []
            driving_source = driving or [np.asarray(source.convert("RGB").resize((NEURAL_CROP_SIZE, NEURAL_CROP_SIZE)))]
            for index in range(frame_count):
                drive = driving_source[index % len(driving_source)]
                drive_nchw = np.transpose(drive.astype(np.float32) / 255.0, (2, 0, 1))[None, ...]
                feed = {}
                for item in inputs:
                    name = item.name.lower()
                    feed[item.name] = drive_nchw if "driv" in name else source_nchw
                if len(feed) == 1 and inputs:
                    feed = {inputs[0].name: source_nchw}
                    if len(inputs) > 1:
                        feed[inputs[1].name] = drive_nchw
                rgb = self._tpsmm.run(None, feed)[0]
                frames.append(_nchw_to_uint8(rgb))
            return frames
        raise RuntimeError("no usable ONNX animation session is loaded")


class SceneCompositor:
    """Keep the slide canvas pixel-crisp and overlay only the cropped character frames."""

    def __init__(self, placement=None):
        self.placement = dict(placement or DEFAULT_CHARACTER_PLACEMENT)

    def render_base(self, scene, output_path, total_scenes):
        create_scene_image(scene, output_path, total_scenes)
        return Image.open(output_path).convert("RGB")

    def overlay(self, base_image, character_frame, placement=None):
        placement = placement or self.placement
        canvas = base_image.convert("RGBA")
        width, height = canvas.size
        box_w = max(32, int(width * float(placement.get("width_rel", 0.30))))
        box_h = max(32, int(height * float(placement.get("height_rel", 0.45))))
        x = int(width * float(placement.get("x_rel", 0.05)))
        y = int(height * float(placement.get("y_rel", 0.50)))
        if character_frame is None:
            return canvas.convert("RGB")
        if hasattr(character_frame, "convert"):
            avatar = character_frame.convert("RGBA")
        else:
            array = np.asarray(character_frame)
            avatar = Image.fromarray(array).convert("RGBA")
        avatar = avatar.resize((box_w, box_h), Image.Resampling.BICUBIC)
        mask = Image.new("L", avatar.size, 0)
        ImageDraw.Draw(mask).ellipse((4, 4, box_w - 5, box_h - 5), fill=255)
        alpha = avatar.split()[-1]
        alpha = Image.fromarray(
            (np.asarray(alpha, dtype=np.float32) * np.asarray(mask, dtype=np.float32) / 255.0).astype(np.uint8)
        )
        opacity = float(placement.get("opacity", 1.0))
        if opacity < 1.0:
            alpha = Image.fromarray((np.asarray(alpha, dtype=np.float32) * opacity).astype(np.uint8))
        avatar.putalpha(alpha)
        canvas.alpha_composite(avatar, (x, y))
        return canvas.convert("RGB")


def _render_fallback_scene(base_image, avatar_image, placement=None):
    """Deterministic canvas plus an optional static character overlay."""
    compositor = SceneCompositor(placement)
    return compositor.overlay(base_image, avatar_image, placement)


def _static_avatar_frame(avatar_path):
    if not avatar_path or not os.path.isfile(avatar_path) or Image is None:
        return None
    return Image.open(avatar_path).convert("RGBA").resize((NEURAL_CROP_SIZE, NEURAL_CROP_SIZE))


# ---------------------------------------------------------
# SCENE IMAGE & VIDEO RENDERING
# ---------------------------------------------------------

def create_scene_image(scene: dict, output_path: str, total_scenes: int, character_frame=None):
    """Render one scene frame using the visual-type draw system.

    The old 'SCENE n/N' counter, 'VISUAL' panel box, and auto-injected
    presenter avatar have been removed — they cluttered every frame and made
    every scene look identical regardless of content.  The full canvas is now
    owned by draw_scene_visual() so each visual type fills the space cleanly.
    """
    blueprint = scene.get("_design", {})
    palette   = blueprint.get("palette", {})
    as_rgb    = lambda value, fallback: (
        tuple(int(value[i:i+2], 16) for i in (1, 3, 5))
        if isinstance(value, str) and len(value) == 7 else fallback
    )
    background = as_rgb(palette.get("primary"), (8, 15, 27))
    accent     = as_rgb(palette.get("accent"),  (40, 150, 255))

    image = Image.new("RGB", (WIDTH, HEIGHT), background)
    draw  = _safe_draw(ImageDraw.Draw(image))

    # Thin top accent line — the only fixed chrome element kept.
    draw.rectangle((0, 0, WIDTH, 4), fill=accent)

    # Scene visual (fills the whole canvas now).
    draw_scene_visual(draw, scene)

    image.save(output_path)


def _animate_scene_frame(get_frame, t: float, duration: float, scene: dict,
                         accent: tuple[int, int, int], elapsed_before: float,
                         total_duration: float):
    """Composite a lower-third narration band and a progress rail onto each rendered frame.

    The floating title text that used to appear at y≈92 has been removed — the
    visual-type renderers (draw_scene_visual) already draw the scene heading
    inside the canvas, so a second floating title only cluttered the frame.

    The lower-third is a slim translucent band pinned to the bottom edge of the
    frame.  It eases in once (over the first 0.4 s) and stays visible for the
    rest of the scene.  The narration text inside it reveals progressively in
    sync with the voiceover.  The progress rail sits below it as a 5-pixel bar.
    """
    frame  = np.asarray(get_frame(t), dtype=np.uint8)
    canvas = Image.fromarray(frame).convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw   = _safe_draw(ImageDraw.Draw(overlay))
    white  = (248, 250, 252, 255)

    narration = str(scene.get("narration") or scene.get("narration_text") or "")
    scene_num = int(scene.get("scene_number", 1) or 1)

    # --- Lower-third band ---
    # Eases up from below the frame over the first 0.4 s, then stays put.
    ease = min(1.0, max(0.0, t / 0.40))
    ease = ease * ease * (3.0 - 2.0 * ease)           # smooth-step

    band_h  = 110                                      # total band height in px
    band_y  = int(HEIGHT - band_h * ease)              # slides up from below

    # Gradient fill: transparent at top edge → dark at bottom
    for row in range(band_h):
        alpha = int(210 * (row / band_h) ** 0.6)
        y_abs = band_y + row
        if 0 <= y_abs < HEIGHT:
            draw.rectangle((0, y_abs, WIDTH, y_abs), fill=(6, 13, 26, alpha))

    # Accent left strip
    if ease > 0.05:
        draw.rectangle((0, band_y, 4, HEIGHT), fill=(*accent, 220))

    # "VOICEOVER / 01" label chip
    label_y = band_y + 12
    if label_y + 20 < HEIGHT:
        draw.rounded_rectangle((18, label_y, 160, label_y + 20), radius=10,
                                fill=(*accent, 220))
        draw.text((24, label_y + 2),
                  f"VOICEOVER / {scene_num:02d}",
                  font=get_font(11, True), fill=(8, 14, 26, 255))

    # Narration text — reveals progressively in sync with audio
    spoken_frac = min(1.0, max(0.0, (t + 0.15) / max(duration, 0.1)))
    visible     = narration[:max(1, int(len(narration) * spoken_frac))] if narration else ""
    if visible:
        sub_size = max(14, min(19, int(1100 / max(1, len(narration) / 55))))
        sub_font = get_font(sub_size)
        sub_y    = band_y + 38
        for idx, line in enumerate(_fit_text_lines(draw, visible, sub_font, WIDTH - 40, 3)):
            y_pos = sub_y + idx * (sub_size + 4)
            if y_pos + sub_size < HEIGHT - 6:
                draw.text((20, y_pos), line, font=sub_font, fill=white)

    # --- Progress rail (5 px, flush at bottom) ---
    progress = min(1.0, max(0.0, (elapsed_before + t) / max(total_duration, 0.1)))
    rail_h   = 5
    rail_y   = HEIGHT - rail_h
    # Background track
    draw.rectangle((0, rail_y, WIDTH, HEIGHT), fill=(20, 32, 52, 255))
    # Filled portion
    filled_w = int(WIDTH * progress)
    if filled_w > 0:
        draw.rectangle((0, rail_y, filled_w, HEIGHT), fill=(*accent, 255))
    # Playhead dot
    if 0 < filled_w < WIDTH:
        dot_x = filled_w
        draw.ellipse((dot_x - 5, rail_y - 3, dot_x + 5, HEIGHT + 3),
                     fill=(*accent, 255))

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

    # Neural presenter layer: make sure the avatar/motion assets exist, then load the engine.
    assets = ensure_neural_assets()
    neural_engine = NeuralAnimationEngine()
    logger.info(
        "Neural animation engine available=%s provider=%s reason=%s",
        neural_engine.available, neural_engine.provider, neural_engine.unavailable_reason,
    )

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
            scene_duration = scene_durations[index]

            # Generate the character motion frame; on any failure create_scene_image
            # falls back to the static presenter avatar.
            char_frame = None
            if neural_engine.available and assets.get("presenter"):
                motion_path = resolve_motion_template(scene_visual)
                frame_count = max(1, min(int(round(scene_duration * NEURAL_INTERNAL_FPS)), 30))
                try:
                    char_frames = neural_engine.animate(assets["presenter"], motion_path, frame_count)
                    if char_frames:
                        char_frame = char_frames[len(char_frames) // 2]
                except Exception as exc:
                    logger.warning("Neural animation failed for scene %s: %s", scene_number, exc)
                    char_frame = None
            create_scene_image(scene_visual, image_path, len(scenes), character_frame=char_frame)

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