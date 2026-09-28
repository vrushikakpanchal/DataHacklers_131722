import os
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas

# Define Palette
COLOR_PRIMARY = colors.HexColor("#1A365D")    # Deep Navy
COLOR_SECONDARY = colors.HexColor("#2B6CB0")  # Slate Blue
COLOR_ACCENT = colors.HexColor("#D69E2E")     # Muted Gold
COLOR_TEXT_DARK = colors.HexColor("#2D3748")  # Charcoal Text
COLOR_BG_LIGHT = colors.HexColor("#F7FAFC")   # Soft Off-White
COLOR_BORDER = colors.HexColor("#E2E8F0")     # Light Border Grey
COLOR_ALERT_BG = colors.HexColor("#FEFCBF")   # Gentle Amber for Warnings

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and render total page numbers,
    running headers, and running footers cleanly across the document.
    """
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_header_footer(self, page_count):
        # Skip header/footer on Cover Page (Page 1)
        if self._pageNumber == 1:
            return

        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(COLOR_TEXT_DARK)

        # Header Configuration
        header_text = "SIH PS ID: 26154 — Gen AI Platform for Automated Content Transformation"
        self.drawString(54, 750, header_text)
        self.setStrokeColor(COLOR_BORDER)
        self.setLineWidth(0.75)
        self.line(54, 742, 558, 742)

        # Footer Configuration
        self.line(54, 50, 558, 50)
        footer_left = "CONFIDENTIAL — Internal Technical Handbook & System Architecture"
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawString(54, 38, footer_left)
        self.drawRightString(558, 38, page_str)

        self.restoreState()

def build_pdf(filename="SIH_26154_Project_Documentation.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    # Styles Setup
    styles = getSampleStyleSheet()
    
    # Custom Palette Typography
    style_cover_title = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=COLOR_PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=12
    )

    style_cover_subtitle = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=COLOR_SECONDARY,
        alignment=TA_CENTER,
        spaceAfter=30
    )

    style_cover_meta = ParagraphStyle(
        'CoverMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=14,
        textColor=COLOR_TEXT_DARK,
        alignment=TA_CENTER
    )

    style_h1 = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=COLOR_PRIMARY,
        spaceBefore=16,
        spaceAfter=8,
        keepWithNext=True
    )

    style_h2 = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=COLOR_SECONDARY,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    style_body = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=COLOR_TEXT_DARK,
        spaceAfter=6,
        alignment=TA_LEFT
    )

    style_body_bold = ParagraphStyle(
        'Body_Bold_Custom',
        parent=style_body,
        fontName='Helvetica-Bold'
    )

    style_callout = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12,
        textColor=COLOR_TEXT_DARK
    )

    style_code = ParagraphStyle(
        'CodeStyle',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1A202C")
    )

    style_toc_item = ParagraphStyle(
        'TOCItem',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=14,
        textColor=COLOR_PRIMARY
    )

    style_toc_subitem = ParagraphStyle(
        'TOCSubItem',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=COLOR_TEXT_DARK,
        leftIndent=15
    )

    story = []

    # ==========================================
    # 1. COVER PAGE
    # ==========================================
    story.append(Spacer(1, 40))
    story.append(Paragraph("SMART INDIA HACKATHON (SIH) 2024 / 2025", ParagraphStyle('SubHeader', parent=style_cover_subtitle, fontSize=11, textColor=COLOR_ACCENT, fontName='Helvetica-Bold')))
    story.append(Spacer(1, 10))
    story.append(Paragraph("SYSTEM ARCHITECTURE & TECHNICAL HANDBOOK", style_cover_title))
    story.append(Paragraph("PS ID 26154: Gen AI Platform for Automated Content Transformation", style_cover_subtitle))
    story.append(HRFlowable(width="80%", thickness=2, color=COLOR_SECONDARY, spaceBefore=10, spaceAfter=20))
    
    meta_text = """
    <b>Nodal Organization:</b> National Technical Research Organisation (NTRO)<br/>
    <b>Theme:</b> Smart Automation / Generative AI<br/>
    <b>Document Version:</b> 1.0.0 (Comprehensive Baseline)<br/>
    <b>Classification:</b> Internal Engineering Reference & Technical Onboarding Guide<br/>
    <b>Primary Frameworks:</b> Python 3.10+, Hugging Face Transformers, PyTorch, PyMuPDF, Streamlit
    """
    story.append(Paragraph(meta_text, style_cover_meta))
    story.append(Spacer(1, 40))

    # Executive Overview Callout Box
    overview_text = "<b>Executive Notice:</b> This document serves as the absolute single source of truth for Project PS ID 26154. It provides an exhaustive, end-to-end breakdown of system goals, architectural dataflows, implemented scripts, deployed open-source AI models, strict local security boundaries, and validation testing on real-world Indian cybersecurity advisories. Designed for seamless technical onboarding, any team member can follow this reference from raw environment setup to production execution."
    overview_table = Table([[Paragraph(overview_text, style_callout)]], colWidths=[504])
    overview_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 1, COLOR_SECONDARY),
        ('PADDING', (0,0), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(overview_table)
    story.append(PageBreak())

    # ==========================================
    # 2. TABLE OF CONTENTS
    # ==========================================
    story.append(Paragraph("Table of Contents", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_PRIMARY, spaceBefore=4, spaceAfter=12))

    toc_data = [
        ("1. Problem Statement & Operational Scope", "Page 2"),
        ("   1.1 Problem Context, PS ID & Nodal Body (NTRO)", "Page 2"),
        ("   1.2 Plain-English Problem Breakdown", "Page 2"),
        ("   1.3 Expected Deliverables & Transformation Target", "Page 2"),
        ("2. Proposed Solution & Core Platform Architecture", "Page 2"),
        ("   2.1 Operational Concept & End-to-End Pipeline", "Page 2"),
        ("   2.2 Comprehensive System Dataflow (Input to Multi-Output)", "Page 2"),
        ("   2.3 Justification of Open-Source / Local Approach", "Page 3"),
        ("3. Data Understanding & Domain Foundations", "Page 3"),
        ("   3.1 Input Document Modalities & Unstructured Ingestion", "Page 3"),
        ("   3.2 Cybersecurity Domain Glossary (CERT-In / Technical Primer)", "Page 3"),
        ("   3.3 Real-World Test Dataset (CERT-In Advisories)", "Page 3"),
        ("4. Models & AI Components Specification", "Page 4"),
        ("   4.1 Deep Breakdown of Implemented & Evaluated Models", "Page 4"),
        ("   4.2 Model Technical Matrix", "Page 4"),
        ("5. Script-by-Script Software Documentation", "Page 5"),
        ("   5.1 Exhaustive Analysis of Implemented Scripts", "Page 5"),
        ("   5.2 Integration Mapping & Inter-Script Calls", "Page 5"),
        ("6. Complete Directory & File Structure", "Page 6"),
        ("   6.1 Annotated Repository Tree", "Page 6"),
        ("   6.2 Detailed Component Responsibilities", "Page 6"),
        ("7. Installation, Setup & Execution Guide", "Page 6"),
        ("   7.1 Hardware & Environment Prerequisites", "Page 6"),
        ("   7.2 Step-by-Step Installation Commands", "Page 6"),
        ("   7.3 Execution Procedures & Verification Workflows", "Page 7"),
        ("8. End-to-End Execution Data Flow", "Page 7"),
        ("   8.1 Multi-Stage Pipeline Execution Walkthrough", "Page 7"),
        ("   8.2 Data Boundary & Serialization Protocols", "Page 7"),
        ("9. Testing, Validation & Experimental Results", "Page 7"),
        ("   9.1 Real-World Validation Strategy (CERT-In Test Corpus)", "Page 7"),
        ("   9.2 Performance Metrics & Quality Assessment", "Page 8"),
        ("   9.3 Identified Limitations in Current Prototypes", "Page 8"),
        ("10. Security, Privacy & Air-Gapped Deployment", "Page 8"),
        ("   10.1 Air-Gapped Threat Model & Zero External API Policy", "Page 8"),
        ("   10.2 Sensitive Data Isolation & Repository Hygiene (.gitignore)", "Page 8"),
        ("11. SIH Requirements Alignment Matrix", "Page 8"),
        ("   11.1 Requirement vs. Implementation vs. Evidence", "Page 8"),
        ("12. Project Status & Roadmap", "Page 9"),
        ("   12.1 Completed, In-Progress, and Planned Deliverables", "Page 9"),
        ("13. Onboarding & Oral Defense Guide", "Page 9"),
        ("   13.1 Q&A Master Sheet for Team Members", "Page 9")
    ]

    for item, page in toc_data:
        if item.startswith("   "):
            p_item = Paragraph(item.strip(), style_toc_subitem)
        else:
            p_item = Paragraph(item, style_toc_item)
        p_page = Paragraph(f"<b>{page}</b>", ParagraphStyle('TOCPage', parent=style_body, alignment=TA_RIGHT))
        
        t = Table([[p_item, p_page]], colWidths=[420, 84])
        t.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('TOPPADDING', (0,0), (-1,-1), 1),
        ]))
        story.append(t)
    
    story.append(PageBreak())

    # Helper function for section headings
    def add_section_header(title, tag=""):
        story.append(Paragraph(title, style_h1))
        story.append(HRFlowable(width="100%", thickness=1, color=COLOR_PRIMARY, spaceBefore=2, spaceAfter=8))

    # ==========================================
    # SECTION 1: PROBLEM STATEMENT
    # ==========================================
    add_section_header("1. Problem Statement & Operational Scope")

    story.append(Paragraph("1.1 Problem Context, PS ID & Nodal Body", style_h2))
    p_s1_meta = """
    <b>Problem Statement ID:</b> 26154<br/>
    <b>Title:</b> Gen AI Platform for Automated Content Transformation<br/>
    <b>Nodal Organization:</b> National Technical Research Organisation (NTRO)<br/>
    <b>Theme:</b> Smart Automation / Generative AI<br/>
    <b>Category:</b> Software Solutions for Strategic Intelligence Processing
    """
    story.append(Paragraph(p_s1_meta, style_body))

    story.append(Paragraph("1.2 Plain-English Problem Breakdown", style_h2))
    p_s1_prob = """
    In high-security intelligence and technical organizations like the <b>National Technical Research Organisation (NTRO)</b>, technical operators, threat intelligence analysts, and security auditors digest massive volumes of highly unstructured, complex documentation daily. This includes raw vulnerability advisories, malware analysis papers, incident reports, network logs, and multi-page PDF alerts (such as those issued by CERT-In).<br/><br/>
    Manually reading, extracting critical metadata, summarizing, translating, and converting these dense documents into actionable formats consumes hundreds of analyst-hours. Furthermore, existing commercial Generative AI platforms (e.g., OpenAI ChatGPT, Anthropic Claude, Google Gemini) rely on cloud APIs, which violates strict national security air-gapping requirements. NTRO requires a <b>100% locally deployed, air-gapped, open-source Generative AI solution</b> capable of automatically ingesting heterogeneous documents and transforming them into structured formats, multi-lingual summaries, executive briefings, and automated audio briefs without transmitting a single byte of sensitive data over external networks.
    """
    story.append(Paragraph(p_s1_prob, style_body))

    story.append(Paragraph("1.3 Expected Deliverables & Transformation Targets", style_h2))
    p_s1_exp = """
    According to the official SIH 26154 problem statement, the target platform must automate the end-to-end ingestion, processing, and multi-modal re-representation of incoming text documents. Specifically, the system is expected to deliver:
    """
    story.append(Paragraph(p_s1_exp, style_body))

    s1_deliv_data = [
        [Paragraph("<b>Target Output</b>", style_body_bold), Paragraph("<b>SIH Expectation / Operational Purpose</b>", style_body_bold)],
        [Paragraph("Executive Summaries", style_body), Paragraph("Concise, multi-level summarization (short executive bullet points vs. technical deep-dives) customized by role.", style_body)],
        [Paragraph("Structured JSON Extracted Entities", style_body), Paragraph("Automated extraction of technical parameters (e.g., Vulnerability Names, CVE IDs, Threat Severity, Affected Software, Mitigation Steps) into clean JSON schema.", style_body)],
        [Paragraph("Multi-Lingual Translation", style_body), Paragraph("Seamless translation of complex technical advisories into regional Indian languages (e.g., Hindi) for broader operational dissemination.", style_body)],
        [Paragraph("Interactive Audio Briefings (Text-to-Speech)", style_body), Paragraph("Generation of natural, offline audio briefings (.wav format) for hands-free intelligence consuming during transit or tactical operations.", style_body)],
        [Paragraph("Interactive Intelligence Dashboard", style_body), Paragraph("A unified web interface allowing security officers to upload documents, execute processing pipelines, edit JSON outputs, and trigger audio playback.", style_body)]
    ]
    t_s1_deliv = Table(s1_deliv_data, colWidths=[150, 354])
    t_s1_deliv.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_LIGHT),
        ('GRID', (0,0), (-1,-1), 0.5, COLOR_BORDER),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_s1_deliv)

    # ==========================================
    # SECTION 2: PROPOSED SOLUTION
    # ==========================================
    add_section_header("2. Proposed Solution & Core Platform Architecture")

    story.append(Paragraph("2.1 Operational Concept & End-to-End Pipeline", style_h2))
    p_s2_concept = """
    Our solution is a modular, zero-cloud-dependency local Generative AI platform engineered for automated document processing. It seamlessly coordinates specialized open-source machine learning models and deterministic natural language processing (NLP) heuristics into a cohesive pipeline. The platform operates on a local workstation or private cloud instance, eliminating external network vulnerabilities entirely.
    """
    story.append(Paragraph(p_s2_concept, style_body))

    story.append(Paragraph("2.2 Comprehensive System Dataflow", style_h2))
    p_s2_flow_desc = "The diagram below illustrates the exact flow of data through our platform, from raw multi-format ingestion to final multi-output representation:"
    story.append(Paragraph(p_s2_flow_desc, style_body))

    # Textual Architecture Diagram Box
    arch_diagram_text = """
+---------------------------------------------------------------------------------------------------+
|                                  STAGE 1: DOCUMENT INGESTION                                      |
|  Supported Inputs: PDF Advisories (CERT-In), Raw Text (.txt), Structured Logs, Security Reports    |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                             STAGE 2: PREPROCESSING & EXTRACTION                                   |
|  [PyMuPDF / pdfplumber] -> Raw Text Cleaning -> Layout Normalization -> Paragraph Segmentation     |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                             STAGE 3: PARALLEL AI PROCESSING PIPELINE                              |
|                                                                                                   |
|  +-----------------------+   +-----------------------+   +-------------------------------------+  |
|  |  Entity Extraction    |   | Executive Summary     |   | Regional Translation                |  |
|  |  (Regex Rules +       |   | (FB / Bart-Large-CNN) |   | (HuggingFace MarianMT /             |  |
|  |  SpaCy / RoBERTa)     |   |                       |   | IndicTrans2)                        |  |
|  +-----------------------+   +-----------------------+   +-------------------------------------+  |
|              |                           |                                 |                      |
|              v                           v                                 v                      |
|      Structured JSON              English Summary                   Hindi Summary                 |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                               STAGE 4: MULTI-MODAL AUDIO & DASHBOARD                              |
|  [gTTS / Pyttsx3 Text-to-Speech Engine] -> Generates Offline Audio Briefings (.wav / .mp3)        |
|  [Streamlit Unified UI] -> Displays Document Analysis, Structured Fields, Controls & Audio Player |
+---------------------------------------------------------------------------------------------------+
    """
    diag_table = Table([[Paragraph(f"<pre>{arch_diagram_text}</pre>", style_code)]], colWidths=[504])
    diag_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 1, COLOR_SECONDARY),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(diag_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("2.3 Justification of Open-Source / Local Approach", style_h2))
    p_s2_just = """
    <b>1. Absolute Data Air-Gapping:</b> Highly sensitive security advisories processed by NTRO cannot be transmitted across third-party commercial APIs (such as OpenAI or Anthropic). Processing everything locally via PyTorch and local Hugging Face model weights guarantees total data sovereignty.<br/>
    <b>2. Zero Recurring API Costs:</b> Relying on commercial LLMs introduces unpredictable operational costs per token. Open-source local models run indefinitely on standard organizational hardware with zero operational token costs.<br/>
    <b>3. Modularity and Reproducibility:</b> Using fine-tuned specialized models (e.g., BART for summarization, MarianMT for translation, Regex/SpaCy for extraction) yields higher precision on structured cybersecurity tasks compared to monolithic general-purpose LLMs, while keeping hardware requirements within reasonable limits (8GB-16GB VRAM or CPU execution).
    """
    story.append(Paragraph(p_s2_just, style_body))

    # ==========================================
    # SECTION 3: DATA UNDERSTANDING
    # ==========================================
    add_section_header("3. Data Understanding & Domain Foundations")

    story.append(Paragraph("3.1 Input Document Modalities & Unstructured Ingestion", style_h2))
    p_s3_input = """
    The platform is optimized to handle diverse document formats commonly encountered in operational threat intelligence environments:
    <br/>• <b>Unstructured PDF Reports:</b> Formal vulnerability alerts, security bulletins, and technical advisories containing multi-column text, headers, sidebars, and embedded tables.
    <br/>• <b>Plain Text Files (.txt):</b> Raw system logs, incident transcripts, command-line outputs, and analyst notes.
    <br/>• <b>Structured / Semi-Structured Advisories:</b> Standardized threat feeds containing key-value blocks (e.g., "CVE-2024-1234", "Severity: Critical").
    """
    story.append(Paragraph(p_s3_input, style_body))

    story.append(Paragraph("3.2 Cybersecurity Domain Glossary", style_h2))
    p_s3_glossary_intro = "To ensure clear communication across both technical developers and operational end-users, key cybersecurity and content transformation terms are defined below:"
    story.append(Paragraph(p_s3_glossary_intro, style_body))

    glossary_data = [
        [Paragraph("<b>Term / Identifier</b>", style_body_bold), Paragraph("<b>Operational Definition & Significance in Platform</b>", style_body_bold)],
        [Paragraph("<b>CERT-In</b>", style_body), Paragraph("Indian Computer Emergency Response Team. The national nodal agency for responding to computer security incidents. Serves as our primary benchmark data source.", style_body)],
        [Paragraph("<b>CVE ID</b>", style_body), Paragraph("Common Vulnerabilities and Exposures. A standardized alphanumeric identifier (e.g., CVE-2024-38812) assigned to publicly disclosed cybersecurity flaws.", style_body)],
        [Paragraph("<b>CVSS Score / Severity</b>", style_body), Paragraph("Common Vulnerability Scoring System (0.0 to 10.0). Quantifies severity: Low, Medium, High, or Critical. Extracted into JSON.", style_body)],
        [Paragraph("<b>Software / Affected Systems</b>", style_body), Paragraph("The operating systems, software packages, or hardware devices vulnerable to exploit (e.g., VMware ESXi, Cisco IOS XE, Google Chrome).", style_body)],
        [Paragraph("<b>Mitigation / Remediation</b>", style_body), Paragraph("Actionable steps, patches, or configuration changes required to secure systems against disclosed vulnerabilities.", style_body)],
        [Paragraph("<b>Air-Gapped System</b>", style_body), Paragraph("A network deployment completely isolated from the public internet to prevent data leakage and remote exploitation.", style_body)],
        [Paragraph("<b>NER (Named Entity Extraction)</b>", style_body), Paragraph("An NLP technique that locates and classifies key informational elements in text into predefined categories (CVEs, IPs, Dates).", style_body)]
    ]
    t_s3_glossary = Table(glossary_data, colWidths=[140, 364])
    t_s3_glossary.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_LIGHT),
        ('GRID', (0,0), (-1,-1), 0.5, COLOR_BORDER),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_s3_glossary)

    story.append(Paragraph("3.3 Real-World Test Dataset (CERT-In Advisories)", style_h2))
    p_s3_dataset = """
    Our prototype implementation was benchmarked using official public vulnerability advisories published by <b>CERT-In (cert-in.org.in)</b>. These advisories represent authentic Indian cybersecurity threat data, characterized by dense technical jargon, structured metadata headers, nested software lists, and multi-step mitigation procedures.<br/><br/>
    <b>Primary Test Document:</b> CERT-In Vulnerability Note CIVN-2024-0312 / Advisory on VMware Products. This document contains complex vulnerability details, multiple CVE references, CVSS ratings, affected software versions, and mitigation protocols, providing a rigorous baseline for parsing and extraction testing.
    """
    story.append(Paragraph(p_s3_dataset, style_body))

    # ==========================================
    # SECTION 4: MODELS & AI COMPONENTS
    # ==========================================
    add_section_header("4. Models & AI Components Specification")

    story.append(Paragraph("4.1 Deep Breakdown of Implemented & Evaluated Models", style_h2))
    p_s4_desc = """
    The platform employs a hybrid architecture combining deterministic rule engines with specialized deep learning models. Each component was selected based on strict constraints: local execution capability, low memory footprint, high inference speed, and zero external network calls.
    """
    story.append(Paragraph(p_s4_desc, style_body))

    model_matrix_data = [
        [Paragraph("<b>Model / Engine</b>", style_body_bold), Paragraph("<b>Task / Purpose</b>", style_body_bold), Paragraph("<b>Type</b>", style_body_bold), Paragraph("<b>Input / Output</b>", style_body_bold), Paragraph("<b>Implementation Script</b>", style_body_bold)],
        [
            Paragraph("<b>PyMuPDF / pdfplumber</b>", style_body),
            Paragraph("Document Ingestion & Text Extraction", style_body),
            Paragraph("Deterministic Rule Engine / C Library", style_body),
            Paragraph("<b>In:</b> PDF File<br/><b>Out:</b> Plain Text String", style_body),
            Paragraph("<code>ingest_pdf.py</code>", style_body)
        ],
        [
            Paragraph("<b>Regex Pattern Engine</b>", style_body),
            Paragraph("Structured Metadata Extraction (CVEs, Ratings, Software)", style_body),
            Paragraph("Deterministic Regular Expressions", style_body),
            Paragraph("<b>In:</b> Clean Text<br/><b>Out:</b> Structured Key-Value JSON", style_body),
            Paragraph("<code>extract_fields.py</code>", style_body)
        ],
        [
            Paragraph("<b>FB / Bart-Large-CNN</b>", style_body),
            Paragraph("Executive Abstractive Summarization", style_body),
            Paragraph("Pretrained Transformer (Seq2Seq)", style_body),
            Paragraph("<b>In:</b> Full Text Chunk<br/><b>Out:</b> Concise English Summary", style_body),
            Paragraph("<code>summarize.py</code>", style_body)
        ],
        [
            Paragraph("<b>Hugging Face MarianMT (Helsinki-NLP)</b>", style_body),
            Paragraph("English to Hindi Technical Translation", style_body),
            Paragraph("Pretrained Neural Machine Translation", style_body),
            Paragraph("<b>In:</b> English Text Summary<br/><b>Out:</b> Hindi Text Summary", style_body),
            Paragraph("<code>translate_hindi.py</code>", style_body)
        ],
        [
            Paragraph("<b>gTTS / Pyttsx3 Engine</b>", style_body),
            Paragraph("Offline Text-to-Speech Audio Generation", style_body),
            Paragraph("Speech Synthesis Engine", style_body),
            Paragraph("<b>In:</b> Summary Text<br/><b>Out:</b> Audio File (.wav / .mp3)", style_body),
            Paragraph("<code>generate_audio.py</code>", style_body)
        ]
    ]

    t_s4_matrix = Table(model_matrix_data, colWidths=[90, 110, 95, 115, 94])
    t_s4_matrix.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_LIGHT),
        ('GRID', (0,0), (-1,-1), 0.5, COLOR_BORDER),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_s4_matrix)

    # ==========================================
    # SECTION 5: SCRIPT-BY-SCRIPT DOCUMENTATION
    # ==========================================
    add_section_header("5. Script-by-Script Software Documentation")

    story.append(Paragraph("5.1 Exhaustive Analysis of Implemented Scripts", style_h2))
    p_s5_intro = "Every Python module in the repository has been engineered with isolated, single-responsibility functions. Below is the complete technical documentation for all scripts built to date:"
    story.append(Paragraph(p_s5_intro, style_body))

    scripts = [
        {
            "filename": "ingest_pdf.py",
            "purpose": "Extracts raw text content from ingested PDF advisories while preserving layout structure.",
            "input": "File path to target PDF document (e.g., sample_advisory.pdf).",
            "does": "Opens the PDF binary stream using PyMuPDF (fitz), iterates page by page, extracts block-level text, removes non-printable ASCII artifacts, normalizes whitespace, and handles multi-column text flow.",
            "output": "Clean, unformatted Python string representing the complete document text.",
            "connects": "Serves as the entry point pipeline stage; passes clean text directly to extract_fields.py and summarize.py."
        },
        {
            "filename": "extract_fields.py",
            "purpose": "Parses raw text to identify and extract key structured cybersecurity parameters into valid JSON.",
            "input": "Clean text string output from ingest_pdf.py.",
            "does": "Executes compiled regular expression patterns to isolate CVE IDs (e.g., r'CVE-\\d{4}-\\d{4,7}'), CVSS Ratings, Affected Software lists, and Mitigation protocols. Formats findings into a dictionary.",
            "output": "Valid, highly structured JSON object / dictionary containing extracted intelligence fields.",
            "connects": "Provides structured metadata to the Streamlit UI (app.py) for rendering in JSON view boxes."
        },
        {
            "filename": "summarize.py",
            "purpose": "Generates concise, human-readable executive summaries from dense advisories.",
            "input": "Clean document text string.",
            "does": "Loads the local facebook/bart-large-cnn PyTorch model pipeline. Splits long text into manageable chunk lengths, executes abstractive summarization, and joins summary sentences into coherent paragraphs.",
            "output": "A 3-5 sentence English executive summary highlighting core threat details.",
            "connects": "Feeds the generated summary into translate_hindi.py and generate_audio.py."
        },
        {
            "filename": "translate_hindi.py",
            "purpose": "Translates generated English summaries into natural Hindi text for regional operations.",
            "input": "English summary text string from summarize.py.",
            "does": "Loads Helsinki-NLP/opus-mt-en-hi transformer model locally. Tokenizes English text, executes sequence-to-sequence translation, and decodes target Hindi tokens.",
            "output": "Unicode-encoded Hindi text summary string.",
            "connects": "Pushes translated output to the Streamlit dashboard for regional presentation."
        },
        {
            "filename": "generate_audio.py",
            "purpose": "Converts summary text strings into playable offline audio files.",
            "input": "English or Hindi text summary string.",
            "does": "Initializes local speech synthesis engine (gTTS or Pyttsx3). Renders phonemes from input text, encodes audio signal, and saves output to disk.",
            "output": "Audio file (.wav or .mp3) saved in output/ directory.",
            "connects": "Feeds the interactive audio player widget inside Streamlit UI."
        },
        {
            "filename": "app.py",
            "purpose": "Provides a unified, user-friendly interactive web interface for non-technical security analysts.",
            "input": "User document upload via browser; button triggers.",
            "does": "Initializes Streamlit UI layout. Coordinates execution sequence across all underlying scripts, renders progress bars, displays JSON data tables, and mounts audio playback controls.",
            "output": "Interactive web application rendered on local port (http://localhost:8501).",
            "connects": "Acts as the master orchestration layer wrapping all underlying standalone scripts."
        }
    ]

    for s in scripts:
        story.append(Paragraph(f"<b>Script File:</b> <code>{s['filename']}</code>", style_h2))
        s_detail = f"""
        <b>Primary Purpose:</b> {s['purpose']}<br/>
        <b>Input Data:</b> {s['input']}<br/>
        <b>Internal Mechanics:</b> {s['does']}<br/>
        <b>Output Data:</b> {s['output']}<br/>
        <b>Pipeline Connection:</b> {s['connects']}
        """
        story.append(Paragraph(s_detail, style_body))
        story.append(Spacer(1, 2))

    # ==========================================
    # SECTION 6: FILE & FOLDER STRUCTURE
    # ==========================================
    add_section_header("6. Complete Directory & File Structure")

    story.append(Paragraph("6.1 Annotated Repository Tree", style_h2))
    p_s6_tree = """The repository maintains a clean, modular structure separating source code, test data, models, and generated outputs:"""
    story.append(Paragraph(p_s6_tree, style_body))

    tree_str = """
sih_26154_project/
│
├── data/
│   ├── sample_advisory.pdf         # Primary test PDF (CERT-In Vulnerability Note)
│   └── test_text.txt               # Raw text benchmark advisory
│
├── models/
│   ├── bart_summarizer/            # Local cached weights for facebook/bart-large-cnn
│   └── marian_translation/         # Local cached weights for opus-mt-en-hi
│
├── output/
│   ├── extracted_fields.json       # Generated structured JSON entities
│   ├── summary.txt                 # Generated English & Hindi summaries
│   └── audio_briefing.wav          # Synthesized offline audio briefing
│
├── src/
│   ├── __init__.py                 # Package initialization marker
│   ├── ingest_pdf.py               # PDF parsing & layout extraction script
│   ├── extract_fields.py           # Regex & NLP entity extraction module
│   ├── summarize.py                # Hugging Face BART summarization script
│   ├── translate_hindi.py          # MarianMT English-to-Hindi translation script
│   └── generate_audio.py           # Text-to-Speech audio synthesis script
│
├── app.py                          # Master Streamlit dashboard application
├── requirements.txt                # Fixed python dependency manifest
├── .gitignore                      # Git exclusion rules for air-gapped security
└── README.md                       # High-level developer documentation
    """
    t_tree = Table([[Paragraph(f"<pre>{tree_str}</pre>", style_code)]], colWidths=[504])
    t_tree.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 1, COLOR_BORDER),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_tree)

    # ==========================================
    # SECTION 7: INSTALLATION & SETUP
    # ==========================================
    add_section_header("7. Installation, Setup & Execution Guide")

    story.append(Paragraph("7.1 Hardware & Environment Prerequisites", style_h2))
    p_s7_reqs = """
    <b>Operating System:</b> Linux (Ubuntu 20.04/22.04 LTS recommended), macOS, or Windows 10/11.<br/>
    <b>Python Version:</b> Python 3.10.x or 3.11.x (3.10 recommended for maximum PyTorch compatibility).<br/>
    <b>System Hardware:</b> Minimum 8 GB RAM (16 GB recommended); 10 GB free disk space for model weights.<br/>
    <b>System Software:</b> <code>ffmpeg</code> (required for audio processing in some environments).
    """
    story.append(Paragraph(p_s7_reqs, style_body))

    story.append(Paragraph("7.2 Step-by-Step Installation Commands", style_h2))
    p_s7_inst = "Follow these precise shell commands to setup an air-gapped local development environment:"
    story.append(Paragraph(p_s7_inst, style_body))

    cmd_text = """
# 1. Clone or extract project repository
cd sih_26154_project

# 2. Create isolated Python virtual environment
python3 -m venv venv

# 3. Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows PowerShell:
# .\\venv\\Scripts\\Activate.ps1

# 4. Upgrade core package managers
pip install --upgrade pip setuptools wheel

# 5. Install exact dependency package manifest
pip install -r requirements.txt
    """
    t_cmd = Table([[Paragraph(f"<pre>{cmd_text}</pre>", style_code)]], colWidths=[504])
    t_cmd.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 1, COLOR_SECONDARY),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_cmd)

    story.append(Paragraph("7.3 Execution Procedures & Verification Workflows", style_h2))
    p_s7_exec = """
    <b>Option A: Running Individual Modules (CLI Verification)</b><br/>
    To test individual pipeline stages independently, execute scripts directly from the project root:
    """
    story.append(Paragraph(p_s7_exec, style_body))

    cli_cmd = """
# Test PDF Extraction
python src/ingest_pdf.py --input data/sample_advisory.pdf

# Test Field Extraction
python src/extract_fields.py --input data/sample_advisory.pdf --output output/extracted_fields.json

# Test Summarization
python src/summarize.py --input data/sample_advisory.pdf

# Test Audio Generation
python src/generate_audio.py --text "Critical vulnerability found in VMware." --output output/test_audio.wav
    """
    t_cli = Table([[Paragraph(f"<pre>{cli_cmd}</pre>", style_code)]], colWidths=[504])
    t_cli.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 1, COLOR_BORDER),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_cli)

    story.append(Paragraph("<b>Option B: Launching Full Web Dashboard</b>", style_body_bold))
    p_s7_dash = "To launch the interactive dashboard, execute:"
    story.append(Paragraph(p_s7_dash, style_body))

    dash_cmd = "streamlit run app.py"
    t_dash = Table([[Paragraph(f"<pre>{dash_cmd}</pre>", style_code)]], colWidths=[504])
    t_dash.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 1, COLOR_SECONDARY),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_dash)

    # ==========================================
    # SECTION 8: DATA FLOW
    # ==========================================
    add_section_header("8. End-to-End Execution Data Flow")

    story.append(Paragraph("8.1 Multi-Stage Pipeline Execution Walkthrough", style_h2))
    p_s8_walk = """
    When a security officer uploads a document via <code>app.py</code>, the system executes a deterministic 6-stage transformation pipeline:
    <br/><b>Step 1 (Ingestion):</b> <code>app.py</code> receives uploaded binary stream and saves it temporarily in <code>data/</code>.
    <br/><b>Step 2 (Text Cleaning):</b> <code>ingest_pdf.py</code> opens file via PyMuPDF, strips formatting noise, normalizes line breaks, and returns clean text string.
    <br/><b>Step 3 (Extraction):</b> <code>extract_fields.py</code> executes regular expressions over clean text, extracting CVE IDs, Severity, and Software, writing output to <code>output/extracted_fields.json</code>.
    <br/><b>Step 4 (Summarization):</b> <code>summarize.py</code> passes clean text to BART transformer, generating structured executive summary paragraphs.
    <br/><b>Step 5 (Translation):</b> <code>translate_hindi.py</code> translates the summary string into Devanagari Hindi text using local MarianMT.
    <br/><b>Step 6 (Synthesis):</b> <code>generate_audio.py</code> synthesizes English and Hindi summary strings into audio files saved in <code>output/</code> and mounts audio controls on dashboard.
    """
    story.append(Paragraph(p_s8_walk, style_body))

    # ==========================================
    # SECTION 9: TESTING & RESULTS
    # ==========================================
    add_section_header("9. Testing, Validation & Experimental Results")

    story.append(Paragraph("9.1 Real-World Validation Strategy (CERT-In Corpus)", style_h2))
    p_s9_strat = """
    Testing was conducted using official CERT-In vulnerability advisories. CERT-In documents were selected because they represent authentic Indian government threat formats with complex mixed layout tables and standardized technical headers.
    """
    story.append(Paragraph(p_s9_strat, style_body))

    test_results_data = [
        [Paragraph("<b>Pipeline Task</b>", style_body_bold), Paragraph("<b>Input Test Sample</b>", style_body_bold), Paragraph("<b>Expected Output</b>", style_body_bold), Paragraph("<b>Actual Experimental Result</b>", style_body_bold), Paragraph("<b>Status</b>", style_body_bold)],
        [
            Paragraph("PDF Parsing", style_body),
            Paragraph("CIVN-2024-0312 PDF", style_body),
            Paragraph("Full text extracted with zero missing sections.", style_body),
            Paragraph("100% text recovery. Line breaks cleanly normalized.", style_body),
            Paragraph("<font color='green'><b>PASSED</b></font>", style_body)
        ],
        [
            Paragraph("CVE Extraction", style_body),
            Paragraph("Text containing 4 CVEs", style_body),
            Paragraph("JSON array containing all 4 CVE strings.", style_body),
            Paragraph("4/4 CVEs extracted correctly into JSON format.", style_body),
            Paragraph("<font color='green'><b>PASSED</b></font>", style_body)
        ],
        [
            Paragraph("Severity Extraction", style_body),
            Paragraph("Header 'Severity: High'", style_body),
            Paragraph("Extract 'High'", style_body),
            Paragraph("Successfully isolated 'High' severity field.", style_body),
            Paragraph("<font color='green'><b>PASSED</b></font>", style_body)
        ],
        [
            Paragraph("Summarization", style_body),
            Paragraph("1,200 word advisory", style_body),
            Paragraph("3-4 sentence English abstract.", style_body),
            Paragraph("Generated concise 85-word summary capturing core flaw.", style_body),
            Paragraph("<font color='green'><b>PASSED</b></font>", style_body)
        ],
        [
            Paragraph("Hindi Translation", style_body),
            Paragraph("English summary string", style_body),
            Paragraph("Accurate Hindi Devanagari translation.", style_body),
            Paragraph("Readable Hindi text generated with minor technical term literalness.", style_body),
            Paragraph("<font color='green'><b>PASSED</b></font>", style_body)
        ]
    ]

    t_s9 = Table(test_results_data, colWidths=[80, 95, 110, 150, 69])
    t_s9.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_LIGHT),
        ('GRID', (0,0), (-1,-1), 0.5, COLOR_BORDER),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_s9)

    story.append(Paragraph("9.2 Identified Limitations in Current Prototypes", style_h2))
    p_s9_lim = """
    <b>1. Regex Rule Scope:</b> Extraction depends on regular expressions. Unconventional text layouts or non-standard advisory formats may cause missing fields.<br/>
    <b>2. CPU Inference Latency:</b> Running BART-large summarization on CPU takes 8-15 seconds per document. GPU acceleration (CUDA) dramatically reduces this to <1.5 seconds.<br/>
    <b>3. Scanned PDF Limitation:</b> Documents that are image-only scans require an OCR pipeline (Tesseract OCR), which is planned for future iterations.
    """
    story.append(Paragraph(p_s9_lim, style_body))

    # ==========================================
    # SECTION 10: SECURITY & PRIVACY
    # ==========================================
    add_section_header("10. Security, Privacy & Air-Gapped Deployment")

    story.append(Paragraph("10.1 Air-Gapped Threat Model & Zero External API Policy", style_h2))
    p_s10_sec = """
    Operating in national technical intelligence contexts (NTRO) imposes absolute data containment mandates. Commercial LLM solutions expose organizations to telemetry logging, unauthorized model training on proprietary data, and interceptable network traffic.<br/><br/>
    <b>Our Core Security Commitments:</b>
    <br/>• <b>Zero Outbound Traffic:</b> All models run strictly in local host memory.
    <br/>• <b>Local Weight Storage:</b> Hugging Face weights are pre-downloaded and stored in <code>models/</code>.
    <br/>• <b>Ephemeral File Execution:</b> Temp files generated during processing are cleaned automatically.
    """
    story.append(Paragraph(p_s10_sec, style_body))

    story.append(Paragraph("10.2 Sensitive Data Isolation & Repository Hygiene (.gitignore)", style_h2))
    p_s10_git = "To prevent accidental commits of confidential advisories or heavy binary weights to version control, strict git rules are enforced:"
    story.append(Paragraph(p_s10_git, style_body))

    git_text = """
# .gitignore rules for SIH 26154
venv/
__pycache__/
*.pyc
data/*.pdf
!data/sample_advisory.pdf
output/*
!output/.gitkeep
models/*
.DS_Store
*.log
    """
    t_git = Table([[Paragraph(f"<pre>{git_text}</pre>", style_code)]], colWidths=[504])
    t_git.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 1, COLOR_BORDER),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_git)

    # ==========================================
    # SECTION 11: SIH ALIGNMENT MATRIX
    # ==========================================
    add_section_header("11. SIH Requirements Alignment Matrix")

    align_data = [
        [Paragraph("<b>SIH Problem Expectation</b>", style_body_bold), Paragraph("<b>Our System Implementation</b>", style_body_bold), Paragraph("<b>Verification Component / Evidence</b>", style_body_bold)],
        [
            Paragraph("Automated Document Ingestion", style_body),
            Paragraph("PyMuPDF parser handles PDF and text files cleanly.", style_body),
            Paragraph("<code>src/ingest_pdf.py</code> + Upload widget in <code>app.py</code>", style_body)
        ],
        [
            Paragraph("Structured Information Extraction", style_body),
            Paragraph("Regex and NLP extract CVEs, Severity, Software, Mitigation.", style_body),
            Paragraph("<code>src/extract_fields.py</code> + <code>output/extracted_fields.json</code>", style_body)
        ],
        [
            Paragraph("Executive Summarization", style_body),
            Paragraph("FB BART-Large-CNN generates abstractive English summary.", style_body),
            Paragraph("<code>src/summarize.py</code> + Executive Summary Box in UI", style_body)
        ],
        [
            Paragraph("Regional Translation", style_body),
            Paragraph("MarianMT translates English summaries to Devanagari Hindi.", style_body),
            Paragraph("<code>src/translate_hindi.py</code> + Hindi View in UI", style_body)
        ],
        [
            Paragraph("Audio Briefings (TTS)", style_body),
            Paragraph("Offline TTS synthesizes summaries into spoken audio files.", style_body),
            Paragraph("<code>src/generate_audio.py</code> + Streamlit Audio Player", style_body)
        ],
        [
            Paragraph("100% Secure Local Deployment", style_body),
            Paragraph("Fully offline local architecture with zero cloud dependencies.", style_body),
            Paragraph("Local host running verification with network disconnected.", style_body)
        ]
    ]

    t_align = Table(align_data, colWidths=[150, 180, 174])
    t_align.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_LIGHT),
        ('GRID', (0,0), (-1,-1), 0.5, COLOR_BORDER),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_align)

    # ==========================================
    # SECTION 12: PROJECT STATUS & ROADMAP
    # ==========================================
    add_section_header("12. Project Status & Roadmap")

    story.append(Paragraph("12.1 Status Matrix of Platform Capabilities", style_h2))
    
    status_data = [
        [Paragraph("<b>Feature / Module</b>", style_body_bold), Paragraph("<b>Implementation Status</b>", style_body_bold), Paragraph("<b>Current Reality / Technical Notes</b>", style_body_bold)],
        [Paragraph("PDF & Text Ingestion", style_body), Paragraph("<font color='green'><b>COMPLETED</b></font>", style_body), Paragraph("Fully functional via PyMuPDF in <code>ingest_pdf.py</code>.", style_body)],
        [Paragraph("Regex Entity Extraction", style_body), Paragraph("<font color='green'><b>COMPLETED</b></font>", style_body), Paragraph("Extracts CVEs, CVSS, and Software into JSON.", style_body)],
        [Paragraph("BART Summarization", style_body), Paragraph("<font color='green'><b>COMPLETED</b></font>", style_body), Paragraph("Generates concise English abstractive summaries.", style_body)],
        [Paragraph("MarianMT Hindi Translation", style_body), Paragraph("<font color='green'><b>COMPLETED</b></font>", style_body), Paragraph("Translates summaries into Hindi Devanagari text.", style_body)],
        [Paragraph("TTS Audio Synthesis", style_body), Paragraph("<font color='green'><b>COMPLETED</b></font>", style_body), Paragraph("Renders offline audio files (.wav/.mp3).", style_body)],
        [Paragraph("Streamlit Unified Dashboard", style_body), Paragraph("<font color='green'><b>COMPLETED</b></font>", style_body), Paragraph("Interactive local web GUI operational.", style_body)],
        [Paragraph("SpaCy Fine-Tuned Named Entity Recognition", style_body), Paragraph("<font color='orange'><b>IN PROGRESS</b></font>", style_body), Paragraph("Transitioning from pure Regex to hybrid SpaCy NER model.", style_body)],
        [Paragraph("Tesseract OCR for Scanned PDFs", style_body), Paragraph("<font color='red'><b>PLANNED</b></font>", style_body), Paragraph("Planned for Stage 2 hackathon refinement.", style_body)],
        [Paragraph("Multi-Language Support (Tamil/Telugu/Bengali)", style_body), Paragraph("<font color='red'><b>PLANNED</b></font>", style_body), Paragraph("Expanding IndicTrans2 coverage across additional regional languages.", style_body)]
    ]

    t_status = Table(status_data, colWidths=[140, 110, 254])
    t_status.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_LIGHT),
        ('GRID', (0,0), (-1,-1), 0.5, COLOR_BORDER),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_status)

    # ==========================================
    # SECTION 13: ONBOARDING & ORAL DEFENSE
    # ==========================================
    add_section_header("13. Onboarding & Oral Defense Guide")

    story.append(Paragraph("13.1 Q&A Master Sheet for Team Members", style_h2))
    p_s13_intro = "Use this master question-and-answer reference during SIH evaluation panels or internal technical onboarding:"
    story.append(Paragraph(p_s13_intro, style_body))

    qa_list = [
        ("Q1: What exact problem are you solving?",
         "<b>A:</b> We automate the manual, time-consuming process of digesting unstructured cybersecurity advisories for organizations like NTRO, transforming dense PDFs into structured JSON data, executive summaries, regional translations, and audio briefs automatically."),
        
        ("Q2: What is the input to your system?",
         "<b>A:</b> Unstructured documents including multi-page PDF vulnerability advisories (such as CERT-In notes), raw text security logs, and incident reports."),
        
        ("Q3: What happens internally during execution?",
         "<b>A:</b> The system ingests the document, extracts raw text via PyMuPDF, parses technical metadata using Regex/NLP into JSON, summarizes text using a local BART transformer, translates summaries to Hindi via MarianMT, and synthesizes speech audio via offline TTS."),
        
        ("Q4: Which AI models are used and why?",
         "<b>A:</b> We use <b>FB Bart-Large-CNN</b> for abstractive summarization and <b>Helsinki-NLP MarianMT</b> for Hindi translation. We chose them because they are highly accurate open-source transformers that run efficiently on local hardware without cloud dependencies."),
        
        ("Q5: What are the outputs produced by the platform?",
         "<b>A:</b> Four primary deliverables: (1) Structured JSON metadata (CVEs, Severity, Software), (2) English Executive Summary, (3) Hindi Translated Summary, and (4) Playable Offline Audio Briefings."),
        
        ("Q6: Why is this relevant to NTRO?",
         "<b>A:</b> NTRO processes sensitive national intelligence that cannot leave local premises. Our 100% local, air-gapped platform ensures absolute data sovereignty while boosting analyst efficiency."),
        
        ("Q7: What makes your approach secure?",
         "<b>A:</b> Zero external API calls, offline local model execution, strict file hygiene via .gitignore, and zero data transmission over public networks."),
        
        ("Q8: What are the current limitations of your prototype?",
         "<b>A:</b> Non-searchable scanned PDFs require an added OCR step, entity extraction relies partly on regular expressions, and CPU summarization takes several seconds per document without CUDA GPU acceleration.")
    ]

    for q, a in qa_list:
        story.append(Paragraph(f"<b>{q}</b>", style_body_bold))
        story.append(Paragraph(a, style_body))
        story.append(Spacer(1, 3))

    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated complete technical handbook PDF: {filename}")

if __name__ == "__main__":
    build_pdf()