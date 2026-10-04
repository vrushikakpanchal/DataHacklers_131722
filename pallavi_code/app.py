"""Flask UI for the local Social Media Content Engine."""

from __future__ import annotations

import io
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from flask import Flask, render_template_string, request, send_file
from werkzeug.utils import secure_filename

try:
    from .generator import (
        MODEL_NAME,
        OLLAMA_HOST,
        generate_content,
        validate_grounding,
    )
    from .parser import parse_document
    from .validator import validate_content
except ImportError:
    from generator import MODEL_NAME, OLLAMA_HOST, generate_content, validate_grounding
    from parser import parse_document
    from validator import validate_content


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

DEFAULT_SETTINGS = {
    "audience": "General public",
    "tone": "Professional",
    "objective": "Inform",
    "language": "English",
    "detail": "Medium",
}

ALLOWED_PLATFORMS = {"linkedin", "x", "both"}


HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Social Media Content Engine</title>

    <style>
        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            background: #10151b;
            color: #edf4f7;
            font-family: Arial, sans-serif;
            line-height: 1.5;
        }

        main {
            max-width: 1100px;
            margin: auto;
            padding: 30px 20px 60px;
        }

        h1 {
            margin-bottom: 5px;
        }

        h2 {
            margin-top: 0;
        }

        .muted {
            color: #9aabb5;
        }

        .card {
            background: #172029;
            border: 1px solid #30404c;
            border-radius: 12px;
            padding: 22px;
            margin: 18px 0;
        }

        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 18px;
        }

        .settings {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 12px;
            margin-top: 18px;
        }

        label {
            display: block;
            color: #b7c5cc;
            font-size: 13px;
            font-weight: bold;
            margin-bottom: 7px;
        }

        input[type="file"],
        textarea,
        select {
            width: 100%;
            border: 1px solid #30404c;
            border-radius: 8px;
            background: #10181f;
            color: #edf4f7;
            padding: 10px;
            font: inherit;
        }

        textarea {
            min-height: 150px;
            resize: vertical;
        }

        .source-text {
            min-height: 220px;
        }

        select {
            height: 42px;
        }

        .choice-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }

        .choice {
            display: inline-block;
            border: 1px solid #30404c;
            border-radius: 20px;
            padding: 8px 12px;
        }

        button {
            border: 0;
            border-radius: 8px;
            padding: 11px 15px;
            font-weight: bold;
            cursor: pointer;
        }

        button:hover {
            opacity: 0.9;
        }

        .primary {
            background: #68d5c1;
            color: #09201f;
        }

        .secondary {
            background: #263641;
            color: #ffffff;
        }

        .actions {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 16px;
        }

        .notice {
            border-radius: 8px;
            padding: 13px;
            margin: 15px 0;
        }

        .error {
            background: #351f25;
            border: 1px solid #763f43;
            color: #ffd6d1;
        }

        .pass {
            background: #153b38;
            border: 1px solid #28665c;
            color: #c9fff2;
        }

        .flag {
            background: #392e1a;
            border: 1px solid #70572d;
            color: #ffe0a5;
        }

        .facts {
            background: #10181f;
            border: 1px solid #30404c;
            border-radius: 8px;
            padding: 15px;
            white-space: pre-wrap;
            overflow: auto;
        }

        .thread-post {
            margin: 14px 0;
        }

        .thread-head {
            display: flex;
            justify-content: space-between;
            color: #9aabb5;
            font-size: 13px;
            margin-bottom: 5px;
        }

        .checks {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }

        .check {
            border: 1px solid #30404c;
            border-radius: 8px;
            padding: 12px;
        }

        .small {
            color: #9aabb5;
            font-size: 12px;
        }

        @media (max-width: 800px) {
            .grid,
            .settings,
            .checks {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>

<body>
<main>
    <h1>Social Media Content Engine</h1>
    <p class="muted">
        Source → facts → platform content → validation → human review
    </p>

    <section class="card">
        <h2>1. Source and settings</h2>

        <form method="post" enctype="multipart/form-data">
            <div class="grid">
                <div>
                    <label for="source_file">
                        Upload PDF, DOCX, TXT, or JSON
                    </label>

                    <input
                        id="source_file"
                        type="file"
                        name="source_file"
                        accept=".pdf,.docx,.txt,.json"
                    >

                    <p class="small">Text PDFs are read directly. Image-only PDFs use local Tesseract OCR.</p>
                    
                </div>

                <div>
                    <label for="pasted_text">
                        Or paste source text
                    </label>

                    <textarea
                        id="pasted_text"
                        name="pasted_text"
                        class="source-text"
                        placeholder="Paste a report or advisory here..."
                    >{{ pasted_text }}</textarea>
                </div>
            </div>

            <div style="margin-top: 18px;">
                <label>Platform</label>

                <div class="choice-row">
                    {% for value, label in platform_options %}
                    <label class="choice">
                        <input
                            type="radio"
                            name="platform"
                            value="{{ value }}"
                            {% if platform == value %}checked{% endif %}
                        >
                        {{ label }}
                    </label>
                    {% endfor %}
                </div>
            </div>

            <div class="settings">
                {% for key, label, options in setting_options %}
                <div>
                    <label for="{{ key }}">{{ label }}</label>

                    <select id="{{ key }}" name="{{ key }}">
                        {% for option in options %}
                        <option
                            value="{{ option }}"
                            {% if settings.get(key) == option %}selected{% endif %}
                        >
                            {{ option }}
                        </option>
                        {% endfor %}
                    </select>
                </div>
                {% endfor %}
            </div>

            <label class="choice" style="margin-top: 18px;">
                <input
                    type="checkbox"
                    name="run_grounding"
                    value="1"
                    {% if run_grounding %}checked{% endif %}
                >
                Run optional grounding review
            </label>

            <div class="actions">
                <button class="primary" type="submit">
                    {% if result %}Regenerate content{% else %}Generate content{% endif %}
                </button>
            </div>
        </form>
    </section>

    {% if error %}
    <div class="notice error">
        <strong>Could not generate content</strong>
        <br>
        {{ error }}
    </div>
    {% endif %}

    {% if elapsed %}
    <div class="notice pass">
        Generated in {{ elapsed }} seconds using {{ call_count }} Ollama calls.
    </div>
    {% endif %}

    {% if result %}
    <section class="card">
        <h2>2. Structured source facts</h2>

        <p class="small">
            These facts are the single source of truth for the generated content.
        </p>

        <pre class="facts">{{ facts_json }}</pre>
    </section>

    <form method="post" action="/download">
        <input type="hidden" name="facts_json" value="{{ facts_json|e }}">
        <input type="hidden" name="validation_json" value="{{ validation_json|e }}">

        {% if platform in ["linkedin", "both"] %}
        <section class="card">
            <h2>3. LinkedIn post</h2>

            <textarea id="linkedin" name="linkedin">{{ linkedin }}</textarea>

            <div class="actions">
                <button
                    type="button"
                    class="secondary"
                    onclick="copyValue('linkedin')"
                >
                    Copy LinkedIn
                </button>

                <button
                    type="submit"
                    class="secondary"
                    name="download"
                    value="linkedin"
                >
                    Download LinkedIn
                </button>
            </div>
        </section>
        {% endif %}

        {% if platform in ["x", "both"] %}
        <section class="card">
            <h2>4. X / Twitter thread</h2>

            {% for post in x_thread %}
            <div class="thread-post">
                <div class="thread-head">
                    <span>
                        Post {{ loop.index }} / {{ x_thread|length }}
                    </span>

                    <span>
                        {{ post|length }} / 280 characters
                    </span>
                </div>

                <textarea name="x_post">{{ post }}</textarea>
            </div>
            {% endfor %}

            <div class="actions">
                <button
                    type="button"
                    class="secondary"
                    onclick="copyThread()"
                >
                    Copy X thread
                </button>

                <button
                    type="submit"
                    class="secondary"
                    name="download"
                    value="x"
                >
                    Download X thread
                </button>
            </div>
        </section>
        {% endif %}

        <section class="card">
            <h2>5. Validation and export</h2>

            {% if validation.valid %}
            <div class="notice pass">
                <strong>PASS</strong>
                No basic validation problems were found.
            </div>
            {% else %}
            <div class="notice flag">
                <strong>FLAG</strong>
                Review the findings before using the content.
            </div>
            {% endif %}

            <div class="checks">
                {% for key, title in validation_labels %}
                {% set check = validation.get(key) %}

                <div class="check">
                    <strong>
                        {{ title }} · {{ check.status }}
                    </strong>

                    {% if check.issues %}
                    <ul>
                        {% for issue in check.issues %}
                        <li>{{ issue }}</li>
                        {% endfor %}
                    </ul>
                    {% elif check.status == "SKIP" %}
                    <span class="small">Not requested.</span>
                    {% else %}
                    <span class="small">No issues found.</span>
                    {% endif %}
                </div>
                {% endfor %}
            </div>

            {% if validation.grounding %}
            <div class="check" style="margin-top: 10px;">
                <strong>
                    Grounding review · {{ validation.grounding.status }}
                </strong>

                {% if validation.grounding.unsupported_claims %}
                <ul>
                    {% for claim in validation.grounding.unsupported_claims %}
                    <li>{{ claim }}</li>
                    {% endfor %}
                </ul>
                {% else %}
                <span class="small">
                    No unsupported claims found.
                </span>
                {% endif %}
            </div>
            {% endif %}

            <div class="actions">
                <button
                    type="button"
                    class="secondary"
                    onclick="approveContent()"
                >
                    Approve for export
                </button>

                <span id="approvalStatus" class="small"></span>

                <button
                    type="submit"
                    class="primary"
                    name="download"
                    value="json"
                >
                    Download JSON
                </button>

                <button
                    type="submit"
                    class="secondary"
                    name="download"
                    value="all"
                >
                    Download all as text
                </button>
            </div>

            <p class="small">
                Nothing is automatically published.
            </p>
        </section>
    </form>
    {% endif %}
</main>

<script>
function copyValue(id) {
    navigator.clipboard
        .writeText(document.getElementById(id).value)
        .then(() => alert("Copied."));
}

function copyThread() {
    const nodes = [
        ...document.querySelectorAll('textarea[name="x_post"]')
    ];

    const posts = nodes.map((node, index) => {
        return `${index + 1}/${nodes.length} ${node.value}`;
    });

    navigator.clipboard
        .writeText(posts.join("\\n\\n"))
        .then(() => alert("Copied."));
}

function approveContent() {
    const status = document.getElementById("approvalStatus");
    status.textContent = "Marked approved for export.";
    status.style.color = "#68d5c1";
}
</script>
</body>
</html>
"""


def _form_settings() -> dict[str, str]:
    settings = {}

    for key, default in DEFAULT_SETTINGS.items():
        value = request.form.get(key, default).strip()
        settings[key] = value or default

    return settings


def _render(**values: Any) -> str:
    settings = values.pop("settings", DEFAULT_SETTINGS.copy())

    return render_template_string(
        HTML_TEMPLATE,
        model_name=MODEL_NAME,
        ollama_host=OLLAMA_HOST,
        settings=settings,
        platform=values.pop("platform", "both"),
        platform_options=[
            ("both", "LinkedIn + X"),
            ("linkedin", "LinkedIn only"),
            ("x", "X thread only"),
        ],
        setting_options=[
            (
                "audience",
                "Audience",
                [
                    "General public",
                    "Technical audience",
                    "Government / officials",
                    "Cybersecurity professionals",
                ],
            ),
            (
                "tone",
                "Tone",
                [
                    "Professional",
                    "Informative",
                    "Simple",
                    "Technical",
                ],
            ),
            (
                "objective",
                "Objective",
                [
                    "Inform",
                    "Educate",
                    "Awareness",
                    "Action / recommendation",
                ],
            ),
            ("language", "Language", ["English"]),
            ("detail", "Detail", ["Short", "Medium", "Detailed"]),
        ],
        validation_labels=[
            ("facts", "Source facts"),
            ("linkedin", "LinkedIn"),
            ("x_thread", "X character and sensitive-data checks"),
        ],
        run_grounding=values.pop("run_grounding", False),
        **values,
    )


@app.route("/", methods=["GET", "POST"])
def index() -> str:
    values: dict[str, Any] = {
        "error": None,
        "result": None,
        "pasted_text": "",
        "platform": "both",
        "settings": DEFAULT_SETTINGS.copy(),
        "run_grounding": False,
    }

    if request.method == "GET":
        return _render(**values)

    values["platform"] = request.form.get("platform", "both").lower()
    values["settings"] = _form_settings()
    values["settings"]["platform"] = values["platform"]
    values["pasted_text"] = request.form.get("pasted_text", "")
    values["run_grounding"] = request.form.get("run_grounding") == "1"

    if values["platform"] not in ALLOWED_PLATFORMS:
        values["error"] = "Please choose a supported platform."
        return _render(**values)

    uploaded_file = request.files.get("source_file")
    temporary_path: Path | None = None
    started = time.perf_counter()

    try:
        if uploaded_file and uploaded_file.filename:
            safe_name = secure_filename(uploaded_file.filename)

            if not safe_name:
                raise ValueError("The uploaded filename is invalid.")

            suffix = Path(safe_name).suffix.lower()

            temporary_file = tempfile.NamedTemporaryFile(
                prefix="smc-",
                suffix=suffix,
                dir=UPLOAD_FOLDER,
                delete=False,
            )

            temporary_path = Path(temporary_file.name)
            temporary_file.close()

            uploaded_file.save(temporary_path)

        source_text = parse_document(
            file_path=temporary_path,
            pasted_text=values["pasted_text"],
        )

        result = generate_content(
            source_text,
            values["settings"],
            values["platform"],
        )

        grounding = None

        if values["run_grounding"]:
            grounding = validate_grounding(
                result["facts"],
                result.get("linkedin", ""),
                result.get("x_thread", []),
            )

        validation = validate_content(
            result,
            values["platform"],
            grounding,
        )

        values.update(
            {
                "result": result,
                "facts_json": json.dumps(
                    result["facts"],
                    indent=2,
                    ensure_ascii=False,
                ),
                "validation_json": json.dumps(
                    validation,
                    ensure_ascii=False,
                ),
                "validation": validation,
                "linkedin": result.get("linkedin", ""),
                "x_thread": result.get("x_thread", []),
                "elapsed": round(time.perf_counter() - started, 2),
                "call_count": 3 if values["run_grounding"] else 2,
            }
        )

    except Exception as exc:
        values["error"] = str(exc)

    finally:
        if temporary_path:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    return _render(**values)


@app.post("/download")
def download() -> Any:
    kind = request.form.get("download", "all")

    linkedin = request.form.get("linkedin", "").strip()

    x_thread = [
        post.strip()
        for post in request.form.getlist("x_post")
        if post.strip()
    ]

    facts_raw = request.form.get("facts_json", "{}")
    validation_raw = request.form.get("validation_json", "{}")

    try:
        facts = json.loads(facts_raw)
    except json.JSONDecodeError:
        facts = {}

    try:
        validation = json.loads(validation_raw)
    except json.JSONDecodeError:
        validation = {}

    if kind == "linkedin":
        content = linkedin
        filename = "linkedin_post.txt"
        mimetype = "text/plain"

    elif kind == "x":
        content = "\n\n".join(
            f"{index}/{len(x_thread)} {post}"
            for index, post in enumerate(x_thread, 1)
        )
        filename = "x_thread.txt"
        mimetype = "text/plain"

    elif kind == "json":
        content = json.dumps(
            {
                "facts": facts,
                "linkedin": linkedin,
                "x_thread": x_thread,
                "validation": validation,
            },
            indent=2,
            ensure_ascii=False,
        )
        filename = "social_media_content.json"
        mimetype = "application/json"

    else:
        content = "LINKEDIN POST\n\n"
        content += linkedin
        content += "\n\nX / TWITTER THREAD\n\n"
        content += "\n\n".join(
            f"{index}/{len(x_thread)} {post}"
            for index, post in enumerate(x_thread, 1)
        )
        filename = "social_media_content.txt"
        mimetype = "text/plain"

    return send_file(
        io.BytesIO(content.encode("utf-8")),
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype,
    )


if __name__ == "__main__":
    print(f"SMC Engine using {MODEL_NAME} at {OLLAMA_HOST}")
    print("Open http://127.0.0.1:5000")

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
        use_reloader=False,
    )