"""Live end-to-end check: real local Ollama -> generate_video_blueprint -> motion_script.

Writes the resulting blueprint to a scratch fixture so the browser test can fetch it
through the same download_urls.video_package_json path the app uses.
"""
import json
import os
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "my_code"))

from modules.video_engine import generate_video_blueprint  # noqa: E402

CANONICAL_FACTS = {
    "title": "Critical Ransomware Campaign Targeting Healthcare PACS Servers",
    "severity": "Critical",
    "summary": (
        "Exposed DICOM endpoints shipping default credentials (admin/admin) are being exploited to "
        "encrypt hospital imaging archives. Fourteen hospitals lost historical DICOM studies with an "
        "average recovery time of nine days."
    ),
    "cve_ids": ["CVE-2026-31142", "CVE-2026-31177"],
    "affected_systems": ["MedView PACS 4.2 through 4.7", "DICOMgate Connector 2.1"],
    "locked_ips": ["103.44.12.9", "45.77.201.14"],
    "recommended_actions": [
        "Rotate all DICOM service account credentials and remove default admin/admin pairs",
        "Disable anonymous DICOM association and segment PACS VLANs from the corporate network",
        "Restore affected imaging archives from offline backups",
        "Monitor SMB lateral movement on ports 445 and 3389",
    ],
}

FIXTURE = os.path.join(PROJECT_ROOT, "output", "_test_video_package.json")


def main() -> int:
    # Mirror my_code/apps/api.py fast_mode exactly: serialized facts JSON + a 60s target.
    source_text = json.dumps(CANONICAL_FACTS, ensure_ascii=False, indent=2)
    start = time.time()
    blueprint = generate_video_blueprint(
        text=source_text,
        target_audience="General Public",
        tone="Informative",
        duration="60s",
    )
    elapsed = time.time() - start

    script = blueprint.get("motion_script") or []
    print(f"generate_video_blueprint returned in {elapsed:.1f}s")
    print(f"generation_mode = {blueprint.get('generation_mode')}")
    print(f"scenes = {len(blueprint.get('scenes') or [])}, motion_script = {len(script)}")
    print(f"top-level keys = {sorted(blueprint.keys())}")
    print(f"blueprint title = {blueprint.get('title')!r}")
    print(f"blueprint severity = {blueprint.get('severity')!r}")

    problems = []
    allowed_sev = {"critical", "warning", "info"}
    allowed_icon = {"shield", "network", "lock", "user_analyst"}
    allowed_style = {"slide_in", "pulse_alert", "kinetic_zoom"}
    expected_keys = {"scene_id", "heading", "subtext", "theme_severity", "active_icon",
                     "animation_style", "duration_seconds"}
    for entry in script:
        if set(entry.keys()) != expected_keys:
            problems.append(f"scene {entry.get('scene_id')}: keys {sorted(entry.keys())}")
        if entry.get("theme_severity") not in allowed_sev:
            problems.append(f"scene {entry.get('scene_id')}: bad theme_severity {entry.get('theme_severity')!r}")
        if entry.get("active_icon") not in allowed_icon:
            problems.append(f"scene {entry.get('scene_id')}: bad active_icon {entry.get('active_icon')!r}")
        if entry.get("animation_style") not in allowed_style:
            problems.append(f"scene {entry.get('scene_id')}: bad animation_style {entry.get('animation_style')!r}")
        if not str(entry.get("heading") or "").strip():
            problems.append(f"scene {entry.get('scene_id')}: empty heading")

    print("\n--- motion_script ---")
    for entry in script:
        print(json.dumps(entry, ensure_ascii=False))

    os.makedirs(os.path.dirname(FIXTURE), exist_ok=True)
    with open(FIXTURE, "w", encoding="utf-8") as handle:
        json.dump(blueprint, handle, indent=2, ensure_ascii=False)
    print(f"\nfixture written -> {FIXTURE}")

    if problems:
        print("\nCONTRACT PROBLEMS:")
        for item in problems:
            print("  -", item)
        return 1
    print("\nCONTRACT OK: every motion_script entry matches the six-field schema and enum values.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
