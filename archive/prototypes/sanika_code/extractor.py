import pymupdf

def extract_pdf_text(file_path):

    document = pymupdf.open(file_path)

    text = ""

    for page in document:
        text += page.get_text()
        text += "\n"

    document.close()

    return text
def clean_text(text):

    lines = text.splitlines()

    cleaned_lines = []

    for line in lines:
        line = line.strip()

        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)
text = extract_pdf_text("input/DataRoles.pdf")
text = clean_text(text)

print(text)