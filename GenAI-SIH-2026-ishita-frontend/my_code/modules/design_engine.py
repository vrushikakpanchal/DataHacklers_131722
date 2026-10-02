"""Content-aware visual themes shared by infographic, deck, and video renderers."""
from __future__ import annotations

import re
from typing import Any


PALETTES = {
    "cyber": {"primary": "#0F172A", "secondary": "#1E293B", "accent": "#0284C7", "highlight": "#38BDF8", "success": "#10B981", "warning": "#F59E0B", "background": "#F8FAFC", "surface": "#FFFFFF", "dark_surface": "#1E293B", "ink": "#0F172A", "muted": "#64748B", "border": "#E2E8F0"},
    "finance": {"primary": "#14213D", "secondary": "#1F3A5F", "accent": "#B98524", "highlight": "#10B981", "success": "#10B981", "warning": "#F59E0B", "background": "#F8FAFC", "surface": "#FFFFFF", "dark_surface": "#1E293B", "ink": "#172033", "muted": "#64748B", "border": "#E2E8F0"},
    "technical": {"primary": "#172554", "secondary": "#334155", "accent": "#0284C7", "highlight": "#14B8A6", "success": "#10B981", "warning": "#F59E0B", "background": "#F8FAFC", "surface": "#FFFFFF", "dark_surface": "#1E293B", "ink": "#0F172A", "muted": "#64748B", "border": "#E2E8F0"},
    "general": {"primary": "#0F172A", "secondary": "#334155", "accent": "#0284C7", "highlight": "#10B981", "success": "#10B981", "warning": "#F59E0B", "background": "#F8FAFC", "surface": "#FFFFFF", "dark_surface": "#1E293B", "ink": "#0F172A", "muted": "#64748B", "border": "#E2E8F0"},
}

TYPOGRAPHY = {"family": "Segoe UI, Inter, Arial, sans-serif", "title_px": 24, "subtitle_px": 14, "body_px": 11, "line_height": 1.45}
SPACING = {"page": 32, "card": 24, "gutter": 20, "radius": 14}


def as_items(value: Any) -> list[Any]:
    """Normalize optional model fields so a scalar response cannot break rendering."""
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple, set)) else [value]


def infer_design(canonical_facts: dict[str, Any] | None) -> dict[str, Any]:
    """Infer a stable visual system and layout intent from available source facts."""
    facts = canonical_facts or {}
    fact_lists = as_items(facts.get("cve_ids")) + as_items(facts.get("affected_systems")) + as_items(facts.get("recommended_actions"))
    corpus = (" ".join(str(facts.get(k, "")) for k in ("title", "summary", "topic", "category", "content_type")) + " " + " ".join(map(str, fact_lists))).lower()
    severity = str(facts.get("severity", "")).upper()
    if any(word in corpus for word in ("financial", "revenue", "market", "investment", "budget", "bank")):
        theme = "finance"
    elif any(word in corpus for word in ("technical report", "architecture", "engineering", "system design")):
        theme = "technical"
    elif any(word in corpus for word in ("cyber", "security", "threat", "vulnerability", "malware", "ransomware", "cve")) or severity in {"CRITICAL", "HIGH"}:
        theme = "cyber"
    else:
        theme = "general"
    actions = as_items(facts.get("recommended_actions") or facts.get("key_points"))
    metrics = as_items(facts.get("metrics"))
    indicators = as_items(facts.get("cve_ids") or facts.get("locked_ips"))
    if any(word in corpus for word in ("timeline", "milestone", "history", "roadmap")):
        layout = "timeline"
    elif any(word in corpus for word in ("process", "workflow", "sequence", "architecture", "steps")):
        layout = "process_flow"
    elif any(word in corpus for word in ("versus", " vs ", "comparison", "before and after")):
        layout = "split_comparison"
    elif metrics or indicators:
        layout = "metric_dashboard"
    else:
        layout = "recommendation_matrix"
    severity_color = {"CRITICAL": "#B42332", "HIGH": "#D14B3F", "MEDIUM": "#D28A25", "LOW": "#34866D"}.get(severity)
    palette = dict(PALETTES[theme])
    palette["severity"] = severity_color or palette["warning"]
    topic = re.sub(r"[^a-z0-9 ]", "", str(facts.get("topic") or theme)).strip().lower()
    icon = "shield" if theme == "cyber" else "chart" if theme == "finance" else "network" if theme == "technical" else "spark"
    motif = "hexagon" if theme == "cyber" else "line_chart" if theme == "finance" else "grid" if theme == "technical" else "circles"
    return {"theme": theme, "topic": topic, "palette": palette, "severity_color": palette["severity"], "layout": layout, "icon": icon, "motif": motif, "typography": dict(TYPOGRAPHY), "spacing": dict(SPACING), "action_count": len(actions), "metric_count": len(metrics), "indicator_count": len(indicators)}


def svg_icon(name: str, x: int, y: int, color: str = "#FFFFFF", size: int = 24) -> str:
    """Small inline icon set; SVG paths remain self-contained and portable."""
    paths = {
        "shield": '<path d="M12 2 21 6v5c0 5-3.8 9-9 11-5.2-2-9-6-9-11V6z"/><path d="m8 12 2.5 2.5L16 9"/>',
        "lock": '<rect x="4" y="10" width="16" height="12" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v3"/>',
        "alert": '<path d="M12 3 2.5 20h19z"/><path d="M12 9v4m0 3h.01"/>',
        "server": '<rect x="3" y="3" width="18" height="8" rx="2"/><rect x="3" y="13" width="18" height="8" rx="2"/><path d="M7 7h.01M7 17h.01M11 7h6m-6 10h6"/>',
        "check": '<circle cx="12" cy="12" r="9"/><path d="m8 12 2.5 2.5L16 9"/>',
        "chart": '<path d="M4 19V5M4 19h17M8 15l4-5 3 3 5-7"/>',
        "network": '<circle cx="12" cy="12" r="3"/><circle cx="4" cy="5" r="2"/><circle cx="20" cy="5" r="2"/><circle cx="4" cy="19" r="2"/><circle cx="20" cy="19" r="2"/><path d="m10 10-5-4m9 4 5-4m-9 8-5 4m9-4 5 4"/>',
        "spark": '<path d="m12 2 1.8 7.2L21 12l-7.2 1.8L12 21l-1.8-7.2L3 12l7.2-2.8z"/>',
    }
    return f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{paths.get(name, paths["spark"])}</svg>'
