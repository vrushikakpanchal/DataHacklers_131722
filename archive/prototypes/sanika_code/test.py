from extractor import extract_pdf_text

text = extract_pdf_text("input/DataRoles.pdf")

print(text[:3000])
