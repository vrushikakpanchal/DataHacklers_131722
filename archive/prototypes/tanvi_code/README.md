\# Video Blueprint Generator



\## Overview



The Video Blueprint Generator is the video content transformation module of the SIH 2026 project. It converts source documents into a structured video blueprint using Qwen3-4B.



\## Features



\- Supports PDF, DOCX and TXT files

\- Extracts source text from uploaded documents

\- Uses Qwen3-4B for content generation

\- Generates a 5-scene video storyboard

\- Generates narration and subtitles

\- Provides visual descriptions and recommendations

\- Provides on-screen text and audio cues

\- Flask-based web interface

\- Qwen model runs through a remote Google Colab API



\## Workflow



Source Document

↓

PDF / DOCX / TXT Parser

↓

Extracted Text

↓

Flask Application

↓

Qwen3-4B API

↓

Structured Video Blueprint



\## Output



Each scene contains:



\- Duration

\- Visual Description

\- On-Screen Text

\- Narration

\- Audio Cue

\- Visual Recommendation



The system also generates the complete narration and subtitle structure.



\## Technologies



\- Python

\- Flask

\- Qwen3-4B

\- Hugging Face Transformers

\- PyPDF

\- python-docx

\- Requests

\- Google Colab

\- ngrok



\## Testing



The module was tested using the \*\*India Ransomware Report 2024\*\* as a sample source document. The system successfully generated a structured 60-second video blueprint containing five scenes, narration, visual descriptions, on-screen text, audio cues, visual recommendations, and subtitles.



\## Running the Project



1\. Install the required dependencies:



```bash

pip install -r requirements.txt

```



2\. Start the Flask application:



```bash

python app.py

```



3\. Open the local Flask URL in a browser.



4\. Upload a PDF, DOCX, or TXT document and generate the video blueprint.



\## SIH Module



This module focuses on transforming source documents into a structured Video Blueprint Package containing scene-wise narration, storyboard information, visual guidance, subtitles, and audio cues.



