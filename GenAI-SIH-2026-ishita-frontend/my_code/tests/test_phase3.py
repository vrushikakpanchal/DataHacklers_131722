import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from modules.extractor import process_and_lock_document
from modules.llm_engine import extract_canonical_facts

def verify_phase3():
    print("==================================================")
    print("   SIH PS ID: 26154 - PHASE 3 LLM SCHEMA ENGINE   ")
    print("==================================================")
    
    sample_file = os.path.join("data", "sample_inputs", "sample_advisory.txt")
    
    if not os.path.exists(sample_file):
        print(f"[X] Missing sample file at: {sample_file}")
        return

    # 1. Ingestion & Parameter Locking
    ingestion_result = process_and_lock_document(sample_file)
    raw_text = ingestion_result["raw_text"]
    locked_params = ingestion_result["locked_parameters"]

    print(f"[✓] Raw Text Loaded ({len(raw_text)} chars)")
    print(f"[✓] Locked Parameters: {locked_params}")
    print("[...] Requesting structured extraction from local Ollama (qwen2.5:3b)...")

    # 2. Local LLM Schema Extraction
    canonical_facts = extract_canonical_facts(raw_text, locked_params, model_name="qwen2.5:3b")

    print("\n[✓] Canonical Facts Extracted Successfully!")
    print(json.dumps(canonical_facts, indent=2))

    # Assertions
    assert "title" in canonical_facts and len(canonical_facts["title"]) > 0, "Title missing"
    assert "cve_ids" in canonical_facts, "CVE list missing"
    assert len(canonical_facts["recommended_actions"]) > 0, "Recommended actions missing"
    
    # Save canonical facts to mock JSON file for Phase 4 consumption
    mock_path = os.path.join("data", "sample_inputs", "canonical_facts.json")
    with open(mock_path, "w", encoding="utf-8") as f:
        json.dump(canonical_facts, f, indent=2)
    print(f"\n[✓] Saved structured output to: {mock_path}")

    print("\nSUCCESS: Phase 3 LLM Schema Engine verified!")

if __name__ == "__main__":
    verify_phase3()