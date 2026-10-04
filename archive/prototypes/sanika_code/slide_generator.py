import ollama
import json
from extractor import extract_pdf_text


# ============================================
# STEP 1: PDF FILE
# ============================================

pdf_path = "input/DataRoles.pdf"


# ============================================
# STEP 2: EXTRACT TEXT FROM PDF
# ============================================

print("Reading PDF...")

source_text = extract_pdf_text(pdf_path)

print("PDF text extracted successfully!")
print("--------------------------------------------")
print(source_text[:1000])
print("--------------------------------------------")


# ============================================
# STEP 3: CREATE AI PROMPT
# ============================================

prompt = f"""
You are a professional presentation generator.

Create a presentation from the source content provided below.

Requirements:

1. Create 4 slides.
2. Each slide must have a title.
3. Each slide must have 3 to 4 key points.
4. Each slide must have speaker notes.
5. Use ONLY information from the source content.
6. Do not invent facts or information.
7. Keep the important information from the source.
8. Return ONLY valid JSON.
9. Do not add explanations before or after the JSON.
10. Do not use Markdown code fences.

Use exactly this JSON structure:

{{
    "presentation_title": "string",
    "slides": [
        {{
            "slide_number": 1,
            "title": "string",
            "key_points": [
                "point 1",
                "point 2",
                "point 3"
            ],
            "speaker_notes": "string"
        }}
    ]
}}

SOURCE CONTENT:

{source_text}
"""


# ============================================
# STEP 4: SEND PROMPT TO OLLAMA
# ============================================

print("\nGenerating presentation using AI...")

response = ollama.chat(
    model="qwen2.5:0.5b",
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ]
)


# ============================================
# STEP 5: GET AI RESPONSE
# ============================================

result = response["message"]["content"]

print("\nAI Generated Presentation:")
print("--------------------------------------------")
print(result)
print("--------------------------------------------")


# ============================================
# STEP 6: CLEAN AI RESPONSE
# ============================================

result = result.strip()

# Remove Markdown JSON code fence if AI adds it
if result.startswith("```json"):
    result = result[7:]

elif result.startswith("```"):
    result = result[3:]

if result.endswith("```"):
    result = result[:-3]

result = result.strip()


# ============================================
# STEP 7: CONVERT AI RESPONSE TO JSON
# ============================================

try:

    presentation = json.loads(result)

    print("\nJSON generated successfully!")


except json.JSONDecodeError as e:

    print("\nERROR: AI response is not valid JSON.")
    print("JSON Error:", e)

    print("\nRaw AI response:")
    print(result)

    exit()


# ============================================
# STEP 8: BASIC VALIDATION
# ============================================

if "presentation_title" not in presentation:

    print("ERROR: presentation_title is missing.")
    exit()


if "slides" not in presentation:

    print("ERROR: slides are missing.")
    exit()


if not isinstance(presentation["slides"], list):

    print("ERROR: slides must be a list.")
    exit()


print("Presentation structure is valid.")

print("\nPresentation Title:")
print(presentation["presentation_title"])

print("\nNumber of Slides:")
print(len(presentation["slides"]))


# ============================================
# STEP 9: CHECK EACH SLIDE
# ============================================

for slide in presentation["slides"]:

    required_fields = [
        "slide_number",
        "title",
        "key_points",
        "speaker_notes"
    ]

    for field in required_fields:

        if field not in slide:

            print(
                f"ERROR: '{field}' is missing "
                f"from slide {slide.get('slide_number', '?')}"
            )

            exit()


print("\nAll slides passed validation.")


# ============================================
# STEP 10: SAVE JSON FILE
# ============================================

output_path = "output/presentation.json"

with open(
    output_path,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        presentation,
        file,
        indent=4,
        ensure_ascii=False
    )


print("\n============================================")
print("SUCCESS!")
print("============================================")

print(f"\nPresentation JSON saved to:")
print(output_path)