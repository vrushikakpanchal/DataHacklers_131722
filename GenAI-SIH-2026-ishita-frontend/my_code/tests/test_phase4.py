import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from modules.generators import (
    generate_pdf_advisory,
    generate_social_content,
    generate_presentation,
    generate_video_package,
    generate_infographic_svg
)

def verify_phase4():
    print("==================================================")
    print("   SIH PS ID: 26154 - PHASE 4 MULTI-FORMAT ENGINE ")
    print("==================================================")
    
    mock_facts_path = os.path.join("data", "sample_inputs", "canonical_facts.json")
    if not os.path.exists(mock_facts_path):
        print(f"[X] Missing canonical facts file at: {mock_facts_path}")
        return

    with open(mock_facts_path, "r", encoding="utf-8") as f:
        canonical_facts = json.load(f)

    print(f"[✓] Loaded Canonical Facts: {canonical_facts['title']}")

    # 1. PDF / HTML Report
    pdf_res = generate_pdf_advisory(canonical_facts)
    print(f"[✓] 1. Executive Advisory Report Generated: {pdf_res}")

    # 2. Social Media Posts
    print("[...] 2. Requesting Social Media content from Ollama...")
    social_res = generate_social_content(canonical_facts, model_name="qwen2.5:3b")
    print(f"[✓] 2. Social Media Content Generated (LinkedIn + {len(social_res.get('twitter_thread', []))}-Tweet X Thread)")

    # 3. PowerPoint Deck
    pptx_res = generate_presentation(canonical_facts)
    print(f"[✓] 3. PowerPoint Deck (.pptx) Generated: {pptx_res}")

    # 4. Video Package
    print("[...] 4. Requesting Video Script & Storyboard from Ollama...")
    video_res = generate_video_package(canonical_facts, model_name="qwen2.5:3b")
    print(f"[✓] 4. Video Package Generated ({len(video_res.get('scenes', []))} Scenes)")

    # 5. Infographic SVG
    svg_res = generate_infographic_svg(canonical_facts)
    print(f"[✓] 5. Infographic Blueprint (.svg) Generated: {svg_res}")

    print("\nSUCCESS: All 5 Phase 4 Multi-Format Generators verified!")

if __name__ == "__main__":
    verify_phase4()