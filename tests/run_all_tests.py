"""Comprehensive test runner for SIH PS 26154 Content Transformation Platform."""

import os
import subprocess
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYTHON = sys.executable

TEST_SCRIPTS = [
    ("Environment Setup", os.path.join(PROJECT_ROOT, "my_code", "tests", "test_setup.py"), os.path.join(PROJECT_ROOT, "my_code")),
    ("Phase 2: Ingestion & Locking", os.path.join(PROJECT_ROOT, "my_code", "tests", "test_phase2.py"), os.path.join(PROJECT_ROOT, "my_code")),
    ("Phase 3: LLM Schema Extraction", os.path.join(PROJECT_ROOT, "my_code", "tests", "test_phase3.py"), os.path.join(PROJECT_ROOT, "my_code")),
    ("Phase 4: Multi-Format Generators", os.path.join(PROJECT_ROOT, "my_code", "tests", "test_phase4.py"), os.path.join(PROJECT_ROOT, "my_code")),
    ("Phase 5: Social Media Engine", os.path.join(PROJECT_ROOT, "my_code", "tests", "test_phase5.py"), os.path.join(PROJECT_ROOT, "my_code")),
    ("Phase 6: Dynamic Presentation Engine", os.path.join(PROJECT_ROOT, "my_code", "tests", "test_phase6.py"), os.path.join(PROJECT_ROOT, "my_code")),
    ("Phase 7: Security & Audit Logging", os.path.join(PROJECT_ROOT, "my_code", "tests", "test_phase7.py"), os.path.join(PROJECT_ROOT, "my_code")),
    ("Phase 8: Operator Dashboard Interface", os.path.join(PROJECT_ROOT, "my_code", "tests", "test_phase8.py"), os.path.join(PROJECT_ROOT, "my_code")),
    ("Video Engine Verification", os.path.join(PROJECT_ROOT, "tests", "verify_video_engine.py"), PROJECT_ROOT),
]


def main():
    print("=" * 60)
    print("   RUNNING ALL SIH PS 26154 VERIFICATION TESTS   ")
    print("=" * 60)
    passed = 0
    failed = 0

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"

    for name, script_path, cwd in TEST_SCRIPTS:
        if not os.path.exists(script_path):
            print(f"[-] SKIPPED: {name} (file not found: {script_path})")
            continue
        print(f"\n>> Running: {name} ...")
        res = subprocess.run([PYTHON, script_path], cwd=cwd, env=env)
        if res.returncode == 0:
            passed += 1
            print(f"[PASS] {name}")
        else:
            failed += 1
            print(f"[FAIL] {name} (exit code {res.returncode})")

    print("\n" + "=" * 60)
    print(f"   TEST SUMMARY: {passed} PASSED, {failed} FAILED   ")
    print("=" * 60)
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
