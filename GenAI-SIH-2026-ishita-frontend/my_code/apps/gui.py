import os
import sys
import json
import streamlit as st
import streamlit.components.v1 as components

# Add project root directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.extractor import process_and_lock_document
from modules.llm_engine import extract_canonical_facts
from modules.generators import (
    generate_pdf_advisory,
    generate_social_content,
    generate_presentation,
    generate_video_package,
    generate_infographic_svg
)
from modules.verifier import verify_all_generated_outputs
from modules.security import compute_sha256, redact_sensitive_pii, log_transformation_audit_event

# Streamlit Page Config
st.set_page_config(
    page_title="NTRO GenAI Content Transformation Engine",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Executive Theme
st.markdown("""
<style>
    .main-header { font-size: 26px; font-weight: bold; color: #1a365d; margin-bottom: 5px; }
    .sub-header { font-size: 14px; color: #4a5568; margin-bottom: 20px; }
    .stMetric { background-color: #f7fafc; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; }
    .status-pass { color: #2f855a; font-weight: bold; }
    .status-warn { color: #c05621; font-weight: bold; }
    .card { background-color: #ffffff; padding: 18px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 12px; }
</style>
""", unsafe_allow_html=True)

# Application Header
st.markdown("<div class='main-header'>NTRO Automated Multi-Format Content Transformation Platform</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>SIH Problem Statement ID: 26154 | Sovereign Local AI Model Engine (qwen2.5:3b)</div>", unsafe_allow_html=True)

# ---------------------------------------------------------
# Sidebar: Document Upload & Operator Controls
# ---------------------------------------------------------
st.sidebar.header("Document Ingestion & Controls")

uploaded_file = st.sidebar.file_uploader("Upload Threat Document (.txt, .pdf)", type=["txt", "pdf"])

st.sidebar.subheader("Operator Transformation Settings")
tone_setting = st.sidebar.selectbox("Communication Tone", ["Executive / Formal", "Urgent Threat Advisory", "Public Awareness"])
audience_setting = st.sidebar.selectbox("Target Audience", ["Leadership & Board", "Technical Operations", "General Public"])
detail_setting = st.sidebar.select_slider("Detail Level", options=["Compact", "Standard", "High"], value="High")

use_sample = st.sidebar.checkbox("Use Sample Advisory Document", value=(uploaded_file is None))

sample_file_path = os.path.join("data", "sample_inputs", "sample_advisory.txt")

# Handle Input File Selection
active_file_path = None
if uploaded_file is not None:
    temp_path = os.path.join("data", "sample_inputs", uploaded_file.name)
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    active_file_path = temp_path
elif use_sample and os.path.exists(sample_file_path):
    active_file_path = sample_file_path

process_btn = st.sidebar.button("Process & Generate Multi-Format Deliverables", type="primary", use_container_width=True)

# ---------------------------------------------------------
# Main Execution Pipeline
# ---------------------------------------------------------
if process_btn or "canonical_facts" in st.session_state:

    if process_btn and active_file_path:
        with st.spinner("Processing document: Extracting locked parameters, running local LLM schema engine..."):
            # 1. Ingest & Lock Parameters
            ingestion_res = process_and_lock_document(active_file_path)
            raw_text = ingestion_res["raw_text"]
            locked_params = ingestion_res["locked_parameters"]

            # 2. Security Redaction & Cryptographic Hash
            sanitized_text, redaction_stats = redact_sensitive_pii(raw_text)
            file_hash = compute_sha256(active_file_path)

            # 3. Local LLM Fact Extraction
            canonical_facts = extract_canonical_facts(sanitized_text, locked_params, model_name="qwen2.5:3b")

            # 4. Generate Multi-Format Deliverables
            pdf_path = generate_pdf_advisory(canonical_facts)
            social_posts = generate_social_content(canonical_facts, model_name="qwen2.5:3b")
            pptx_path = generate_presentation(canonical_facts)
            video_package = generate_video_package(canonical_facts, model_name="qwen2.5:3b")
            svg_path = generate_infographic_svg(canonical_facts)

            # 5. Verification & Anti-Hallucination Audit
            audit_report = verify_all_generated_outputs(canonical_facts, social_posts, video_package)

            # 6. Audit Logging
            log_transformation_audit_event(
                source_file=os.path.basename(active_file_path),
                source_hash=file_hash,
                operator_config={"tone": tone_setting, "audience": audience_setting, "detail": detail_setting},
                verification_score=audit_report["average_fact_preservation_rate"],
                status=audit_report["overall_status"]
            )

            # Save state
            st.session_state["canonical_facts"] = canonical_facts
            st.session_state["social_posts"] = social_posts
            st.session_state["video_package"] = video_package
            st.session_state["audit_report"] = audit_report
            st.session_state["pdf_path"] = pdf_path
            st.session_state["pptx_path"] = pptx_path
            st.session_state["svg_path"] = svg_path
            st.session_state["redaction_stats"] = redaction_stats
            st.session_state["file_hash"] = file_hash

    # Retrieve data from session state
    if "canonical_facts" in st.session_state:
        canonical_facts = st.session_state["canonical_facts"]
        social_posts = st.session_state["social_posts"]
        video_package = st.session_state["video_package"]
        audit_report = st.session_state["audit_report"]
        pdf_path = st.session_state["pdf_path"]
        pptx_path = st.session_state["pptx_path"]
        svg_path = st.session_state["svg_path"]
        redaction_stats = st.session_state["redaction_stats"]
        file_hash = st.session_state["file_hash"]

        # Top Metric Banner
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Threat Severity", canonical_facts.get("severity", "CRITICAL"))
        m2.metric("Fact Preservation Rate", f"{audit_report['average_fact_preservation_rate']}%")
        m3.metric("Locked Technical Indicators", len(canonical_facts.get("cve_ids", [])) + len(canonical_facts.get("locked_ips", [])))
        m4.metric("Verification Status", audit_report["overall_status"])

        st.markdown("---")

        # ---------------------------------------------------------
        # Multi-Tab Output Dashboard
        # ---------------------------------------------------------
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "Executive Briefing",
            "Social Media Engine",
            "Presentation Deck",
            "Video Storyboard",
            "Infographic Blueprint",
            "Security & Audit Log"
        ])

        # TAB 1: Executive Briefing & PDF
        with tab1:
            st.subheader("Executive Advisory Report")
            col_left, col_right = st.columns([2, 1])

            with col_left:
                st.markdown(f"### {canonical_facts.get('title', 'Security Advisory')}")
                st.write(f"**Summary:** {canonical_facts.get('summary')}")
                st.markdown("**Identified CVEs:** " + ", ".join([f"`{c}`" for c in canonical_facts.get("cve_ids", [])]))
                st.markdown("**Flagged IP Addresses:** " + ", ".join([f"`{ip}`" for ip in canonical_facts.get("locked_ips", [])]))
                st.markdown("**Recommended Mitigation Steps:**")
                for act in canonical_facts.get("recommended_actions", []):
                    st.markdown(f"- {act}")

            with col_right:
                st.info("File Export Options")
                if os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        btn_label = "Download PDF Report" if pdf_path.endswith(".pdf") else "Download HTML Report"
                        mime_type = "application/pdf" if pdf_path.endswith(".pdf") else "text/html"
                        st.download_button(btn_label, f, file_name=os.path.basename(pdf_path), mime=mime_type, use_container_width=True)

        # TAB 2: Social Media Engine
        with tab2:
            st.subheader("Multi-Platform Social Media Assets")
            s_col1, s_col2 = st.columns(2)

            with s_col1:
                st.markdown("#### LinkedIn Post")
                st.text_area("LinkedIn Publication Copy", value=social_posts.get("linkedin_post", ""), height=250)

            with s_col2:
                st.markdown("####Twitter/X Thread")
                tweets = social_posts.get("twitter_thread", [])
                for idx, tweet in enumerate(tweets, 1):
                    st.text_area(f"Tweet {idx} / {len(tweets)}", value=tweet, height=80)

        # TAB 3: Presentation Deck (.pptx)
        with tab3:
            st.subheader("Programmatic Slide Deck Preview (.pptx)")
            st.success("Slide deck generated using 4-slide cybersecurity briefing template.")

            if os.path.exists(pptx_path):
                with open(pptx_path, "rb") as f:
                    st.download_button(
                        "Download PowerPoint Deck (.pptx)",
                        f,
                        file_name="NTRO_Threat_Briefing.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True
                    )

            st.markdown("#### Slide Outline Structure:")
            st.markdown("""
            1. **Slide 1: Title Slide** — Title, Severity Rating, NTRO Briefing Designation.
            2. **Slide 2: Threat Overview** — Summary of Vulnerability & Affected Systems.
            3. **Slide 3: Technical Indicators** — Locked CVEs & Blocked IP Addresses.
            4. **Slide 4: Action Items** — Immediate Remediation Steps.
            """)

        # TAB 4: Video Storyboard
        with tab4:
            st.subheader("30-Second Alert Video Script & Storyboard")
            scenes = video_package.get("scenes", [])

            for scene in scenes:
                with st.expander(f"Scene {scene.get('scene_number', 1)}: {scene.get('on_screen_text', '')}", expanded=True):
                    sc1, sc2 = st.columns([1, 2])
                    with sc1:
                        st.markdown(f"**Visual:** {scene.get('visual_description', '')}")
                    with sc2:
                        st.markdown(f"**Narration:** *\"{scene.get('narration_text', '')}\"*")

        # TAB 5: Infographic Blueprint (.svg)
        with tab5:
            st.subheader("Infographic Vector Blueprint (.svg)")
            if os.path.exists(svg_path):
                with open(svg_path, "r", encoding="utf-8") as f:
                    svg_code = f.read()
                
                # Render SVG in browser
                components.html(svg_code, height=420, scrolling=False)

                st.download_button(
                    "Download SVG Vector Graphic",
                    svg_code,
                    file_name="infographic_blueprint.svg",
                    mime="image/svg+xml"
                )

        # TAB 6: Security & Audit Log
        with tab6:
            st.subheader("Local Security, Privacy & Integrity Audit")
            
            a1, a2 = st.columns(2)
            with a1:
                st.markdown("#### PII & Sensitive Data Masking Stats")
                st.json(redaction_stats)
            with a2:
                st.markdown("#### Cryptographic Data Provenance")
                st.code(f"SHA-256 Digest: {file_hash}")

            st.markdown("#### Verification Breakdown by Component:")
            st.json(audit_report["detailed_component_reports"])

else:
    st.info("Upload a document in the sidebar or check 'Use Sample Advisory Document' and click **Process & Generate Multi-Format Deliverables** to start.")