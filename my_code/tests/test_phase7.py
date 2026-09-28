import sys
import os
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from apps.api import app

client = TestClient(app)

def verify_phase7():
    print("==================================================")
    print("   SIH PS ID: 26154 - PHASE 7 FASTAPI BACKEND     ")
    print("==================================================")

    # 1. Test Health Endpoint
    health_resp = client.get("/health")
    print(f"[✓] Health Check Status Code: {health_resp.status_code}")
    print(f"[✓] Health Check Response: {health_resp.json()}")
    assert health_resp.status_code == 200

    # 2. Test Full Transformation Endpoint
    sample_path = os.path.join("data", "sample_inputs", "sample_advisory.txt")
    if not os.path.exists(sample_path):
        print(f"[X] Sample input missing at: {sample_path}")
        return

    print("\n[...] Sending file upload request to /api/v1/transform...")
    with open(sample_path, "rb") as f:
        response = client.post(
            "/api/v1/transform",
            files={"file": ("sample_advisory.txt", f, "text/plain")},
            data={
                "tone": "Executive / Board-Level",
                "target_audience": "Leadership",
                "detail_level": "High"
            }
        )

    print(f"[✓] Transformation Status Code: {response.status_code}")
    assert response.status_code == 200

    data = response.json()
    print(f"[✓] Processed File SHA-256: {data['sha256_hash'][:16]}...")
    print(f"[✓] Fact Preservation Rate: {data['verification_audit']['average_fact_preservation_rate']}%")
    print(f"[✓] Download URLs Provided: {list(data['download_urls'].keys())}")

    # 3. Test File Download Endpoint
    pdf_url = data['download_urls']['advisory_pdf']
    file_resp = client.get(pdf_url)
    print(f"[✓] Artifact Download Test ({pdf_url}): Status Code {file_resp.status_code}")
    assert file_resp.status_code == 200

    print("\nSUCCESS: Phase 7 FastAPI Backend verified!")

if __name__ == "__main__":
    verify_phase7()