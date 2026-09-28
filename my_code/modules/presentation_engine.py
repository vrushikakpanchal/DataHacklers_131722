"""Dynamic source-grounded PowerPoint generation adapted from Sanika's prototype."""
from __future__ import annotations

import json
import os
from typing import List

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


def extract_presentation_structure(
    source_text: str,
    model_name: str = "qwen2.5:3b",
    slide_count: int = 5,
) -> dict:
    """Use local Ollama to create a validated, source-grounded slide outline."""
    prompt = f"""Create a concise cybersecurity briefing presentation from the source below.
Return {slide_count} content slides. Use only source facts; preserve identifiers and uncertainty.
Each slide needs a title, 3-5 key_points, layout (title_and_content, section, or two_content),
and speaker_notes written as a brief narration. Return only JSON matching this schema:
{PresentationContent.model_json_schema()}
SOURCE:\n{source_text[:18000]}"""
    response = ollama.chat(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        format=PresentationContent.model_json_schema(),
    )
    content = json.loads(response["message"]["content"])
    return PresentationContent.model_validate(content).model_dump()


def build_presentation(structure: dict, output_path: str) -> str:
    """Build distinct, theme-adaptive slides and retain model-generated speaker notes."""
    validated = PresentationContent.model_validate(structure)
    presentation = Presentation()
    presentation.slide_width, presentation.slide_height = Inches(13.333), Inches(7.5)
    source_visual_context = " ".join(" ".join([slide.title, *slide.key_points]) for slide in validated.slides)
    deck_severity = next((word for word in ("CRITICAL", "HIGH", "MEDIUM", "LOW") if word in source_visual_context.upper()), "")
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

    def base(title, slide_number, background=None):
        slide = presentation.slides.add_slide(blank)
        fill = background or palette["background"]
        slide.background.fill.solid(); slide.background.fill.fore_color.rgb = rgb(fill)
        shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, 13.333, .11, palette["accent"])
        text(slide, title, .62, .34, 11.9, .58, 24, palette["primary"], True)
        shape(slide, MSO_SHAPE.RECTANGLE, .62, 1.02, 12.0, .035, palette["highlight"])
        text(slide, f"{design['theme'].upper()} BRIEF  •  {slide_number:02d}", .64, 7.12, 12, .2, 9, palette["muted"], True)
        return slide

    items = validated.slides
    cover = presentation.slides.add_slide(blank)
    cover.background.fill.solid(); cover.background.fill.fore_color.rgb = rgb(palette["primary"])
    shape(cover, MSO_SHAPE.RECTANGLE, 0, 0, .24, 7.5, palette["accent"])
    shape(cover, MSO_SHAPE.RECTANGLE, .24, 5.95, 13.1, 1.55, palette["secondary"])
    text(cover, design["topic"].upper() + "  /  BRIEFING", .9, .8, 10.8, .4, 13, palette["highlight"], True)
    shape(cover, MSO_SHAPE.ROUNDED_RECTANGLE, .86, 1.34, 11.6, 1.92, palette["dark_surface"], line=palette["secondary"], radius=True)
    text(cover, validated.presentation_title, 1.18, 1.57, 10.95, 1.45, 30, "#FFFFFF", True)
    for index, label in enumerate((f"{len(items)} TOPICS", design["layout"].replace("_", " ").upper(), design["theme"].upper())):
        x = .9 + index * 2.75
        shape(cover, MSO_SHAPE.ROUNDED_RECTANGLE, x, 3.72, 2.45, .58, palette["secondary"], line=palette["highlight"], radius=True)
        text(cover, label, x + .12, 3.84, 2.2, .3, 10, "#FFFFFF", True, PP_ALIGN.CENTER)
    text(cover, "SOURCE-GROUNDED CONTENT  •  ADAPTIVE VISUAL SYSTEM", .9, 6.45, 11, .3, 11, "#FFFFFF", True)
    cover.notes_slide.notes_text_frame.text = "Presentation overview. " + " ".join(item.speaker_notes for item in items[:2])

    # Slide 2: three-column executive overview cards.
    slide = base(items[0].title if items else "Key Highlights", 2)
    highlights = list((items[0].key_points if items else [])[:3])
    highlights += ["Key risk and affected scope", "Priority indicators", "Recommended response"]
    for index, value in enumerate(highlights[:3]):
        x, y = .72 + index * 4.2, 1.62
        shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, 3.78, 4.45, "#FFFFFF", line=palette["border"], radius=True)
        shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x + .28, y + .3, 3.18, .62, palette["background"], line=palette["border"], radius=True)
        text(slide, f"0{index+1}   EXECUTIVE SIGNAL", x + .42, y + .45, 2.92, .26, 10, palette["accent"], True)
        shape(slide, MSO_SHAPE.OVAL, x + .3, y + 1.25, .74, .74, palette["accent"] if index == 0 else palette["highlight"])
        text(slide, f"{index+1:02d}", x + .3, y + 1.43, .74, .28, 13, "#FFFFFF", True, PP_ALIGN.CENTER)
        text(slide, value, x + .32, y + 2.2, 3.12, 1.65, 16, palette["ink"], True)
        shape(slide, MSO_SHAPE.RECTANGLE, x + .32, y + 3.98, .64, .05, palette["accent"])
    slide.notes_slide.notes_text_frame.text = items[0].speaker_notes if items else "Key metrics and highlights."

    # Slide 3: analysis/action split.
    item = items[1] if len(items) > 1 else (items[0] if items else None)
    slide = base(item.title if item else "Analysis & Action", 3)
    severity = next((word for word in ("CRITICAL", "HIGH", "MEDIUM", "LOW") if word in " ".join([item.title, *item.key_points]).upper()), "REVIEW") if item else "REVIEW"
    for col, (heading, color, points) in enumerate((("TECHNICAL ANALYSIS", palette["secondary"], (item.key_points[:3] if item else [])), ("IMPACT & RESPONSE", palette["accent"], (item.key_points[3:] or item.key_points[:2] if item else [])))):
        x = .75 + col * 6.0
        shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, 1.5, 5.55, 4.9, "#FFFFFF", radius=True)
        shape(slide, MSO_SHAPE.RECTANGLE, x, 1.5, 5.55, .62, color)
        text(slide, heading, x + .25, 1.62, 5.0, .3, 15, "#FFFFFF", True)
        if col == 0:
            status_fill = "#FFF1F2" if severity in {"CRITICAL", "HIGH"} else "#FFFBEB"
            status_color = design["severity_color"] if severity in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} else palette["warning"]
            shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x + .3, 2.32, 4.95, .82, status_fill, line=status_color, radius=True)
            text(slide, f"SEVERITY / STATUS     {severity}", x + .52, 2.55, 4.55, .32, 13, status_color, True)
        for index, point in enumerate(points or ["See source-grounded briefing details."]):
            y = (3.4 if col == 0 else 2.45) + index * .92
            shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x + .3, y, 4.95, .7, palette["background"], radius=True)
            text(slide, f"•  {point}", x + .52, y + .1, 4.5, .5, 13, palette["ink"])
    slide.notes_slide.notes_text_frame.text = item.speaker_notes if item else "Analysis and action summary."

    # Slide 4: process flow.
    item = items[2] if len(items) > 2 else (items[-1] if items else None)
    slide = base(item.title if item else "Response Process", 4)
    steps = item.key_points[:5] if item else ["Assess", "Contain", "Remediate", "Validate"]
    for index, point in enumerate(steps):
        x = .65 + index * (12.0 / max(1, len(steps)))
        shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, 2.2, 2.0, 2.25, "#FFFFFF", radius=True)
        shape(slide, MSO_SHAPE.OVAL, x + .68, 1.73, .65, .65, palette["accent"] if index == 0 else palette["highlight"])
        text(slide, str(index+1), x + .68, 1.88, .65, .25, 14, "#FFFFFF", True, PP_ALIGN.CENTER)
        text(slide, point, x + .14, 2.65, 1.72, 1.45, 14, palette["ink"], True, PP_ALIGN.CENTER)
        if index < len(steps)-1:
            shape(slide, MSO_SHAPE.CHEVRON, x + 2.04, 3.05, .35, .5, palette["accent"])
    slide.notes_slide.notes_text_frame.text = item.speaker_notes if item else "Step-by-step response flow."

    # Slide 5: recommendations and close.
    item = items[3] if len(items) > 3 else (items[-1] if items else None)
    slide = base(item.title if item else "Summary & Recommendations", 5)
    points = item.key_points[:6] if item else ["Review key findings", "Apply recommended controls", "Confirm resolution"]
    for index, point in enumerate(points):
        col, row = index % 2, index // 2
        x, y = .78 + col * 6.0, 1.5 + row * 1.62
        shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, 5.52, 1.28, "#FFFFFF", radius=True)
        shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x + .2, y + .22, .66, .7, palette["accent"] if index == 0 else palette["highlight"], radius=True)
        text(slide, f"{index+1:02d}", x + .2, y + .39, .66, .28, 12, "#FFFFFF", True, PP_ALIGN.CENTER)
        text(slide, point, x + 1.02, y + .18, 4.25, .92, 13, palette["ink"], index == 0)
    slide.notes_slide.notes_text_frame.text = item.speaker_notes if item else "Summary and recommended next steps."

    # Preserve additional model-generated content with varied editable cards.
    for index, item in enumerate(items[4:], start=6):
        slide = base(item.title, index)
        cols = 2 if len(item.key_points) > 2 else 1
        for point_index, point in enumerate(item.key_points):
            col, row = point_index % cols, point_index // cols
            x = .8 + col * 6.0; y = 1.5 + row * 1.35
            shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, 5.5, 1.05, "#FFFFFF", radius=True)
            shape(slide, MSO_SHAPE.RECTANGLE, x, y, .09, 1.05, palette["accent"] if point_index == 0 else palette["highlight"])
            text(slide, point, x + .28, y + .13, 5.0, .8, 15, palette["ink"])
        slide.notes_slide.notes_text_frame.text = item.speaker_notes or ""

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    presentation.save(output_path)
    return output_path


def generate_dynamic_presentation(
    source_text: str,
    output_path: str = os.path.join("data", "outputs", "dynamic_presentation.pptx"),
    model_name: str = "qwen2.5:3b",
    slide_count: int = 5,
) -> tuple[str, dict]:
    structure = extract_presentation_structure(source_text, model_name, slide_count)
    return build_presentation(structure, output_path), structure
