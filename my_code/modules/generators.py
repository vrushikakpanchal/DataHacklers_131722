import os
import json
import ollama
from html import escape
from textwrap import wrap
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from typing import Dict, Any
from modules.design_engine import as_items, infer_design, svg_icon

# Ensure output directory exists
OUTPUT_DIR = os.path.join("data", "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------
# Helper: Extract Canonical Facts Dictionary from Raw Text
# ---------------------------------------------------------
def build_canonical_facts(
    text: str,
    locked_params: Dict[str, Any] = None,
    model_name: str = "qwen2.5:3b",
    language: str = "English",
    detail_level: str = "Executive Brief",
    objective: str = "Inform",
    content_style: str = "Corporate",
) -> Dict[str, Any]:
    """
    Parses unstructured advisory text into a structured facts dictionary.
    Integrates locked deterministic parameters (CVEs, IPs, Severities) if provided.
    """
    prompt = f"""
    Analyze the following technical advisory text and extract structured facts.
    Write human-readable values in {language}, at a {detail_level} level, using a {content_style} style for the objective: {objective}.
    Preserve all source facts and do not translate or alter technical identifiers.
    
    Source Text:
    {text}
    
    Return a strictly valid JSON object with the following schema:
    {{
        "title": "Short descriptive advisory title",
        "severity": "CRITICAL / HIGH / MEDIUM / LOW",
        "summary": "2-3 sentence executive summary",
        "cve_ids": ["CVE-YYYY-XXXX"],
        "affected_systems": ["System or software names"],
        "locked_ips": ["IP addresses mentioned"],
        "recommended_actions": ["Specific actionable mitigation step 1", "Step 2"]
    }}
    Do NOT include markdown wrapping or extra text outside JSON.
    """
    
    try:
        response = ollama.chat(
            model=model_name,
            messages=[{'role': 'user', 'content': prompt}],
            format='json'
        )
        facts = json.loads(response['message']['content'])
    except Exception:
        facts = {
            "title": "Security Advisory Briefing",
            "severity": "HIGH",
            "summary": text[:250] + "...",
            "cve_ids": [],
            "affected_systems": [],
            "locked_ips": [],
            "recommended_actions": ["Review log files and apply latest system patches."]
        }

    # Merge locked deterministic parameters if available from extractor
    if locked_params:
        if locked_params.get("locked_cves"):
            facts["cve_ids"] = list(set(facts.get("cve_ids", []) + locked_params["locked_cves"]))
        if locked_params.get("locked_ips"):
            facts["locked_ips"] = list(set(facts.get("locked_ips", []) + locked_params["locked_ips"]))
        if locked_params.get("locked_severities") and not facts.get("severity"):
            facts["severity"] = locked_params["locked_severities"][0]

    return facts


# ---------------------------------------------------------
# 1. Text Transformation Generators for Streamlit App
# ---------------------------------------------------------
def generate_summary(
    text: str,
    model_name: str = "qwen2.5:3b",
    language: str = "English",
    detail_level: str = "Executive Brief",
    objective: str = "Inform",
    content_style: str = "Corporate",
) -> str:
    """Generate an executive summary using operator-selected output settings."""
    prompt = (
        f"Write in {language}. Detail level: {detail_level}. Objective: {objective}. "
        f"Content style: {content_style}. Preserve technical facts and identifiers. "
        f"Provide an executive summary with key findings and impact from this text:\n\n{text}"
    )
    response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}])
    return response['message']['content']


def generate_faqs(
    text: str,
    model_name: str = "qwen2.5:3b",
    language: str = "English",
    detail_level: str = "Executive Brief",
    objective: str = "Inform",
    content_style: str = "Corporate",
) -> str:
    """Generate key questions and answers using operator-selected settings."""
    prompt = (
        f"Write in {language}. Detail level: {detail_level}. Objective: {objective}. "
        f"Content style: {content_style}. Preserve technical facts and identifiers. "
        f"Generate 4 key Questions & Answers explaining the core issues and mitigations "
        f"in this text:\n\n{text}"
    )
    response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}])
    return response['message']['content']


def generate_report(
    text: str,
    model_name: str = "qwen2.5:3b",
    language: str = "English",
    detail_level: str = "Detailed",
    objective: str = "Mitigate",
    content_style: str = "Technical",
) -> str:
    """Generate a technical advisory report using operator-selected settings."""
    prompt = (
        f"Write in {language}. Detail level: {detail_level}. Objective: {objective}. "
        f"Content style: {content_style}. Preserve technical facts and identifiers. "
        "Construct a security report with sections for Overview, Threat Vectors, "
        "Impact Analysis, and Immediate Recommendations:\n\n" + text
    )
    response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}])
    return response['message']['content']


# ---------------------------------------------------------
# 2. Executive Brief & PDF Advisory Generator
# ---------------------------------------------------------
def generate_pdf_advisory(canonical_facts: Dict[str, Any]) -> str:
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; color: #222; }}
            .header {{ border-bottom: 3px solid #1a365d; padding-bottom: 10px; margin-bottom: 20px; }}
            .title {{ color: #1a365d; font-size: 24px; font-weight: bold; }}
            .badge {{ display: inline-block; padding: 4px 12px; font-weight: bold; color: white; background-color: #e53e3e; border-radius: 4px; }}
            .section {{ margin-top: 20px; }}
            .section-title {{ font-size: 16px; font-weight: bold; color: #2b6cb0; border-bottom: 1px solid #cbd5e0; padding-bottom: 4px; }}
            ul {{ line-height: 1.6; }}
            .code-box {{ background: #f7fafc; border: 1px solid #e2e8f0; padding: 10px; font-family: monospace; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="title">{canonical_facts.get('title', 'CYBERSECURITY ADVISORY')}</div>
            <p><strong>Severity:</strong> <span class="badge">{canonical_facts.get('severity', 'UNKNOWN')}</span></p>
        </div>
        
        <div class="section">
            <div class="section-title">Executive Summary</div>
            <p>{canonical_facts.get('summary', 'No summary available.')}</p>
        </div>

        <div class="section">
            <div class="section-title">Identified Vulnerabilities & Technical Indicators</div>
            <p><strong>Associated CVEs:</strong> {', '.join(canonical_facts.get('cve_ids', []))}</p>
            <p><strong>Affected Systems:</strong> {', '.join(canonical_facts.get('affected_systems', []))}</p>
            <p><strong>Locked IP Addresses:</strong></p>
            <div class="code-box">{', '.join(canonical_facts.get('locked_ips', []))}</div>
        </div>

        <div class="section">
            <div class="section-title">Recommended Mitigations</div>
            <ul>
                {''.join([f'<li>{action}</li>' for action in canonical_facts.get('recommended_actions', [])])}
            </ul>
        </div>
    </body>
    </html>
    """
    
    pdf_path = os.path.join(OUTPUT_DIR, "advisory_report.pdf")
    html_path = os.path.join(OUTPUT_DIR, "advisory_report.html")
    
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    try:
        from weasyprint import HTML
        HTML(string=html_content).write_pdf(pdf_path)
        return pdf_path
    except Exception as e:
        print(f"[!] WeasyPrint warning ({e}). HTML report saved to {html_path}")
        return html_path


# ---------------------------------------------------------
# 3. Social Media Generator (LinkedIn & Twitter/X)
# ---------------------------------------------------------
def generate_social_content(canonical_facts: Dict[str, Any], model_name: str = "qwen2.5:3b") -> Dict[str, Any]:
    prompt = f"""
    Transform the following security facts into two distinct social media posts:
    1. LinkedIn Post: Professional, urgent alert format with bullet points, threat overview, action items, and relevant hashtags.
    2. Twitter/X Thread: Exactly 3 numbered tweets. Keep each tweet strictly under 280 characters.
    
    Facts: {json.dumps(canonical_facts)}
    
    Return a strictly valid JSON object with keys: "linkedin_post" and "twitter_thread" (a list of 3 strings).
    Do NOT include markdown formatting or extra text outside the JSON object.
    """
    
    response = ollama.chat(
        model=model_name,
        messages=[{'role': 'user', 'content': prompt}],
        format='json'
    )
    
    social_data = json.loads(response['message']['content'])
    output_path = os.path.join(OUTPUT_DIR, "social_posts.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(social_data, f, indent=2)
        
    return social_data


# ---------------------------------------------------------
# 4. PowerPoint Slide Deck Generator (.pptx)
# ---------------------------------------------------------
def generate_presentation(canonical_facts: Dict[str, Any]) -> str:
    prs = Presentation()
    
    # Slide 1: Title Slide
    blank_slide_layout = prs.slide_layouts[0]
    slide1 = prs.slides.add_slide(blank_slide_layout)
    slide1.shapes.title.text = canonical_facts.get("title", "Threat Briefing")
    slide1.placeholders[1].text = f"Severity: {canonical_facts.get('severity', 'HIGH')}\nNTRO Cybersecurity Automated Briefing"
    
    # Slide 2: Threat Summary
    bullet_slide_layout = prs.slide_layouts[1]
    slide2 = prs.slides.add_slide(bullet_slide_layout)
    slide2.shapes.title.text = "Executive Threat Overview"
    tf2 = slide2.placeholders[1].text_frame
    tf2.text = canonical_facts.get("summary", "")
    p2 = tf2.add_paragraph()
    p2.text = f"Affected Systems: {', '.join(canonical_facts.get('affected_systems', []))}"
    
    # Slide 3: Vulnerabilities & IPs
    slide3 = prs.slides.add_slide(bullet_slide_layout)
    slide3.shapes.title.text = "Technical Indicators & CVEs"
    tf3 = slide3.placeholders[1].text_frame
    tf3.text = f"Identified CVEs: {', '.join(canonical_facts.get('cve_ids', []))}"
    p3 = tf3.add_paragraph()
    p3.text = f"Flagged IP Addresses: {', '.join(canonical_facts.get('locked_ips', []))}"
    
    # Slide 4: Recommendations
    slide4 = prs.slides.add_slide(bullet_slide_layout)
    slide4.shapes.title.text = "Mitigation & Next Steps"
    tf4 = slide4.placeholders[1].text_frame
    for action in canonical_facts.get("recommended_actions", []):
        p = tf4.add_paragraph()
        p.text = f"• {action}"

    pptx_path = os.path.join(OUTPUT_DIR, "presentation.pptx")
    prs.save(pptx_path)
    return pptx_path


# ---------------------------------------------------------
# 5. Video Package Generator (Script + Storyboard)
# ---------------------------------------------------------
def generate_video_package(canonical_facts: Dict[str, Any], model_name: str = "qwen2.5:3b") -> Dict[str, Any]:
    prompt = f"""
    Create a 30-second cybersecurity alert video script and visual storyboard based on these facts:
    {json.dumps(canonical_facts)}
    
    Return a JSON object with keys:
    - "video_title": str
    - "scenes": list of objects containing ("scene_number", "visual_description", "narration_text", "on_screen_text")
    """
    
    response = ollama.chat(
        model=model_name,
        messages=[{'role': 'user', 'content': prompt}],
        format='json'
    )
    
    video_data = json.loads(response['message']['content'])
    output_path = os.path.join(OUTPUT_DIR, "video_package.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(video_data, f, indent=2)
        
    return video_data


# ---------------------------------------------------------
# 6. Infographic Blueprint Generator (.svg)
# ---------------------------------------------------------
def _generate_infographic_svg_legacy(canonical_facts: Dict[str, Any]) -> str:
    severity = canonical_facts.get('severity', 'CRITICAL')
    cves = ', '.join(canonical_facts.get('cve_ids', []))
    ips = ', '.join(canonical_facts.get('locked_ips', []))
    actions = canonical_facts.get('recommended_actions', ['Apply patches immediately'])
    
    action_items_xml = ""
    for idx, act in enumerate(actions[:3]):
        action_items_xml += f'<text x="40" y="{260 + idx * 30}" font-family="Arial" font-size="14" fill="#2D3748">• {act[:65]}</text>\n'

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400" width="100%" height="100%">
        <!-- Background -->
        <rect width="800" height="400" fill="#F7FAFC" rx="10"/>
        
        <!-- Header Banner -->
        <rect width="800" height="70" fill="#1A365D" rx="10"/>
        <text x="30" y="45" font-family="Arial" font-size="22" font-weight="bold" fill="#FFFFFF">{canonical_facts.get('title', 'SECURITY ALERT')[:50]}</text>
        
        <!-- Severity Card -->
        <rect x="30" y="90" width="220" height="100" fill="#FFF5F5" stroke="#E53E3E" stroke-width="2" rx="8"/>
        <text x="45" y="120" font-family="Arial" font-size="14" fill="#C53030" font-weight="bold">SEVERITY RATING</text>
        <text x="45" y="160" font-family="Arial" font-size="28" fill="#E53E3E" font-weight="bold">{severity}</text>
        
        <!-- CVE Card -->
        <rect x="270" y="90" width="240" height="100" fill="#EBF8FF" stroke="#3182CE" stroke-width="2" rx="8"/>
        <text x="285" y="120" font-family="Arial" font-size="14" fill="#2B6CB0" font-weight="bold">IDENTIFIED CVEs</text>
        <text x="285" y="155" font-family="Arial" font-size="16" fill="#2D3748">{cves}</text>

        <!-- IP Card -->
        <rect x="530" y="90" width="240" height="100" fill="#EDF2F7" stroke="#4A5568" stroke-width="2" rx="8"/>
        <text x="545" y="120" font-family="Arial" font-size="14" fill="#2D3748" font-weight="bold">LOCKED IPs</text>
        <text x="545" y="155" font-family="Arial" font-size="16" fill="#2D3748">{ips}</text>

        <!-- Mitigations Section -->
        <rect x="30" y="210" width="740" height="160" fill="#FFFFFF" stroke="#CBD5E0" stroke-width="1.5" rx="8"/>
        <text x="40" y="238" font-family="Arial" font-size="16" font-weight="bold" fill="#1A365D">RECOMMENDED MITIGATION STEPS</text>
        {action_items_xml}
    </svg>"""

    svg_path = os.path.join(OUTPUT_DIR, "infographic_blueprint.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    return svg_path


def generate_infographic_svg(canonical_facts: Dict[str, Any]) -> str:
    """Render a responsive, content-aware SVG infographic and return its path."""
    design = infer_design(canonical_facts)
    c = design["palette"]
    title = escape(str(canonical_facts.get("title") or "Situation Brief"))
    severity = escape(str(canonical_facts.get("severity") or "UNRATED"))
    summary_lines = wrap(str(canonical_facts.get("summary") or "Key facts and recommended response"), 100) or [""]
    cves = as_items(canonical_facts.get("cve_ids"))
    ips = as_items(canonical_facts.get("locked_ips"))
    systems = as_items(canonical_facts.get("affected_systems"))
    actions = as_items(canonical_facts.get("recommended_actions")) or ["Review the source and confirm next steps."]
    action_lines = [(str(action), wrap(str(action), 64) or [""]) for action in actions]
    badges = [*(f"CVE {x}" for x in cves[:4]), *(f"IP {x}" for x in ips[:3])]
    layout = design["layout"]
    summary_y = 242 if badges else 212
    card_y = summary_y + 42 + 22 * len(summary_lines)
    if layout == "timeline":
        panel_height = max(180, 78 + len(actions) * 66)
    elif layout == "process_flow":
        panel_height = max(190, 72 + ((len(actions) + 2) // 3) * 112)
    elif layout == "split_comparison":
        panel_height = max(190, 125 + ((len(actions) + 1) // 2) * 38)
    else:
        panel_height = max(180, 65 + ((len(actions) + 1) // 2) * 44)
    panel_y = card_y + 120
    height = panel_y + panel_height + 34
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 {height}" width="100%" role="img" aria-label="{title}">
<defs><filter id="shadow" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="5" stdDeviation="7" flood-color="{c['primary']}" flood-opacity=".14"/></filter><linearGradient id="banner"><stop stop-color="{c['primary']}"/><stop offset="1" stop-color="{c['secondary']}"/></linearGradient><linearGradient id="accentWash" x2="1" y2="1"><stop stop-color="{c['accent']}" stop-opacity=".18"/><stop offset="1" stop-color="{c['highlight']}" stop-opacity=".04"/></linearGradient></defs><style>text{{font-family:'Segoe UI',Inter,Arial,sans-serif;line-height:1.45}}</style>
<rect width="100%" height="100%" rx="22" fill="{c['background']}"/><rect width="1000" height="158" rx="22" fill="url(#banner)"/><path d="M0 138 Q500 176 1000 132 V158 Q1000 176 980 176 H20 Q0 176 0 158Z" fill="{c['accent']}"/>
{svg_icon(design['icon'], 40, 35, '#FFFFFF', 32)}<text x="88" y="58" fill="#fff" font-family="Arial" font-size="13" font-weight="700" letter-spacing="2">{escape(design['topic'].upper())} / {layout.replace('_',' ').upper()}</text>
<text x="40" y="108" fill="#fff" font-family="Arial" font-size="{max(16,min(32,int(920/max(1,len(title)*.56))))}" font-weight="700">{title[:100]}</text><rect x="800" y="36" width="155" height="39" rx="19" fill="{design['severity_color']}"/><text x="877" y="61" text-anchor="middle" fill="#fff" font-family="Arial" font-size="14" font-weight="700">{severity}</text>''']
    x = 40
    for badge in badges:
        label = escape(str(badge)[:34]); chip_width = min(230, max(110, len(label) * 8 + 32))
        if x + chip_width > 965: break
        parts.append(f'<rect x="{x}" y="178" width="{chip_width}" height="30" rx="15" fill="{c["surface"]}" stroke="{c["highlight"]}"/><text x="{x+14}" y="198" fill="{c["ink"]}" font-family="Arial" font-size="12">{label}</text>')
        x += chip_width + 10
    parts.append(f'<text x="40" y="{summary_y}" fill="{c["muted"]}" font-family="Arial" font-size="13" font-weight="700">BRIEF</text>')
    for i, line in enumerate(summary_lines):
        parts.append(f'<text x="40" y="{summary_y+25+i*22}" fill="{c["ink"]}" font-family="Arial" font-size="15">{escape(line)}</text>')
    values = [("SEVERITY", severity), ("AFFECTED SYSTEMS", ", ".join(map(str, systems)) or "See source details"), ("INDICATORS", ", ".join(map(str, cves+ips)) or "None listed")]
    for i, (label, value) in enumerate(values):
        x = 40 + i*312
        parts.append(f'<rect x="{x}" y="{card_y}" width="296" height="100" rx="14" fill="{c["surface"]}" stroke="{c["border"]}" stroke-width="1" filter="url(#shadow)"/><rect x="{x}" y="{card_y}" width="5" height="100" rx="2" fill="{design["severity_color"] if i == 0 else c["highlight"]}"/><rect x="{x+1}" y="{card_y+1}" width="294" height="98" rx="13" fill="url(#accentWash)" opacity=".45"/><text x="{x+24}" y="{card_y+26}" fill="{c["muted"]}" font-family="Arial" font-size="11" font-weight="700">{label}</text>')
        icon_name = "alert" if i == 0 else "server" if i == 1 else "lock"
        parts.append(svg_icon(icon_name, x+256, card_y+12, design["severity_color"] if i == 0 else c["highlight"], 22))
        for j, line in enumerate(wrap(str(value), 34)[:3]):
            parts.append(f'<text x="{x+24}" y="{card_y+52+j*17}" fill="{c["ink"]}" font-family="Arial" font-size="14">{escape(line)}</text>')
    parts.append(f'<rect x="40" y="{panel_y}" width="920" height="{panel_height}" rx="16" fill="{c["surface"]}" stroke="{c["border"]}" stroke-width="1" filter="url(#shadow)"/><text x="86" y="{panel_y+35}" fill="{c["primary"]}" font-family="Arial" font-size="17" font-weight="700">RECOMMENDED RESPONSE</text><rect x="62" y="{panel_y+53}" width="876" height="2" fill="{c["border"]}"/><rect x="62" y="{panel_y+53}" width="136" height="3" rx="2" fill="{c["accent"]}"/>')
    parts.append(svg_icon("check", 62, panel_y+17, c["success"], 22))
    if layout == "process_flow":
        for i, (_, lines) in enumerate(action_lines):
            row, col = divmod(i, 3); x, y = 62+col*290, panel_y+66+row*112
            parts.append(f'<rect x="{x}" y="{y}" width="260" height="88" rx="12" fill="{c["background"]}" stroke="{c["highlight"]}"/><circle cx="{x+25}" cy="{y+25}" r="15" fill="{c["primary"]}"/><text x="{x+25}" y="{y+30}" text-anchor="middle" fill="#fff" font-family="Arial" font-size="13">{i+1}</text>')
            for j, line in enumerate(lines[:3]): parts.append(f'<text x="{x+50}" y="{y+29+j*17}" fill="{c["ink"]}" font-family="Arial" font-size="12">{escape(line)}</text>')
    elif layout == "timeline":
        parts.append(f'<path d="M84 {panel_y+73}v{max(40,len(actions)*66)}" stroke="{c["highlight"]}" stroke-width="4"/>')
        for i, (_, lines) in enumerate(action_lines):
            y=panel_y+78+i*66; parts.append(f'<circle cx="84" cy="{y-5}" r="10" fill="{c["accent"]}"/><text x="112" y="{y}" fill="{c["ink"]}" font-family="Arial" font-size="13">{i+1:02d}  {escape(" ".join(lines)[:105])}</text>')
    elif layout == "split_comparison":
        split=max(1,(len(actions)+1)//2)
        for col, heading, items in ((0,"ASSESSMENT",action_lines[:split]),(1,"RESPONSE",action_lines[split:] or action_lines[:1])):
            x=62+col*440; parts.append(f'<rect x="{x}" y="{panel_y+65}" width="418" height="{panel_height-82}" rx="12" fill="{c["background"]}"/><text x="{x+18}" y="{panel_y+92}" fill="{c["secondary"]}" font-family="Arial" font-size="12" font-weight="700">{heading}</text>')
            for i, (_, lines) in enumerate(items): parts.append(f'<text x="{x+20}" y="{panel_y+122+i*35}" fill="{c["ink"]}" font-family="Arial" font-size="12">• {escape(" ".join(lines)[:72])}</text>')
    else:
        cols=2 if len(actions)>2 else 1; box_width=(876-(cols-1)*14)//cols
        for i, (_, lines) in enumerate(action_lines):
            row,col=divmod(i,cols); x,y=62+col*(box_width+14),panel_y+64+row*44
            parts.append(f'<rect x="{x}" y="{y}" width="{box_width}" height="34" rx="9" fill="{c["background"]}"/><circle cx="{x+17}" cy="{y+17}" r="6" fill="{c["accent"]}"/><text x="{x+32}" y="{y+22}" fill="{c["ink"]}" font-family="Arial" font-size="12">{escape(" ".join(lines)[:100])}</text>')
    parts.append('</svg>')
    svg_path = os.path.join(OUTPUT_DIR, "infographic_blueprint.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    return svg_path
