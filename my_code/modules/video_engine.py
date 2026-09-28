import os
import json
import tempfile
import requests
import pyttsx3
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips, vfx, afx
from modules.design_engine import infer_design

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

def generate_video_blueprint(
    text: str,
    target_audience: str = "General",
    tone: str = "Informative",
    language: str = "English",
    duration: str = "60s",
    objective: str = "Summarize threat advisory",
    style: str = "Cybersecurity Technical"
) -> dict:
    """
    Sends the source document and video metadata to local Ollama (qwen2.5:3b)
    to generate a structured video script JSON blueprint.
    """
    text = text[:12000]

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
   - "intent": One of title_alert, attack_flow, metrics, mitigation, evidence_dashboard
   - "on_screen_text": Short scene title
   - "visual_description": Visual cues string
   - "narration": Voiceover/narration text string
   - "duration_seconds": Estimated duration integer
   - "metrics": Optional list of source-backed {{"label": string, "value": string}} items; never invent numbers
   - "actions": Optional list of source-backed mitigation steps
   - "key_points": Optional list of concise, source-grounded visual callouts
Every scene must have a distinct intent where the source supports it. Keep text brief enough for a 16:9 card.
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
        result = json.loads(raw_response)
    except (json.JSONDecodeError, KeyError) as e:
        raise RuntimeError(f"Failed to parse JSON response from Ollama: {e}")

    return result


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

def draw_india_visual(draw):
    draw = _safe_draw(draw)
    points = [
        (500, 275), (555, 250), (610, 265), (650, 300), (690, 325),
        (675, 365), (650, 400), (625, 440), (610, 490), (585, 535),
        (565, 500), (550, 455), (525, 420), (500, 380), (475, 345), (460, 310)
    ]
    draw.polygon(points, fill=(35, 75, 120), outline=(80, 170, 255))

    locations = [(540, 315), (590, 350), (620, 390), (575, 430), (600, 470)]
    for x, y in locations:
        draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill=(255, 70, 70))
        draw.ellipse((x - 17, y - 17, x + 17, y + 17), outline=(255, 100, 100), width=2)

    draw.text(
        (455, 550),
        "RANSOMWARE ACTIVITY",
        font=get_font(24, bold=True),
        fill=(255, 100, 100)
    )


def draw_vm_visual(draw):
    draw = _safe_draw(draw)
    draw.rounded_rectangle(
        (400, 270, 850, 475),
        radius=20,
        fill=(24, 42, 65),
        outline=(70, 150, 230),
        width=3
    )
    draw.text(
        (440, 300),
        "VIRTUAL MACHINE",
        font=get_font(32, bold=True),
        fill=(110, 190, 255)
    )

    for y in [355, 405]:
        draw.rounded_rectangle((450, y, 800, y + 30), radius=8, fill=(40, 60, 85))
        draw.ellipse((470, y + 8, 482, y + 20), fill=(80, 220, 130))

    draw.polygon([(900, 300), (965, 420), (835, 420)], fill=(210, 55, 55))
    draw.text((890, 340), "!", font=get_font(60, bold=True), fill="white")


def draw_terminal_visual(draw):
    draw = _safe_draw(draw)
    draw.rounded_rectangle(
        (350, 245, 930, 475),
        radius=12,
        fill=(8, 12, 18),
        outline=(70, 150, 230),
        width=3
    )
    draw.rectangle((350, 245, 930, 285), fill=(30, 45, 65))
    draw.ellipse((370, 258, 382, 270), fill=(220, 80, 80))
    draw.ellipse((390, 258, 402, 270), fill=(230, 180, 60))
    draw.ellipse((410, 258, 422, 270), fill=(70, 190, 100))

    terminal_font = get_font(25)
    commands = [
        "PS C:\\System>",
        "Get-Process",
        "Get-Service",
        "Invoke-Command",
        "Access granted..."
    ]

    y = 305
    for command in commands:
        draw.text((390, y), command, font=terminal_font, fill=(100, 220, 150))
        y += 32


def draw_server_visual(draw):
    draw = _safe_draw(draw)
    server_positions = [(300, 275), (520, 275), (740, 275)]
    labels = ["DATABASE", "ESXi", "NAS"]

    for (x, y), label in zip(server_positions, labels):
        draw.rounded_rectangle(
            (x, y, x + 170, y + 210),
            radius=15,
            fill=(25, 43, 65),
            outline=(70, 150, 230),
            width=3
        )
        draw.text(
            (x + 25, y + 25),
            label,
            font=get_font(24, bold=True),
            fill=(110, 190, 255)
        )

        for row in range(3):
            draw.rectangle(
                (x + 30, y + 75 + row * 38, x + 140, y + 100 + row * 38),
                fill=(45, 65, 90)
            )
            draw.ellipse(
                (x + 40, y + 82 + row * 38, x + 52, y + 94 + row * 38),
                fill=(80, 220, 130)
            )

    draw.polygon([(570, 500), (630, 590), (510, 590)], fill=(220, 60, 60))
    draw.text((555, 515), "!", font=get_font(45, bold=True), fill="white")


def draw_security_visual(draw):
    draw = _safe_draw(draw)
    draw.rounded_rectangle(
        (350, 240, 930, 470),
        radius=15,
        fill=(18, 32, 50),
        outline=(70, 150, 230),
        width=3
    )

    for i in range(4):
        y = 290 + i * 38
        draw.rectangle((400, y, 850, y + 15), fill=(40, 65, 90))
        draw.rectangle((400, y, 620 + i * 40, y + 15), fill=(70, 180, 130))

    draw.text(
        (400, 425),
        "THREAT INTELLIGENCE",
        font=get_font(25, bold=True),
        fill=(110, 190, 255)
    )

    shield = [
        (1000, 260), (1080, 290), (1060, 430),
        (1000, 490), (940, 430), (920, 290)
    ]
    draw.polygon(shield, fill=(35, 130, 90), outline=(100, 230, 170))
    draw.line([(955, 370), (985, 405), (1050, 335)], fill="white", width=12)


def draw_scene_visual(draw, scene: dict):
    """Draw a distinct, content-aware scene template using a dark visual canvas."""
    draw = _safe_draw(draw)
    n = int(scene.get("scene_number", 1))
    intent = str(scene.get("intent", "")).lower().replace("-", "_").replace(" ", "_")
    intent_templates = {
        "title_alert": 1, "alert": 1, "opening": 1,
        "attack_flow": 2, "data_flow": 2, "architecture": 2,
        "metrics": 3, "metric_highlights": 3, "impact_metrics": 3,
        "mitigation": 4, "actions": 4, "response_steps": 4,
        "evidence_dashboard": 5, "evidence": 5, "summary": 5,
    }
    n = intent_templates.get(intent, n)
    visual_text = " ".join(str(scene.get(key, "")) for key in ("visual_description", "visual_recommendation", "on_screen_text", "narration")).lower()
    palette = (scene.get("_design") or {}).get("palette", {})
    theme_accent = palette.get("accent")
    accent = tuple(int(theme_accent[i:i+2], 16) for i in (1, 3, 5)) if isinstance(theme_accent, str) and len(theme_accent) == 7 else ((66, 220, 207) if any(x in visual_text for x in ("finance", "revenue", "market", "budget")) else (255, 83, 93))
    blue, panel, ink = (77, 150, 235), (19, 35, 55), (224, 236, 248)
    if n == 1:
        # Alert/title template with a high contrast signal marker.
        draw.rounded_rectangle((760, 205, 1150, 485), radius=34, fill=(38, 24, 37), outline=accent, width=4)
        draw.polygon([(955, 242), (1095, 438), (815, 438)], fill=accent)
        draw.text((916, 300), "!", font=get_font(112, True), fill="white")
        draw.rounded_rectangle((130, 280, 665, 405), radius=24, fill=panel, outline=blue, width=3)
        draw.text((180, 315), "ALERT  /  BRIEFING", font=get_font(38, True), fill=ink)
    elif n == 2:
        # Attack/data flow diagram: segmented nodes connected by directional paths.
        labels = ["SOURCE", "VECTOR", "IMPACT"]
        for i, label in enumerate(labels):
            x = 125 + i * 390
            draw.rounded_rectangle((x, 285, x+275, 440), radius=22, fill=panel, outline=accent if i == 1 else blue, width=4)
            draw.ellipse((x+102, 230, x+172, 300), fill=accent if i == 1 else blue)
            draw.text((x+35, 345), label, font=get_font(30, True), fill=ink)
            if i < 2:
                draw.line((x+280, 365, x+365, 365), fill=accent, width=8)
                draw.polygon([(x+365, 350), (x+395, 365), (x+365, 380)], fill=accent)
    elif n == 3:
        # Oversized metric callouts and compact indicator chips.
        metrics = scene.get("metrics") or scene.get("key_metrics") or []
        callouts = [(str(m.get("label") or "SOURCE METRIC"), str(m.get("value") or "Not specified")) if isinstance(m, dict) else ("SOURCE DETAIL", str(m)) for m in metrics[:3]]
        if not callouts:
            callouts = [("KEY SIGNAL", point) for point in (scene.get("key_points") or [])[:3]]
        if not callouts:
            callouts = [("SOURCE METRIC", "No quantitative metric supplied")]
        for i, (label, value) in enumerate(callouts):
            x = 95 + i*400
            draw.rounded_rectangle((x, 250, x+350, 465), radius=28, fill=panel, outline=accent if i == 0 else blue, width=4)
            font_size = max(23, min(40, int(290 / max(1, len(value) / 18))))
            wrapped = _fit_text_lines(draw, value, get_font(font_size, True), 295, 3)
            for line_index, line in enumerate(wrapped):
                draw.text((x+24, 292+line_index*48), line, font=get_font(font_size, True), fill=accent if i == 0 else ink)
            draw.text((x+24, 420), label[:24].upper(), font=get_font(18, True), fill=blue)
    elif n == 4:
        # Mitigation checklist and progress rail.
        actions = scene.get("actions") or scene.get("recommended_actions") or []
        actions = [str(a) for a in actions[:4]] or ["Identify affected assets", "Apply mitigations", "Validate recovery"]
        draw.rounded_rectangle((210, 220, 1080, 500), radius=26, fill=panel, outline=blue, width=3)
        for i, action in enumerate(actions):
            y = 265 + i*55
            draw.ellipse((255, y, 285, y+30), fill=accent)
            draw.line((263, y+15, 271, y+23, 281, y+8), fill=(255,255,255), width=3)
        fit_font = get_font(20 if len(action) > 74 else 23)
        for line_index, line in enumerate(_fit_text_lines(draw, action, fit_font, 700, 2)):
            draw.text((315, y-3+line_index*25), line, font=fit_font, fill=ink)
    else:
        # Evidence/security dashboard template for remaining scenes.
        draw.rounded_rectangle((170, 220, 1110, 490), radius=26, fill=panel, outline=blue, width=3)
        for i, width in enumerate((680, 500, 750, 430)):
            y = 275 + i*48
            draw.rounded_rectangle((255, y, 255+width, y+18), radius=8, fill=(39, 59, 83))
            draw.rounded_rectangle((255, y, 255+int(width*(.48+.12*(i%3))), y+18), radius=8, fill=accent if i == 0 else blue)
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

        scene_durations = [max(1.0, float(scene.get("duration_seconds", 5)), audio_durations.get(scene["scene_number"], 0.0)) for scene in scenes]
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
    """Build a video from canonical facts and return its blueprint and path."""
    os.makedirs(output_dir, exist_ok=True)
    if isinstance(canonical_facts, dict):
        source_text = json.dumps(canonical_facts, ensure_ascii=False, indent=2)
    else:
        source_text = str(canonical_facts)

    blueprint = generate_video_blueprint(
        text=source_text,
        target_audience="General Public",
        tone="Informative",
        duration="60s"
    )
    video_path = os.path.join(output_dir, "generated_advisory.mp4")
    create_video(blueprint, output_path=video_path)
    return {"blueprint": blueprint, "video_path": video_path}
