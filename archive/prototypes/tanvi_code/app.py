from flask import Flask, render_template, request, send_file
from parser import extract_text
from generator import generate_video_blueprint
from gtts import gTTS
from video_renderer import create_video

import os

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
AUDIO_FOLDER = "audio"
VIDEO_FOLDER = "outputs"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)


def generate_scene_audio(blueprint):
    """Generate narration audio for every scene."""

    for scene in blueprint["scenes"]:

        scene_number = scene["scene_number"]
        narration = scene.get("narration", "").strip()

        if not narration:
            continue

        audio_path = os.path.join(
            AUDIO_FOLDER,
            f"scene_{scene_number}.mp3"
        )

        tts = gTTS(
            text=narration,
            lang="en",
            slow=False
        )

        tts.save(audio_path)

        print(f"Created audio: {audio_path}")


@app.route("/", methods=["GET", "POST"])
def index():

    result = None
    error = None
    video_path = None

    if request.method == "POST":

        file = request.files.get("document")

        target_audience = request.form.get(
            "target_audience",
            "General Audience"
        )

        tone = request.form.get(
            "tone",
            "Professional"
        )

        language = request.form.get(
            "language",
            "English"
        )

        duration = request.form.get(
            "duration",
            "60"
        )

        objective = request.form.get(
            "objective",
            "Inform"
        )

        style = request.form.get(
            "style",
            "Educational"
        )

        if not file or file.filename == "":
            error = "Please upload a document."

            return render_template(
                "index.html",
                result=result,
                error=error,
                video_path=video_path
            )

        filepath = os.path.join(
            app.config["UPLOAD_FOLDER"],
            file.filename
        )

        file.save(filepath)

        try:

            # 1. Extract text from document
            text = extract_text(filepath)

            if not text.strip():
                raise ValueError(
                    "No readable text found in the document."
                )

            print("Source text extracted successfully.")

            # 2. Generate video blueprint using Qwen
            result = generate_video_blueprint(
                text=text,
                target_audience=target_audience,
                tone=tone,
                language=language,
                duration=int(duration),
                objective=objective,
                style=style
            )

            print("Video blueprint generated successfully.")

            # 3. Generate narration audio
            generate_scene_audio(result)

            print("All scene audio generated.")

            # 4. Create final MP4 video
            output_video = os.path.join(
                VIDEO_FOLDER,
                "generated_video.mp4"
            )

            create_video(
                result,
                output_path=output_video
            )

            print("Video generated successfully.")

            video_path = "generated_video.mp4"

        except Exception as e:

            error = str(e)
            print("ERROR:", error)

    return render_template(
        "index.html",
        result=result,
        error=error,
        video_path=video_path
    )


@app.route("/video/<filename>")
def video(filename):

    filepath = os.path.join(
        VIDEO_FOLDER,
        filename
    )

    if not os.path.exists(filepath):
        return "Video not found.", 404

    return send_file(filepath)


if __name__ == "__main__":
    app.run(debug=True)
    