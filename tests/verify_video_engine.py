"""Verification harness for the Code-as-Motion backend refactor (no network calls)."""

import importlib.util
import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MY_CODE = os.path.join(PROJECT_ROOT, "my_code")
sys.path.insert(0, MY_CODE)
os.chdir(MY_CODE)

from modules import video_engine as ve  # noqa: E402

failures = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    if not condition:
        failures.append(f"{label} :: {detail}")
    print(f"[{status}] {label}{(' -> ' + str(detail)) if detail and not condition else ''}")


print("=" * 72)
print("1. Module import + optional heavy stack")
print("=" * 72)
check("module imports", True)
check("HEAVY_RENDER_AVAILABLE is True with moviepy installed", ve.HEAVY_RENDER_AVAILABLE is True, ve.HEAVY_RENDER_AVAILABLE)
check("motion enums exposed", ve._MOTION_SEVERITIES == ("critical", "warning", "info")
      and ve._MOTION_ICONS == ("shield", "network", "lock", "user_analyst")
      and ve._MOTION_STYLES == ("slide_in", "pulse_alert", "kinetic_zoom"))

print()
print("=" * 72)
print("2. Import still succeeds with the heavy stack blocked")
print("=" * 72)

BLOCKED = {"moviepy", "pyttsx3", "numpy", "PIL"}


class _Blocker:
    def find_module(self, name, path=None):
        return self.find_spec(name, path)

    def find_spec(self, name, path=None, target=None):
        root = name.split(".")[0]
        if root in BLOCKED:
            raise ImportError(f"blocked {name} for test")
        return None


for mod in list(sys.modules):
    if mod.split(".")[0] in BLOCKED:
        del sys.modules[mod]
sys.meta_path.insert(0, _Blocker())
try:
    spec = importlib.util.spec_from_file_location(
        "video_engine_noheavy", os.path.join(MY_CODE, "modules", "video_engine.py")
    )
    light = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(light)
    check("module imports without moviepy/pyttsx3/numpy/PIL", True)
    check("HEAVY_RENDER_AVAILABLE False when blocked", light.HEAVY_RENDER_AVAILABLE is False)
    check("heavy names are None placeholders", light.ImageClip is None and light.pyttsx3 is None)
    try:
        light.create_video({"scenes": [{"scene_number": 1, "narration": "x"}]}, output_path="ignored.mp4")
        check("create_video raises without heavy deps", False, "no exception")
    except RuntimeError as exc:
        check("create_video raises RuntimeError without heavy deps", "not " in str(exc) or "installed" in str(exc), str(exc)[:80])
    check("blueprint helpers still usable when blocked",
          light._map_severity_to_motion("HIGH") == "critical"
          and light._infer_motion_style(1, "critical", []) == "slide_in")
finally:
    sys.meta_path.pop(0)
    import importlib
    importlib.invalidate_caches()
    for mod in list(sys.modules):
        if mod.split(".")[0] in BLOCKED and mod != "modules":
            del sys.modules[mod]
    importlib.reload(ve)

print()
print("=" * 72)
print("3. create_video guard honours the flag")
print("=" * 72)
original_flag = ve.HEAVY_RENDER_AVAILABLE
ve.HEAVY_RENDER_AVAILABLE = False
try:
    ve.create_video({"scenes": []}, output_path="ignored.mp4")
    check("guard raises before any rendering", False, "no exception")
except RuntimeError as exc:
    check("guard raises RuntimeError naming the missing deps", "moviepy" in str(exc), str(exc)[:90])
finally:
    ve.HEAVY_RENDER_AVAILABLE = original_flag

print()
print("=" * 72)
print("4. _normalize_scene: explicit motion fields are preserved")
print("=" * 72)
explicit = ve._normalize_scene({
    "title": "Perimeter Exposure",
    "narration": "Two gateway products are reachable from the indicator IP.",
    "visual_prompt": "Network topology highlight",
    "duration_seconds": 8,
    "scene_id": 2,
    "heading": "Exposed Perimeter",
    "subtext": "Two products, one indicator IP.",
    "theme_severity": "warning",
    "active_icon": "network",
    "animation_style": "kinetic_zoom",
}, 2)
check("heading preserved", explicit["heading"] == "Exposed Perimeter", explicit["heading"])
check("subtext preserved", explicit["subtext"] == "Two products, one indicator IP.", explicit["subtext"])
check("theme_severity preserved", explicit["theme_severity"] == "warning")
check("active_icon preserved", explicit["active_icon"] == "network")
check("animation_style preserved", explicit["animation_style"] == "kinetic_zoom")
check("scene_id mirrors position", explicit["scene_id"] == 2)
check("legacy keys intact", all(k in explicit for k in
      ("scene_number", "title", "description", "narration", "visual_prompt", "duration_seconds", "on_screen_text")))

print()
print("=" * 72)
print("5. _normalize_scene: legacy payload without motion fields")
print("=" * 72)
legacy = ve._normalize_scene({
    "title": "Containment Actions",
    "narration": "Patch immediately and rotate operator credentials.",
    "visual_prompt": "Checklist of mitigation steps",
    "duration_seconds": 7,
}, 3)
check("heading falls back to title", legacy["heading"] == "Containment Actions", legacy["heading"])
check("subtext falls back to narration", legacy["subtext"].startswith("Patch immediately"), legacy["subtext"])
check("theme left blank for blueprint fallback", legacy["theme_severity"] == "", repr(legacy["theme_severity"]))
check("icon inferred from scene wording (operator -> user_analyst)", legacy["active_icon"] == "user_analyst", legacy["active_icon"])
check("style left blank for blueprint fallback", legacy["animation_style"] == "")

net_scene = ve._normalize_scene({"title": "Lateral Traffic", "narration": "Lateral traffic from 185.220.101.44 to internal nodes.", "duration_seconds": 5}, 2)
lock_scene = ve._normalize_scene({"title": "Ransomware Encryption", "narration": "The payload encrypts local shares.", "duration_seconds": 5}, 2)
plain_scene = ve._normalize_scene({"title": "Advisory Summary", "narration": "Summary of the advisory.", "duration_seconds": 5}, 2)
check("network wording -> network icon", net_scene["active_icon"] == "network", net_scene["active_icon"])
check("encryption wording -> lock icon", lock_scene["active_icon"] == "lock", lock_scene["active_icon"])
check("neutral wording -> shield icon", plain_scene["active_icon"] == "shield", plain_scene["active_icon"])

print()
print("=" * 72)
print("6. _normalize_scene: invalid enum values are re-derived, not passed through")
print("=" * 72)
bad = ve._normalize_scene({
    "title": "Credential Theft Wave",
    "narration": "Operators report stolen passwords across accounts.",
    "theme_severity": "HIGH-RISK",
    "active_icon": "Shield Lock",
    "animation_style": "fade-in",
    "duration_seconds": 6,
}, 1)
check("non-enum severity mapped through the classifier", bad["theme_severity"] == "critical", bad["theme_severity"])
check("non-enum icon re-inferred from wording", bad["active_icon"] == "user_analyst", bad["active_icon"])
check("non-enum style cleared for deterministic fallback", bad["animation_style"] == "", repr(bad["animation_style"]))

print()
print("=" * 72)
print("7. _normalize_blueprint builds motion_script for a legacy payload")
print("=" * 72)
raw_legacy = {
    "title": "Critical VPN Appliance Exploitation",
    "summary": "Chained auth bypass and command injection.",
    "severity": "High",
    "scenes": [
        {"title": "Active Exploitation Alert", "narration": "Critical exploitation confirmed on the VPN appliances.",
         "visual_prompt": "Alert banner", "duration_seconds": 7},
        {"title": "Affected Network Surface", "narration": "Both gateways see lateral traffic from 185.220.101.44.",
         "visual_prompt": "Network topology", "duration_seconds": 8,
         "metrics": [{"label": "CVSS", "value": "9.8"}]},
        {"title": "Containment Actions", "narration": "Patch immediately and rotate operator credentials.",
         "visual_prompt": "Checklist", "duration_seconds": 8,
         "actions": ["Apply vendor patch", "Rotate credentials"]},
    ],
}
bp = ve._normalize_blueprint(raw_legacy, {"severity": "High", "title": "Critical VPN Appliance Exploitation"},
                             "General", "Informative", "English", "Summarize", "Cybersecurity Technical")
ms = bp["motion_script"]
check("motion_script present and one entry per scene", isinstance(ms, list) and len(ms) == 3, len(ms))
check("motion_script keys are the motion contract",
      all(set(entry) == {"scene_id", "heading", "subtext", "theme_severity", "active_icon", "animation_style", "duration_seconds"}
          for entry in ms), sorted(ms[0].keys()))
check("scene_id is 1-based and ordered", [e["scene_id"] for e in ms] == [1, 2, 3], [e["scene_id"] for e in ms])
check("headings derived from scene titles", [e["heading"] for e in ms] ==
      ["Active Exploitation Alert", "Affected Network Surface", "Containment Actions"], [e["heading"] for e in ms])
check("subtexts derived from narration", all(e["subtext"] for e in ms))
check("severity fallback maps High -> critical for every scene",
      all(e["theme_severity"] == "critical" for e in ms), [e["theme_severity"] for e in ms])
check("style varies deterministically (slide_in, pulse_alert x2)",
      [e["animation_style"] for e in ms] == ["slide_in", "pulse_alert", "pulse_alert"], [e["animation_style"] for e in ms])
check("icons inferred per scene", [e["active_icon"] for e in ms] == ["shield", "network", "user_analyst"],
      [e["active_icon"] for e in ms])
check("durations carried into motion_script", [e["duration_seconds"] for e in ms] == [7.0, 8.0, 8.0],
      [e["duration_seconds"] for e in ms])
check("scenes backfilled with motion fields",
      all(s["theme_severity"] == "critical" and s["animation_style"] and s["scene_id"] == i
          for i, s in enumerate(bp["scenes"], 1)))
check("existing blueprint contract preserved",
      all(k in bp for k in ("title", "summary", "severity", "scenes", "visual_prompts", "voiceover_script", "duration", "metadata")),
      sorted(bp.keys()))
check("metadata untouched", bp["metadata"]["scene_count"] == 3 and bp["metadata"]["total_duration_seconds"] == 23.0)
check("duration string unchanged", bp["duration"] == "23s", bp["duration"])

print()
print("=" * 72)
print("8. _normalize_blueprint respects explicit per-scene motion direction")
print("=" * 72)
raw_mixed = {
    "severity": "Medium",
    "scenes": [
        {"title": "Overview", "narration": "Overview of the advisory findings.", "duration_seconds": 5,
         "theme_severity": "info", "active_icon": "shield", "animation_style": "slide_in",
         "heading": "Advisory Overview", "subtext": "What changed and why it matters."},
        {"title": "Encryption Impact", "narration": "Ransomware encrypts shared storage.", "duration_seconds": 6,
         "theme_severity": "critical", "active_icon": "lock", "animation_style": "pulse_alert"},
        {"title": "Metrics", "narration": "Exposure metrics across the estate.", "duration_seconds": 6,
         "metrics": [{"label": "Hosts", "value": "1200"}]},
    ],
}
bp2 = ve._normalize_blueprint(raw_mixed, {"severity": "Medium"}, "General", "Informative", "English", "Summarize", "Cybersecurity Technical")
ms2 = bp2["motion_script"]
check("explicit themes kept", [e["theme_severity"] for e in ms2] == ["info", "critical", "warning"],
      [e["theme_severity"] for e in ms2])
check("explicit icons kept", [e["active_icon"] for e in ms2][:2] == ["shield", "lock"], [e["active_icon"] for e in ms2])
check("explicit styles kept", [e["animation_style"] for e in ms2][:2] == ["slide_in", "pulse_alert"])
check("scene 3 style falls back to kinetic_zoom (has metrics)", ms2[2]["animation_style"] == "kinetic_zoom", ms2[2]["animation_style"])
check("scene 3 theme uses blueprint fallback (Medium -> warning)", ms2[2]["theme_severity"] == "warning")
check("explicit heading/subtext kept", ms2[0]["heading"] == "Advisory Overview" and ms2[0]["subtext"] == "What changed and why it matters.")

print()
print("=" * 72)
print("9. Severity classifier + style inference tables")
print("=" * 72)
sev_cases = {"critical": "critical", "HIGH": "critical", "severe": "critical", "Medium": "warning",
             "moderate": "warning", "Warning": "warning", "elevated": "warning", "low": "info",
             "informational": "info", "": "info", None: "info", "unknown-value": "info"}
for value, expected in sev_cases.items():
    got = ve._map_severity_to_motion(value)
    check(f"severity {value!r} -> {expected}", got == expected, got)

style_cases = [((1, "critical", []), "slide_in"), ((2, "critical", []), "pulse_alert"),
               ((2, "warning", [{"label": "a"}]), "kinetic_zoom"), ((3, "info", []), "slide_in"),
               ((4, "warning", []), "slide_in")]
for args, expected in style_cases:
    got = ve._infer_motion_style(*args)
    check(f"style {args} -> {expected}", got == expected, got)

print()
print("=" * 72)
print("10. process_video_transformation skips rendering when the stack is absent")
print("=" * 72)
calls = {"render": 0}
original_generate = ve.generate_video_blueprint
original_create = ve.create_video
ve.generate_video_blueprint = lambda **kwargs: bp
ve.create_video = lambda blueprint, output_path=None: calls.__setitem__("render", calls["render"] + 1) or output_path
try:
    ve.HEAVY_RENDER_AVAILABLE = False
    out = ve.process_video_transformation({"severity": "High", "title": "T"}, output_dir=os.path.join(os.environ.get("TEMP", "."), "mo_test_out"))
    check("returns blueprint without rendering", out["blueprint"] is bp and out["video_path"] is None, out["video_path"])
    check("create_video not called when stack missing", calls["render"] == 0, calls["render"])

    calls["render"] = 0
    ve.HEAVY_RENDER_AVAILABLE = True
    tmp_out = os.path.join(os.environ.get("TEMP", "."), "mo_test_out2")
    out2 = ve.process_video_transformation({"severity": "High", "title": "T"}, output_dir=tmp_out)
    check("renders and returns generated_advisory.mp4 path when stack present",
          calls["render"] == 1 and out2["video_path"] == os.path.join(tmp_out, "generated_advisory.mp4"), out2["video_path"])
    check("output dir created", os.path.isdir(tmp_out))
finally:
    ve.generate_video_blueprint = original_generate
    ve.create_video = original_create
    ve.HEAVY_RENDER_AVAILABLE = original_flag

print()
print("=" * 72)
print("11. Prompt now requests the motion contract")
print("=" * 72)
src = open(os.path.join(MY_CODE, "modules", "video_engine.py"), "rb").read().decode("utf-8")
for token in ('9. Every scene must also carry motion direction', '"scene_id": 1', '"theme_severity": "critical"',
              '"active_icon": "shield"', '"animation_style": "slide_in"', '"heading": "short on-screen headline for this scene"',
              'required on every scene'):
    check(f"prompt contains {token[:46]!r}", token in src)
check("no LF-only lines introduced", src.count("\n") == src.count("\r\n"), (src.count("\n"), src.count("\r\n")))
check("heavy imports are inside the try block",
      "try:  # Optional" in src and src.index("import pyttsx3") > src.index("try:  # Optional"))

print()
print("=" * 72)
print("12. Sample motion_script payload (for frontend seeding)")
print("=" * 72)
print(json.dumps({"motion_script": ms}, indent=2)[:900])

print()
print("=" * 72)
print("13. Variety guard rescues a monotone model response")
print("=" * 72)
uniform_raw = {
    "title": "Monotone reel", "summary": "s", "severity": "Critical",
    "scenes": [
        {"title": "Default credentials exploited", "narration": "Operators left admin/admin in place.",
         "visual_prompt": "Analyst reviewing credential abuse", "duration_seconds": 8},
        {"title": "Encryption of imaging archives", "narration": "Ransomware encrypts every DICOM study.",
         "visual_prompt": "Locked hospital imaging server", "duration_seconds": 8},
        {"title": "Recommendations for mitigation", "narration": "Patch the gateways and rotate secrets.",
         "visual_prompt": "Network traffic across endpoints", "duration_seconds": 8},
    ],
}
for _scene in uniform_raw["scenes"]:
    _scene.update({"theme_severity": "critical", "active_icon": "shield", "animation_style": "slide_in"})
mono = ve._normalize_blueprint(uniform_raw, {"severity": "Critical", "title": "T"}, "General", "Informative", "English", "o", "s")
mono_styles = [entry["animation_style"] for entry in mono["motion_script"]]
mono_icons = [entry["active_icon"] for entry in mono["motion_script"]]
check("uniform styles are redistributed", len(set(mono_styles)) >= 2, mono_styles)
check("uniform icons are re-derived from scene text", len(set(mono_icons)) >= 2, mono_icons)
check("redistributed styles stay in the enum", all(s in ve._MOTION_STYLES for s in mono_styles), mono_styles)
check("re-derived icons stay in the enum", all(i in ve._MOTION_ICONS for i in mono_icons), mono_icons)
check("motion_script and scenes stay in sync",
      all(mono["scenes"][i]["animation_style"] == mono_styles[i] and mono["scenes"][i]["active_icon"] == mono_icons[i]
          for i in range(len(mono_styles))))

flat_raw = {
    "title": "Flat reel", "summary": "s", "severity": "Low",
    "scenes": [{"title": t, "narration": n, "theme_severity": "info", "active_icon": "shield",
                "animation_style": "slide_in", "duration_seconds": 6}
               for t, n in (("Alpha", "aaa"), ("Bravo", "bbb"), ("Charlie", "ccc"), ("Delta", "ddd"))],
}
flat = ve._normalize_blueprint(flat_raw, {"severity": "Low", "title": "T"}, "General", "Informative", "English", "o", "s")
flat_styles = [entry["animation_style"] for entry in flat["motion_script"]]
check("shapeless reel still rotates through all three styles", len(set(flat_styles)) == 3, flat_styles)

varied_raw = {
    "title": "Already varied", "summary": "s", "severity": "High",
    "scenes": [
        {"title": "A", "narration": "alpha", "theme_severity": "critical", "active_icon": "lock",
         "animation_style": "pulse_alert", "duration_seconds": 6},
        {"title": "B", "narration": "bravo", "theme_severity": "warning", "active_icon": "network",
         "animation_style": "kinetic_zoom", "duration_seconds": 6},
        {"title": "C", "narration": "charlie", "theme_severity": "info", "active_icon": "user_analyst",
         "animation_style": "slide_in", "duration_seconds": 6},
    ],
}
kept = ve._normalize_blueprint(varied_raw, {"severity": "High", "title": "T"}, "General", "Informative", "English", "o", "s")
check("a varied reel is left untouched",
      [e["animation_style"] for e in kept["motion_script"]] == ["pulse_alert", "kinetic_zoom", "slide_in"]
      and [e["active_icon"] for e in kept["motion_script"]] == ["lock", "network", "user_analyst"],
      [e["animation_style"] for e in kept["motion_script"]])

two_raw = {"title": "Two", "summary": "s", "severity": "High",
           "scenes": [{"title": "A", "narration": "alpha", "animation_style": "slide_in",
                       "active_icon": "shield", "duration_seconds": 6},
                      {"title": "B", "narration": "bravo", "animation_style": "slide_in",
                       "active_icon": "shield", "duration_seconds": 6}]}
short = ve._normalize_blueprint(two_raw, {"severity": "High", "title": "T"}, "General", "Informative", "English", "o", "s")
check("guard stays out of the way for a two-scene reel",
      [e["animation_style"] for e in short["motion_script"]] == ["slide_in", "slide_in"]
      and [e["active_icon"] for e in short["motion_script"]] == ["shield", "shield"],
      [e["animation_style"] for e in short["motion_script"]])

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for item in failures:
        print("  -", item)
    sys.exit(1)
print("ALL BACKEND CHECKS PASSED")
