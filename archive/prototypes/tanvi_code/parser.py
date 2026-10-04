import os
from pypdf import PdfReader
from docx import Document


def extract_text(filepath):

    extension = os.path.splitext(filepath)[1].lower()

    if extension == ".pdf":

        reader = PdfReader(filepath)

        text = ""

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

        return text

    elif extension == ".docx":

        document = Document(filepath)

        text = "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
        )

        return text

    elif extension == ".txt":

        with open(
            filepath,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read()

    else:

        raise ValueError(
            "Unsupported file type. Please upload PDF, DOCX or TXT."
        )