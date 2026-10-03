import os
import json
import streamlit as st
import streamlit.components.v1 as components
import sys
from pathlib import Path

# Fix Python path so module imports resolution work automatically
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import core pipeline modules
from modules.extractor import extract_raw_text, lock_deterministic_parameters
from modules.security import (
    compute_sha256,
    log_transformation_audit_event,
    redact_sensitive_pii,
)
from modules.generators import (
    build_canonical_facts,
    generate_faqs,
    generate_infographic_svg,
    generate_pdf_advisory,
    generate_report,
    generate_summary,
)
from modules.social_engine import process_social_transformation
from modules.video_engine import generate_video_blueprint
from modules.presentation_engine import generate_dynamic_presentation
from modules.threat_intel_engine import retrieve_threat_intel, validate_advisory_against_evidence

# Page Configuration
st.set_page_config(
    page_title="UnifiOps | Content Transformation Engine",
    page_icon="?",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E88E5; margin-bottom: 0px; }
    .sub-header { font-size: 1rem; color: #666; margin-bottom: 25px; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { padding-top: 10px; padding-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)
st.markdown('<div class="main-header">? UnifiOps Content Transformation Engine</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Unified Document Processing, Multi-Format Generation & Automated Video Synthesis</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("?? Pipeline Settings")
    st.subheader("Document Ingestion")
    enable_sanitization = st.toggle("Enable PII & Security Redaction", value=True)
    st.divider()
    st.subheader("Video Generator Config")
    target_audience = st.selectbox("Target Audience", ["General Public", "Technical / IT Teams", "Executive Leadership", "Students"])
    tone = st.selectbox("Tone & Style", ["Informative", "Cybersecurity Technical", "Urgent / Advisory", "Corporate"])
    language = st.selectbox("Output Language", ["English", "Hindi", "Spanish"])
    detail_level = st.selectbox("Level of Detail", ["Concise", "Detailed", "Executive Brief"])
    communication_objective = st.selectbox("Communication Objective", ["Inform", "Mitigate", "Urgent Action"])
    content_style = st.selectbox("Content Style", ["Technical", "Corporate", "Simplified"])
    video_duration = st.select_slider("Target Video Duration", options=["30s", "60s", "90s", "2m"], value="60s")

col_left, col_right = st.columns([1, 1.2], gap="large")
with col_left:
    st.subheader("?? 1. Source Document Ingestion")
    uploaded_file = st.file_uploader("Upload Source File (PDF, DOCX, TXT)", type=["pdf", "docx", "txt"])
    manual_text = st.text_area("Or Paste Plain Text / Threat Advisory directly:", height=180, placeholder="Paste advisory content, threat reports, or technical logs here...")

    raw_text = ""
    source_label = "pasted_text"
    source_path = None
    if uploaded_file is not None:
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        source_path = os.path.join(temp_dir, uploaded_file.name)
        source_label = uploaded_file.name
        with open(source_path, "wb") as output_file:
            output_file.write(uploaded_file.getbuffer())
        try:
            raw_text = extract_raw_text(source_path)
            st.success(f"Successfully extracted content from `{uploaded_file.name}`")
        except Exception as exc:
            st.error(f"Extraction Error: {exc}")
    elif manual_text.strip():
        raw_text = manual_text.strip()
        source_label = "pasted_text"

    processed_text = ""
    redaction_stats = {"emails_redacted": 0, "secrets_redacted": 0}
    if raw_text:
        if enable_sanitization:
            try:
                processed_text, redaction_stats = redact_sensitive_pii(raw_text)
                st.info(f"?? Redaction applied (emails: {redaction_stats['emails_redacted']}, secrets: {redaction_stats['secrets_redacted']})")
            except Exception as exc:
                processed_text = raw_text
                st.warning(f"Sanitization skipped due to error: {exc}")
        else:
            processed_text = raw_text
        with st.expander("Preview Processed Source Text", expanded=False):
            st.text_area("Cleaned Input", processed_text, height=220, disabled=True)

with col_right:
    st.subheader("?? 2. Multi-Format Transformation")
    if not processed_text:
        st.info("Upload or paste a document on the left to activate transformation generators.")
    else:
        source_sha256 = compute_sha256(source_path if source_path else raw_text)
        social_settings = {
            "audience": target_audience,
            "tone": f"{tone}; {content_style} style",
            "objective": communication_objective,
            "language": language,
            "detail": detail_level,
            "content_style": content_style,
        }
        button_col1, button_col2 = st.columns(2)
        with button_col1:
            run_docs = st.button("Generate Written Formats", type="primary", use_container_width=True)
        with button_col2:
            run_video = st.button("Generate Video Output", type="secondary", use_container_width=True)

        tabs = st.tabs(["Summary & FAQs", "Social Posts", "Detailed Report", "PowerPoint Presentation", "Executive Briefing & Advisory", "Infographic", "Threat Intel & Verification", "Video Synthesis"])

        with tabs[0]:
            if run_docs:
                with st.spinner("Generating summary and FAQs via Ollama..."):
                    try:
                        st.session_state["summary_data"] = generate_summary(
                            processed_text, language=language, detail_level=detail_level,
                            objective=communication_objective, content_style=content_style,
                        )
                        st.session_state["faq_data"] = generate_faqs(
                            processed_text, language=language, detail_level=detail_level,
                            objective=communication_objective, content_style=content_style,
                        )
                        st.session_state["docs_generation_error"] = ""
                    except Exception as exc:
                        st.session_state["docs_generation_error"] = str(exc)
            if st.session_state.get("docs_generation_error"):
                st.error(st.session_state["docs_generation_error"])
            if "summary_data" in st.session_state:
                st.markdown("### Executive Summary")
                st.write(st.session_state["summary_data"])
                st.divider()
                st.markdown("### Key Questions & Answers (FAQs)")
                st.write(st.session_state.get("faq_data", ""))

        with tabs[1]:
            if run_docs:
                with st.spinner("Formatting platform social posts..."):
                    try:
                        st.session_state["social_data"] = process_social_transformation(
                            processed_text, settings=social_settings, platform="both"
                        )
                    except Exception as exc:
                        st.error(f"Social generation error: {exc}")
            if "social_data" in st.session_state:
                st.markdown("### Social Media Snippets")
                st.write(st.session_state["social_data"])

        with tabs[2]:
            if run_docs:
                with st.spinner("Structuring technical report..."):
                    try:
                        st.session_state["report_data"] = generate_report(
                            processed_text, language=language, detail_level=detail_level,
                            objective=communication_objective, content_style=content_style,
                        )
                    except Exception as exc:
                        st.error(f"Report generation error: {exc}")
            if "report_data" in st.session_state:
                st.markdown("### Structured Report")
                st.write(st.session_state["report_data"])

        with tabs[3]:
            if run_docs:
                with st.spinner("Generating dynamic slide outline and PowerPoint..."):
                    try:
                        pptx_path, slide_structure = generate_dynamic_presentation(processed_text)
                        st.session_state["pptx_path"] = pptx_path
                        st.session_state["slide_structure"] = slide_structure
                    except Exception as exc:
                        st.error(f"Presentation generation error: {exc}")
            if "slide_structure" in st.session_state:
                structure = st.session_state["slide_structure"]
                st.markdown(f"### {structure['presentation_title']}")
                st.caption(f"{len(structure['slides'])} generated content slides; speaker notes are embedded in the PPTX.")
                for slide in structure["slides"]:
                    with st.expander(f"Slide {slide['slide_number']}: {slide['title']}"):
                        for point in slide["key_points"]:
                            st.markdown(f"- {point}")
                        st.caption(f"Speaker notes: {slide['speaker_notes']}")
                if os.path.exists(st.session_state.get("pptx_path", "")):
                    with open(st.session_state["pptx_path"], "rb") as deck:
                        st.download_button("Download PowerPoint (.pptx)", deck, file_name="security_briefing.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")

        with tabs[4]:
            if run_docs:
                with st.spinner("Extracting structured facts and preparing the advisory PDF..."):
                    try:
                        facts = build_canonical_facts(
                            processed_text,
                            locked_params=lock_deterministic_parameters(processed_text),
                            language=language,
                            detail_level=detail_level,
                            objective=communication_objective,
                            content_style=content_style,
                        )
                        st.session_state["canonical_facts"] = facts
                        st.session_state["advisory_path"] = generate_pdf_advisory(facts)
                    except Exception as exc:
                        st.error(f"Advisory generation error: {exc}")
            if "canonical_facts" in st.session_state:
                st.markdown(f"### {st.session_state['canonical_facts'].get('title', 'Security Advisory')}")
                st.write(st.session_state["canonical_facts"].get("summary", ""))
                st.write({key: st.session_state["canonical_facts"].get(key) for key in ("severity", "cve_ids", "affected_systems", "recommended_actions")})
                advisory_path = st.session_state.get("advisory_path", "")
                if advisory_path and os.path.exists(advisory_path):
                    with open(advisory_path, "rb") as advisory_file:
                        is_pdf = advisory_path.lower().endswith(".pdf")
                        st.download_button(
                            "Download Advisory PDF" if is_pdf else "Download Advisory HTML",
                            advisory_file,
                            file_name=os.path.basename(advisory_path),
                            mime="application/pdf" if is_pdf else "text/html",
                        )
                    if not is_pdf:
                        st.warning("PDF rendering is unavailable in this environment; the generator returned its HTML advisory.")

        with tabs[5]:
            if run_docs:
                with st.spinner("Generating the SVG infographic..."):
                    try:
                        facts = st.session_state.get("canonical_facts")
                        if not facts:
                            facts = build_canonical_facts(
                                processed_text,
                                locked_params=lock_deterministic_parameters(processed_text),
                                language=language,
                                detail_level=detail_level,
                                objective=communication_objective,
                                content_style=content_style,
                            )
                            st.session_state["canonical_facts"] = facts
                        st.session_state["svg_path"] = generate_infographic_svg(facts)
                    except Exception as exc:
                        st.error(f"Infographic generation error: {exc}")
            svg_path = st.session_state.get("svg_path", "")
            if svg_path and os.path.exists(svg_path):
                with open(svg_path, "r", encoding="utf-8") as svg_file:
                    svg_markup = svg_file.read()
                components.html(svg_markup, height=440, scrolling=False)
                st.download_button(
                    "Download Infographic (.svg)",
                    data=svg_markup,
                    file_name="security_infographic.svg",
                    mime="image/svg+xml",
                )

        with tabs[6]:
            st.markdown("#### Source Integrity")
            st.code(source_sha256, language="text")
            st.caption("SHA-256 checksum for the uploaded file or pasted source.")
            if run_docs:
                with st.spinner("Searching local NVD/CISA/CERT-In evidence and checking the generated report..."):
                    try:
                        intel_result = retrieve_threat_intel(processed_text)
                        advisory_text = st.session_state.get("report_data", "")
                        validation = validate_advisory_against_evidence(advisory_text, processed_text, intel_result["matches"])
                        st.session_state["threat_intel_result"] = intel_result
                        st.session_state["threat_validation"] = validation
                        st.session_state["threat_source_hash"] = source_sha256
                        log_transformation_audit_event(
                            source_file=source_label,
                            source_hash=source_sha256,
                            operator_config={"action": "written_formats_and_threat_check", "audience": target_audience, "tone": tone, "language": language, "detail": detail_level, "objective": communication_objective, "content_style": content_style, "redaction": enable_sanitization},
                            verification_score=validation["fact_preservation"]["fact_preservation_rate"],
                            status=validation["status"],
                        )
                    except Exception as exc:
                        log_transformation_audit_event(
                            source_file=source_label,
                            source_hash=source_sha256,
                            operator_config={"action": "written_formats_and_threat_check", "audience": target_audience, "tone": tone, "language": language, "detail": detail_level, "objective": communication_objective, "content_style": content_style, "redaction": enable_sanitization},
                            verification_score=0.0,
                            status="FAILED_THREAT_CHECK",
                        )
                        st.error(f"Threat intelligence lookup failed: {exc}")
            if "threat_intel_result" in st.session_state:
                intel_result = st.session_state["threat_intel_result"]
                validation = st.session_state["threat_validation"]
                st.caption(f"Evidence source: {intel_result['retrieval']}")
                if intel_result.get("warning"):
                    st.warning(intel_result["warning"])
                if validation["status"] == "PASS":
                    st.success(f"? Verification PASS ? {validation['fact_preservation']['fact_preservation_rate']}% source/evidence fact preservation")
                else:
                    st.warning(f"?? Verification FLAGGED ? {validation['fact_preservation']['fact_preservation_rate']}% fact preservation")
                st.markdown("#### Retrieved Threat Evidence")
                if intel_result["matches"]:
                    for record in intel_result["matches"]:
                        cves = record.get("cve_ids") or ([record.get("cve_id")] if record.get("cve_id") else [])
                        with st.expander(f"{record.get('source_name', record.get('source_type', 'Evidence'))}: {record.get('title', 'Threat record')} ? {', '.join(cves) or 'No CVE'}"):
                            st.write(record.get("summary", ""))
                            st.write({key: record.get(key) for key in ("severity", "cvss_score", "affected_products", "affected_versions", "mitigations", "references", "relevance_score", "matched_by") if record.get(key)})
                else:
                    st.info("No matching local threat records were found. Add matching evidence to Ishita's datasets or RAG store.")
                st.markdown("#### Fact Check Details")
                st.json({key: value for key, value in validation.items() if key != "fact_preservation"})
                st.json(validation["fact_preservation"])
                st.markdown("#### Source Integrity")
                st.code(st.session_state.get("threat_source_hash", source_sha256), language="text")
                st.caption("SHA-256 source checksum ? audit event recorded in data/outputs/audit.log")
            elif not run_docs:
                st.info("Generate written formats to retrieve local threat evidence, validate the report, and record an audit entry.")

        with tabs[7]:
            video_status = "not_run"
            video_score = 100.0
            if run_video:
                with st.spinner("1/2: Generating video blueprint via Ollama..."):
                    try:
                        blueprint = generate_video_blueprint(
                            text=processed_text,
                            target_audience=target_audience,
                            tone=tone,
                            language=language,
                            duration=video_duration,
                            objective=communication_objective,
                            style=content_style,
                        )
                        st.session_state["blueprint"] = blueprint
                    except Exception as exc:
                        video_status = "failed"
                        st.error(f"Blueprint Error: {exc}")
                if "blueprint" in st.session_state and video_status != "failed":
                    with st.spinner("2/2: Rendering narrated scenes and MP4 video..."):
                        try:
                            os.makedirs("output", exist_ok=True)
                            video_path = os.path.join("output", "generated_advisory.mp4")
                            create_video(st.session_state["blueprint"], output_path=video_path)
                            st.session_state["video_path"] = video_path
                            video_status = "PASS"
                        except Exception as exc:
                            video_status = "failed"
                            st.error(f"Video Rendering Error: {exc}")
                log_transformation_audit_event(
                    source_file=source_label,
                    source_hash=source_sha256,
                    operator_config={"action": "video_generation", "audience": target_audience, "tone": tone, "language": language, "detail": detail_level, "objective": communication_objective, "content_style": content_style, "duration": video_duration},
                    verification_score=video_score,
                    status=video_status,
                )
            if "blueprint" in st.session_state:
                st.markdown("### Generated Script Blueprint")
                with st.expander("View Blueprint JSON", expanded=False):
                    st.json(st.session_state["blueprint"])
            if "video_path" in st.session_state and os.path.exists(st.session_state["video_path"]):
                st.markdown("### Rendered Video Output")
                st.video(st.session_state["video_path"])
                with open(st.session_state["video_path"], "rb") as video_file:
                    st.download_button(label="Download MP4 Video", data=video_file, file_name="unifiops_transformed_video.mp4", mime="video/mp4")
