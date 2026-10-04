from moviepy import (
    ImageClip,
    AudioFileClip,
    concatenate_videoclips
)

from PIL import Image, ImageDraw, ImageFont
import os


WIDTH = 1280
HEIGHT = 720


def get_font(size, bold=False):

    paths = [
        "C:/Windows/Fonts/arialbd.ttf" if bold
        else "C:/Windows/Fonts/arial.ttf",

        "C:/Windows/Fonts/calibrib.ttf" if bold
        else "C:/Windows/Fonts/calibri.ttf"
    ]

    for path in paths:

        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def draw_wrapped_text(
    draw,
    text,
    position,
    font,
    max_width,
    fill="white",
    line_spacing=10
):

    words = text.split()

    lines = []
    current = ""

    for word in words:

        test = current + " " + word if current else word

        if draw.textbbox(
            (0, 0),
            test,
            font=font
        )[2] <= max_width:

            current = test

        else:

            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    x, y = position

    for line in lines:

        draw.text(
            (x, y),
            line,
            font=font,
            fill=fill
        )

        bbox = draw.textbbox(
            (x, y),
            line,
            font=font
        )

        y = bbox[3] + line_spacing

    return y


# ---------------------------------------------------------
# VISUAL 1 — INDIA / RANSOMWARE
# ---------------------------------------------------------

def draw_india_visual(draw):

    # India-style map silhouette
    points = [
        (500, 275),
        (555, 250),
        (610, 265),
        (650, 300),
        (690, 325),
        (675, 365),
        (650, 400),
        (625, 440),
        (610, 490),
        (585, 535),
        (565, 500),
        (550, 455),
        (525, 420),
        (500, 380),
        (475, 345),
        (460, 310)
    ]

    draw.polygon(
        points,
        fill=(35, 75, 120),
        outline=(80, 170, 255)
    )

    # Attack indicators
    locations = [
        (540, 315),
        (590, 350),
        (620, 390),
        (575, 430),
        (600, 470)
    ]

    for x, y in locations:

        draw.ellipse(
            (x - 9, y - 9, x + 9, y + 9),
            fill=(255, 70, 70)
        )

        draw.ellipse(
            (x - 17, y - 17, x + 17, y + 17),
            outline=(255, 100, 100),
            width=2
        )

    draw.text(
        (455, 550),
        "RANSOMWARE ACTIVITY",
        font=get_font(24, bold=True),
        fill=(255, 100, 100)
    )


# ---------------------------------------------------------
# VISUAL 2 — VIRTUAL MACHINE
# ---------------------------------------------------------

def draw_vm_visual(draw):

    # Server / VM container
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

    # Server layers
    for y in [355, 405]:

        draw.rounded_rectangle(
            (450, y, 800, y + 30),
            radius=8,
            fill=(40, 60, 85)
        )

        draw.ellipse(
            (470, y + 8, 482, y + 20),
            fill=(80, 220, 130)
        )

    # Warning symbol
    draw.polygon(
        [(900, 300), (965, 420), (835, 420)],
        fill=(210, 55, 55)
    )

    draw.text(
        (890, 340),
        "!",
        font=get_font(60, bold=True),
        fill="white"
    )


# ---------------------------------------------------------
# VISUAL 3 — POWERSHELL
# ---------------------------------------------------------

def draw_terminal_visual(draw):

    # Terminal window
    draw.rounded_rectangle(
        (350, 245, 930, 475),
        radius=12,
        fill=(8, 12, 18),
        outline=(70, 150, 230),
        width=3
    )

    # Terminal header
    draw.rectangle(
        (350, 245, 930, 285),
        fill=(30, 45, 65)
    )

    draw.ellipse(
        (370, 258, 382, 270),
        fill=(220, 80, 80)
    )

    draw.ellipse(
        (390, 258, 402, 270),
        fill=(230, 180, 60)
    )

    draw.ellipse(
        (410, 258, 422, 270),
        fill=(70, 190, 100)
    )

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

        draw.text(
            (390, y),
            command,
            font=terminal_font,
            fill=(100, 220, 150)
        )

        y += 32


# ---------------------------------------------------------
# VISUAL 4 — DATABASE / ESXi / NAS
# ---------------------------------------------------------

def draw_server_visual(draw):

    # Three servers
    server_positions = [
        (300, 275),
        (520, 275),
        (740, 275)
    ]

    labels = [
        "DATABASE",
        "ESXi",
        "NAS"
    ]

    for (x, y), label in zip(
        server_positions,
        labels
    ):

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
                (
                    x + 30,
                    y + 75 + row * 38,
                    x + 140,
                    y + 100 + row * 38
                ),
                fill=(45, 65, 90)
            )

            draw.ellipse(
                (
                    x + 40,
                    y + 82 + row * 38,
                    x + 52,
                    y + 94 + row * 38
                ),
                fill=(80, 220, 130)
            )

    # Attack warning
    draw.polygon(
        [(570, 500), (630, 590), (510, 590)],
        fill=(220, 60, 60)
    )

    draw.text(
        (555, 515),
        "!",
        font=get_font(45, bold=True),
        fill="white"
    )


# ---------------------------------------------------------
# VISUAL 5 — SECURITY TEAM / PROTECTION
# ---------------------------------------------------------

def draw_security_visual(draw):

    # Monitor
    draw.rounded_rectangle(
        (350, 240, 930, 470),
        radius=15,
        fill=(18, 32, 50),
        outline=(70, 150, 230),
        width=3
    )

    # Dashboard lines
    for i in range(4):

        y = 290 + i * 38

        draw.rectangle(
            (400, y, 850, y + 15),
            fill=(40, 65, 90)
        )

        draw.rectangle(
            (400, y, 620 + i * 40, y + 15),
            fill=(70, 180, 130)
        )

    draw.text(
        (400, 425),
        "THREAT INTELLIGENCE",
        font=get_font(25, bold=True),
        fill=(110, 190, 255)
    )

    # Shield
    shield = [
        (1000, 260),
        (1080, 290),
        (1060, 430),
        (1000, 490),
        (940, 430),
        (920, 290)
    ]

    draw.polygon(
        shield,
        fill=(35, 130, 90),
        outline=(100, 230, 170)
    )

    # Check mark
    draw.line(
        [(955, 370), (985, 405), (1050, 335)],
        fill="white",
        width=12
    )


# ---------------------------------------------------------
# SELECT VISUAL
# ---------------------------------------------------------

def draw_scene_visual(draw, scene):

    scene_number = scene.get("scene_number", 1)

    visual_text = (
        str(scene.get("visual_description", "")) + " " +
        str(scene.get("visual_recommendation", "")) + " " +
        str(scene.get("on_screen_text", ""))
    ).lower()

    # India / geographical content
    if any(word in visual_text for word in [
        "india",
        "country",
        "region",
        "map",
        "geographical",
        "location"
    ]):

        draw_india_visual(draw)
        return

    # Virtual machines / virtualization
    if any(word in visual_text for word in [
        "virtual machine",
        "virtualized",
        "vmware",
        "esxi",
        "hypervisor",
        "virtual environment"
    ]):

        draw_vm_visual(draw)
        return

    # PowerShell / terminal / command line
    if any(word in visual_text for word in [
        "powershell",
        "command prompt",
        "terminal",
        "command line",
        "shell",
        "malicious code"
    ]):

        draw_terminal_visual(draw)
        return

    # Servers / databases / NAS / network infrastructure
    if any(word in visual_text for word in [
        "database",
        "server",
        "nas",
        "network",
        "storage",
        "backup",
        "ransomware attack"
    ]):

        draw_server_visual(draw)
        return

    # Security / protection / monitoring
    if any(word in visual_text for word in [
        "security",
        "security team",
        "threat intelligence",
        "monitoring",
        "protection",
        "restore",
        "recovery",
        "mitigation",
        "cybersecurity"
    ]):

        draw_security_visual(draw)
        return

    # Fallback
    # If no keyword matches, use the scene number
    # only as a fallback.
    fallback_visuals = {
        1: draw_india_visual,
        2: draw_vm_visual,
        3: draw_terminal_visual,
        4: draw_server_visual,
        5: draw_security_visual
    }

    visual_function = fallback_visuals.get(
        scene_number,
        draw_security_visual
    )

    visual_function(draw)

# ---------------------------------------------------------
# CREATE SCENE IMAGE
# ---------------------------------------------------------

def create_scene_image(
    scene,
    output_path,
    total_scenes
):

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        (8, 15, 27)
    )

    draw = ImageDraw.Draw(image)

    # Top blue line
    draw.rectangle(
        (0, 0, WIDTH, 8),
        fill=(40, 150, 255)
    )

    small_font = get_font(26)
    title_font = get_font(44, bold=True)
    subtitle_font = get_font(27)

    scene_number = scene["scene_number"]

    # Scene number
    draw.text(
        (60, 35),
        f"SCENE {scene_number} / {total_scenes}",
        font=small_font,
        fill=(120, 190, 255)
    )

    # Title
    title = scene.get(
        "on_screen_text",
        f"Scene {scene_number}"
    )

    draw_wrapped_text(
        draw,
        title,
        (60, 90),
        title_font,
        1160,
        fill="white",
        line_spacing=10
    )

    # Visual panel
    draw.rounded_rectangle(
        (45, 175, 1235, 505),
        radius=20,
        fill=(18, 31, 49),
        outline=(45, 90, 135),
        width=2
    )

    draw.text(
        (75, 195),
        "VISUAL",
        font=small_font,
        fill=(100, 190, 255)
    )

    # Actual visual graphic
    draw_scene_visual(
        draw,
        scene
        )

    # Bottom narration/subtitle area
    draw.rectangle(
        (0, 555, WIDTH, HEIGHT),
        fill=(4, 8, 15)
    )

    narration = scene.get(
        "narration",
        ""
    )

    draw_wrapped_text(
        draw,
        narration,
        (60, 585),
        subtitle_font,
        1160,
        fill="white",
        line_spacing=7
    )

    image.save(output_path)


# ---------------------------------------------------------
# CREATE VIDEO
# ---------------------------------------------------------

def create_video(
    blueprint,
    output_path="sample_video.mp4"
):

    os.makedirs(
        "video_scenes",
        exist_ok=True
    )

    scenes = blueprint["scenes"]

    clips = []

    for scene in scenes:

        scene_number = scene["scene_number"]

        image_path = (
            f"video_scenes/"
            f"scene_{scene_number}.png"
        )

        create_scene_image(
            scene,
            image_path,
            len(scenes)
        )

        video_clip = ImageClip(
            image_path
        ).with_duration(
            scene["duration_seconds"]
        )

        audio_path = (
            f"audio/"
            f"scene_{scene_number}.mp3"
        )

        if os.path.exists(audio_path):

            audio_clip = AudioFileClip(
                audio_path
            )

            video_clip = video_clip.with_duration(
                audio_clip.duration
            )

            video_clip = video_clip.with_audio(
                audio_clip
            )

        clips.append(video_clip)

    final_video = concatenate_videoclips(
        clips,
        method="compose"
    )

    final_video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac"
    )

    return output_path
