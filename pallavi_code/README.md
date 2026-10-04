# Social Media Content Engine

This application converts a source document into source-grounded social-media
content using a local Ollama model.
Image-only PDFs are supported through local Tesseract OCR. Text-based PDFs
continue to use direct text extraction and do not need OCR.

It supports:

- PDF files
- DOCX files
- TXT files
- JSON files
- Pasted text
- LinkedIn posts
- X/Twitter threads
- Structured source facts
- Basic validation
- Downloadable output

## Folder structure

```text
smc/
├── app.py
├── parser.py
├── generator.py
├── validator.py
├── requirements.txt
├── README.md
└── sample_report.txt