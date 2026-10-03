"""Dynamic source-grounded PowerPoint generation adapted from Sanika's prototype."""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

import ollama
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt
from pydantic import BaseModel, Field
from modules.design_engine import infer_design


class SlideContent(BaseModel):
    slide_number: int
    title: str
    layout: str = Field(description="title_and_content, section, or two_content")
    key_points: List[str]
    speaker_notes: str


class PresentationContent(BaseModel):
    presentation_title: str
    slides: List[SlideContent]


_IDENTIFIER_RE = re.compile(r"CVE-\d{4}-\d{4,}|\b\d{1,3}(?:\.\d{1,3}){3}\b", re.IGNORECASE)
_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)
_SEVERITY_WORDS = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
_SUPPORTED_LAYOUTS = {"title_and_content", "section", "two_content"}
_FACT_KEYS = ("title", "summary", "severity", "cve_ids", "affected_systems", "recommended_actions")


def _clip(value: str, limit: int) -> str:
    """Collapse whitespace and clip narrated text with an explicit ellipsis."""
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip(" ,;:-") + "…"


def _as_facts(source_text: str, canonical_facts: Optional[dict] = None) -> dict:
    """Use canonical facts when provided, or recover them if source_text is a JSON fact sheet."""
    if isinstance(canonical_facts, dict) and canonical_facts:
        return canonical_facts
    candidate = str(source_text or "").strip()
    if candidate.startswith("{") and candidate.endswith("}"):
        try:
            parsed = json.loads(candidate)
        except (ValueError, TypeError):
            return {}
        if isinstance(parsed, dict) and any(key in parsed for key in _FACT_KEYS):
            return parsed
    return {}


def analyze_content_scale(source_text: str, canonical_facts: Optional[dict] = None) -> Dict[str, int]:
    """Measure source size and fact complexity to plan a proportional deck depth."""
    raw = str(source_text or "")
    facts = _as_facts(raw, canonical_facts)
    fact_groups = 0
    fact_items = 0
    for value in facts.values():
        if isinstance(value, (list, tuple)):
            entries = [str(entry) for entry in value if str(entry).strip()]
            fact_groups += 1 if entries else 0
            fact_items += len(entries)
    words = len(raw.split())
    segments = len([line for line in re.split(r"(?<=[.!?])\s+|\n{2,}", raw) if len(line.strip()) >= 30])
    identifiers = len({match.group(0).upper() for match in _IDENTIFIER_RE.finditer(raw)})
    score = (
        (1 if words >= 320 else 0)
        + (1 if words >= 900 else 0)
        + (1 if words >= 1800 else 0)
        + (1 if segments >= 8 else 0)
        + (1 if segments >= 20 else 0)
        + (1 if identifiers >= 3 else 0)
        + (1 if identifiers >= 8 else 0)
        + (2 if fact_items >= 6 else 1 if fact_items >= 3 else 0)
        + (1 if fact_groups >= 4 else 0)
    )
    return {
        "words": words,
        "segments": segments,
        "identifiers": identifiers,
        "fact_groups": fact_groups,
        "fact_items": fact_items,
        "planned_slides": max(4, min(10, 4 + score // 2)),
    }


def _source_cve_ids(source_text: str, canonical_facts: Optional[dict] = None) -> List[str]:
    """Collect distinct CVE identifiers present in the source text or locked facts."""
    cve_ids = {match.group(0).upper() for match in _CVE_RE.finditer(str(source_text or ""))}
    raw_cves = _as_facts(source_text, canonical_facts).get("cve_ids") or []
    if isinstance(raw_cves, str):
        raw_cves = [raw_cves]
    for value in raw_cves:
        cve_ids.update(match.group(0).upper() for match in _CVE_RE.finditer(str(value)))
    return sorted(cve_ids)


def _lock_identifiers(structure: dict, source_text: str, canonical_facts: Optional[dict] = None) -> dict:
    """Guarantee every CVE identifier present in the source or facts surfaces verbatim on a slide."""
    cve_ids = _source_cve_ids(source_text, canonical_facts)
    slides = structure.get("slides") or []
    if not cve_ids or not slides:
        return structure
    visible = " ".join(
        [str(structure.get("presentation_title") or "")]
        + [
            f"{slide.get('title') or ''} {' '.join(str(point) for point in (slide.get('key_points') or []))}"
            for slide in slides
        ]
    ).upper()
    missing = [cve for cve in cve_ids if cve not in visible]
    if not missing:
        return structure
    target = next(
        (
            slide
            for slide in slides
            if "vulnerab" in str(slide.get("title") or "").lower()
            or "vulnerab" in " ".join(str(point) for point in (slide.get("key_points") or [])).lower()
        ),
        slides[0],
    )
    points = [str(point) for point in (target.get("key_points") or []) if str(point).strip()]
    points.append("Tracked as " + ", ".join(missing))
    target["key_points"] = points
    return structure


def extract_presentation_structure(
    source_text: str,
    model_name: str = "qwen2.5:3b",
    slide_count: Optional[int] = None,
    canonical_facts: Optional[dict] = None,
) -> dict:
    """Use local Ollama to create a validated, source-grounded slide outline sized to the content."""
    source = str(source_text or "")
    scale = analyze_content_scale(source, canonical_facts)
    planned = slide_count if slide_count and slide_count > 0 else scale["planned_slides"]
    facts = _as_facts(source, canonical_facts)
    cve_ids = _source_cve_ids(source, canonical_facts)
    cve_rule = ""
    if cve_ids:
        cve_rule = (
            f" The source carries the CVE identifier(s) {', '.join(cve_ids)}: every one must appear verbatim "
            "inside a key_point on its most relevant slide."
        )
    system_prompt = (
        "You are a briefing deck architect. Rules:\n"
        "1. Ground every slide title, key point, and speaker note directly in the provided source; never add outside "
        "knowledge, opinions, or assumptions.\n"
        "2. Never emit placeholders or mock content: no bracketed slots ([insert X]), no <TBD>, no 'Lorem ipsum', no "
        "example or sample figures ('XX%'), and no invented numbers, percentages, identifiers, dates, names, "
        "organizations, or statistics. When the source lacks material for a section, leave it out instead of padding "
        "with filler.\n"
        "3. Reproduce technical identifiers (CVE IDs, IP addresses, product names, version numbers) exactly as written "
        f"in the source; never alter digits or casing.{cve_rule}\n"
        f"4. Content volume analysis: about {scale['words']} words, {scale['segments']} substantive segments, "
        f"{scale['identifiers']} distinct technical identifiers, {scale['fact_items']} structured fact items. "
        f"Plan roughly {planned} content slides; adapt the actual count to the source's real structure and use fewer "
        "slides rather than inventing filler.\n"
        "5. Each slide needs a title, 3-5 concise key_points (fewer when the source supports fewer), and "
        "speaker_notes written as a short narration the presenter can read aloud. Pick the layout that fits the "
        "content: 'section' for topic transitions, 'two_content' for paired material, 'title_and_content' otherwise.\n"
        "6. Order the deck so it follows the source's own narrative; never force a fixed template.\n"
        "7. Output only JSON matching the requested schema; do not mention these rules or the analysis."
    )
    facts_block = ""
    if facts:
        compact = {key: value for key, value in facts.items() if value}
        facts_block = (
            "\nLOCKED FACTS (stay consistent with these; add nothing beyond them):\n"
            f"{json.dumps(compact, ensure_ascii=False, default=str)[:4000]}\n"
        )
    user_prompt = (
        f"Build a source-grounded briefing deck for the content below, targeting about {planned} content slides.\n"
        f"JSON SCHEMA:\n{PresentationContent.model_json_schema()}"
        f"{facts_block}\nSOURCE:\n{source[:18000]}"
    )
    response = ollama.chat(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        format=PresentationContent.model_json_schema(),
    )
    content = json.loads(response["message"]["content"])
    structure = PresentationContent.model_validate(content).model_dump()
    return _lock_identifiers(structure, source, canonical_facts)


def build_presentation(structure: dict, output_path: str) -> str:
    """Render every model-authored slide with a content-adaptive layout on a content-derived theme."""
    validated = PresentationContent.model_validate(structure)
    presentation = Presentation()
    presentation.slide_width, presentation.slide_height = Inches(13.333), Inches(7.5)
    source_visual_context = " ".join(" ".join([slide.title, *slide.key_points]) for slide in validated.slides)
    deck_severity = next((word for word in _SEVERITY_WORDS if word in source_visual_context.upper()), "")
    design = infer_design({"title": validated.presentation_title, "summary": source_visual_context, "severity": deck_severity})
    palette = design["palette"]
    rgb = lambda value: RGBColor.from_string(value.lstrip("#"))
    blank = presentation.slide_layouts[6]

    def shape(slide, kind, x, y, w, h, fill, line=None, radius=False):
        item = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else kind, Inches(x), Inches(y), Inches(w), Inches(h))
        item.fill.solid(); item.fill.fore_color.rgb = rgb(fill)
        item.line.color.rgb = rgb(line or palette["border"])
        item.line.width = Pt(0.8)
        return item

    def text(slide, value, x, y, w, h, size=18, color=None, bold=False, align=PP_ALIGN.LEFT):
        box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        frame = box.text_frame; frame.clear(); frame.word_wrap = True
        frame.margin_left = Inches(.04); frame.margin_right = Inches(.04)
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = frame.paragraphs[0]; p.text = str(value); p.alignment = align
        p.font.name = "Segoe UI"; p.font.size = Pt(size); p.font.bold = bold; p.font.color.rgb = rgb(color or palette["ink"])
        return box

    def attach_notes(slide, value):
        if value:
            slide.notes_slide.notes_text_frame.text = str(value)

    def base(title, slide_number, points=()):
        slide = presentation.slides.add_slide(blank)
        slide.background.fill.solid(); slide.background.fill.fore_color.rgb = rgb(palette["background"])
        shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, 13.333, .11, palette["accent"])
        on_severity = bool(deck_severity) and deck_severity in " ".join([title, *points]).upper()
        text(slide, title, .62, .34, 10.4 if on_severity else 11.9, .58, 24, palette["primary"], True)
        shape(slide, MSO_SHAPE.RECTANGLE, .62, 1.02, 12.0, .035, palette["highlight"])
        if on_severity:
            shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 11.4, .4, 1.3, .48, design["severity_color"], radius=True)
            text(slide, deck_severity, 11.4, .52, 1.3, .26, 11, "#FFFFFF", True, PP_ALIGN.CENTER)
        text(slide, f"{design['theme'].upper()} BRIEF  •  {slide_number:02d}", .64, 7.12, 12, .2, 9, palette["muted"], True)
        return slide

    def point_grid(slide, points, columns=None, top=1.6, height=5.2):
        """Lay out bullets in a grid that adapts card size, count, and type size to the content."""
        total = len(points)
        if not total:
            return
        columns = columns or (1 if total <= 1 else 2 if total <= 4 else 3)
        columns = max(1, min(columns, total))
        rows = (total + columns - 1) // columns
        gap = .3
        card_w = (11.9 - gap * (columns - 1)) / columns
        card_h = min(2.75, (height - gap * (rows - 1)) / rows)
        size = 15 if card_w >= 5 else 13 if card_w >= 3.4 else 11
        limit = max(80, int((card_w - 1.25) * (card_h - .3) * 46))
        grid_h = rows * card_h + gap * (rows - 1)
        y0 = top + max(0.0, (height - grid_h)) / 2
        for index, point in enumerate(points):
            col, row = index % columns, index // columns
            x = .72 + col * (card_w + gap)
            y = y0 + row * (card_h + gap)
            shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, card_w, card_h, "#FFFFFF", line=palette["border"], radius=True)
            shape(slide, MSO_SHAPE.RECTANGLE, x, y, .09, card_h, palette["accent"] if index == 0 else palette["highlight"])
            badge = min(.72, max(.48, card_h - .3))
            badge_y = y + (card_h - badge) / 2
            shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x + .26, badge_y, badge, badge, palette["accent"] if index == 0 else palette["highlight"], radius=True)
            text(slide, f"{index + 1:02d}", x + .26, badge_y + .02, badge, badge - .06, 12, "#FFFFFF", True, PP_ALIGN.CENTER)
            text(slide, _clip(point, limit), x + .26 + badge + .18, y + .14, card_w - (.26 + badge + .18) - .2, card_h - .28, size, palette["ink"], index == 0)

    def render_section(item, slide_number):
        slide = presentation.slides.add_slide(blank)
        slide.background.fill.solid(); slide.background.fill.fore_color.rgb = rgb(palette["primary"])
        shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, 13.333, .11, palette["accent"])
        shape(slide, MSO_SHAPE.RECTANGLE, 0, 6.9, 13.333, .6, palette["secondary"])
        text(slide, f"{design['theme'].upper()} BRIEF  •  {slide_number:02d}", .9, 7.03, 11.5, .3, 9, "#FFFFFF", True)
        text(slide, design["topic"].upper(), 1.27, 2.0, 10.8, .35, 12, palette["highlight"], True, PP_ALIGN.CENTER)
        title_size = 34 if len(item.title) <= 42 else 28 if len(item.title) <= 72 else 24
        text(slide, _clip(item.title, 110), 1.27, 2.45, 10.8, 1.1, title_size, "#FFFFFF", True, PP_ALIGN.CENTER)
        bullets = [_clip(point, 80) for point in item.key_points[:3]]
        if bullets:
            text(slide, "   •   ".join(bullets), 1.27, 3.85, 10.8, .9, 15, palette["highlight"], False, PP_ALIGN.CENTER)
        return slide

    items = validated.slides

    cover = presentation.slides.add_slide(blank)
    cover.background.fill.solid(); cover.background.fill.fore_color.rgb = rgb(palette["primary"])
    shape(cover, MSO_SHAPE.RECTANGLE, 0, 0, .24, 7.5, palette["accent"])
    shape(cover, MSO_SHAPE.RECTANGLE, .24, 5.95, 13.1, 1.55, palette["secondary"])
    text(cover, design["topic"].upper() + "  /  BRIEFING", .9, .8, 10.8, .4, 13, palette["highlight"], True)
    shape(cover, MSO_SHAPE.ROUNDED_RECTANGLE, .86, 1.34, 11.6, 1.92, palette["dark_surface"], line=palette["secondary"], radius=True)
    text(cover, validated.presentation_title, 1.18, 1.57, 10.95, 1.45, 30, "#FFFFFF", True)
    chips = (
        _clip(f"{len(items)} CONTENT SLIDES", 24),
        _clip(design["layout"].replace("_", " ").upper(), 24),
        _clip(design["theme"].upper(), 24),
    )
    for index, label in enumerate(chips):
        x = .9 + index * 2.75
        shape(cover, MSO_SHAPE.ROUNDED_RECTANGLE, x, 3.72, 2.45, .58, palette["secondary"], line=palette["highlight"], radius=True)
        text(cover, label, x + .12, 3.84, 2.2, .3, 10, "#FFFFFF", True, PP_ALIGN.CENTER)
    deck_details = sum(len(point.split()) for item in items for point in item.key_points)
    footer_bits = [f"{deck_details} KEY DETAILS ACROSS {len(items)} SLIDES"]
    if deck_severity:
        footer_bits.append(deck_severity)
    text(cover, "  •  ".join(footer_bits), .9, 6.45, 11, .3, 11, "#FFFFFF", True)
    attach_notes(cover, " ".join(item.speaker_notes for item in items[:2] if item.speaker_notes))

    for offset, item in enumerate(items, start=2):
        points = list(item.key_points)
        layout = (item.layout or "").strip().lower()
        if layout not in _SUPPORTED_LAYOUTS:
            layout = "title_and_content"
        if layout == "section" and len(points) > 3:
            layout = "title_and_content"
        if layout == "two_content" and len(points) < 2:
            layout = "title_and_content"
        if layout == "section":
            slide = render_section(item, offset)
        else:
            slide = base(item.title, offset, points=points)
            point_grid(slide, points, columns=2 if layout == "two_content" else None)
        attach_notes(slide, item.speaker_notes)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    presentation.save(output_path)
    return output_path


def generate_dynamic_presentation(
    source_text: str,
    output_path: str = os.path.join("data", "outputs", "dynamic_presentation.pptx"),
    model_name: str = "qwen2.5:3b",
    slide_count: Optional[int] = None,
    canonical_facts: Optional[dict] = None,
) -> tuple[str, dict]:
    """Plan a proportional deck depth, author source-grounded slides via Ollama, then export the PPTX."""
    scale = analyze_content_scale(source_text, canonical_facts)
    planned = slide_count if slide_count and slide_count > 0 else scale["planned_slides"]
    structure = extract_presentation_structure(source_text, model_name, planned, canonical_facts=canonical_facts)
    return build_presentation(structure, output_path), structure
