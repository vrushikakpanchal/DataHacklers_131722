import io
import re
import hashlib
from typing import Tuple, Optional
from pypdf import PdfReader
from docx import Document
from app.core.config import settings

def compute_sha256(content: bytes | str) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()

class SourceParser:
    @staticmethod
    def sanitize_text(text: str) -> str:
        """Remove null bytes and unprintable control characters except newline and tab."""
        text = text.replace("\x00", "")
        # Normalize newlines
        text = re.sub(r"\r\n|\r", "\n", text)
        return text.strip()

    @staticmethod
    def parse_txt(content_bytes: bytes) -> str:
        """Parse raw text with utf-8 fallback decoding."""
        try:
            return content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return content_bytes.decode("latin-1", errors="replace")

    @staticmethod
    def parse_pdf(content_bytes: bytes) -> str:
        """Extract text from PDF using pypdf."""
        stream = io.BytesIO(content_bytes)
        reader = PdfReader(stream)
        pages_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages_text.append(f"--- Page {i+1} ---\n{text}")
        if not pages_text:
            raise ValueError("The uploaded PDF document contains no readable text or is an image-only scan.")
        return "\n\n".join(pages_text)

    @staticmethod
    def parse_docx(content_bytes: bytes) -> str:
        """Extract text from DOCX using python-docx."""
        stream = io.BytesIO(content_bytes)
        doc = Document(stream)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)
        if not paragraphs:
            raise ValueError("The uploaded DOCX document contains no readable paragraphs.")
        return "\n\n".join(paragraphs)

    @classmethod
    def ingest_document(
        cls,
        filename: str,
        content_bytes: bytes,
        declared_type: Optional[str] = None
    ) -> Tuple[str, str, str]:
        """
        Validate, parse and encapsulate document text.
        Returns: (raw_text, sanitized_text, content_hash)
        """
        if len(content_bytes) > settings.MAX_UPLOAD_SIZE_BYTES:
            max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
            raise ValueError(f"File size exceeds maximum permitted limit of {max_mb} MB.")

        ext = filename.lower().split(".")[-1] if "." in filename else ""
        file_type = declared_type or ext.upper()

        if file_type == "PDF" or ext == "pdf":
            raw = cls.parse_pdf(content_bytes)
        elif file_type == "DOCX" or ext == "docx":
            raw = cls.parse_docx(content_bytes)
        elif file_type in ("TXT", "PASTED") or ext in ("txt", "log", "md"):
            raw = cls.parse_txt(content_bytes)
        else:
            raise ValueError(f"Unsupported file format: '.{ext}'. Supported: PDF, DOCX, TXT, Pasted text.")

        sanitized = cls.sanitize_text(raw)
        if not sanitized:
            raise ValueError("Document appears to be empty after extraction.")

        content_hash = compute_sha256(sanitized)
        return raw, sanitized, content_hash

    @staticmethod
    def wrap_untrusted_prompt(source_text: str) -> str:
        """
        Wrap source content in strict untrusted delimiters to defend against prompt injection.
        """
        return f"<UNTRUSTED_SOURCE>\n{source_text}\n</UNTRUSTED_SOURCE>"
