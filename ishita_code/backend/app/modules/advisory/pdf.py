import io
from datetime import datetime, timezone
from typing import Dict, Any, List
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether
)

class AdvisoryPdfGenerator:
    @staticmethod
    def generate_pdf(content: Dict[str, Any], metadata: Dict[str, Any]) -> bytes:
        """
        Generate a professional, enterprise-grade Cybersecurity Advisory PDF using ReportLab.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )

        styles = getSampleStyleSheet()
        
        # Custom palette
        c_navy = colors.HexColor("#0F172A")
        c_accent = colors.HexColor("#2563EB")
        c_gray_bg = colors.HexColor("#F8FAFC")
        c_line = colors.HexColor("#E2E8F0")
        c_text = colors.HexColor("#1E293B")
        c_muted = colors.HexColor("#64748B")

        # Severity color mapping
        sev = str(content.get("severity", "UNKNOWN")).upper()
        if "CRITICAL" in sev:
            c_sev = colors.HexColor("#DC2626")
        elif "HIGH" in sev:
            c_sev = colors.HexColor("#EA580C")
        elif "MEDIUM" in sev:
            c_sev = colors.HexColor("#D97706")
        else:
            c_sev = colors.HexColor("#16A34A")

        # Typography
        title_style = ParagraphStyle(
            "AdvTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=c_navy,
            fontName="Helvetica-Bold",
            spaceAfter=6
        )

        section_heading = ParagraphStyle(
            "AdvSection",
            parent=styles["Heading2"],
            fontSize=11,
            leading=14,
            textColor=c_accent,
            fontName="Helvetica-Bold",
            textTransform="uppercase",
            spaceBefore=12,
            spaceAfter=4
        )

        body_style = ParagraphStyle(
            "AdvBody",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=13.5,
            textColor=c_text,
            fontName="Helvetica",
            spaceAfter=6
        )

        mono_style = ParagraphStyle(
            "AdvMono",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#0F172A"),
            fontName="Courier",
            spaceAfter=3
        )

        story = []

        # Classification / Header Banner
        header_data = [
            [
                Paragraph("<b>SENTINEL CONTENT INTELLIGENCE // CYBERSECURITY ADVISORY</b>", ParagraphStyle("HdrL", fontSize=8, textColor=c_muted, fontName="Helvetica")),
                Paragraph(f"<b>STATUS: APPROVED</b> | TLP:CLEAR", ParagraphStyle("HdrR", fontSize=8, textColor=c_muted, fontName="Helvetica", alignment=2))
            ]
        ]
        hdr_table = Table(header_data, colWidths=[330, 202])
        hdr_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(hdr_table)
        story.append(HRFlowable(width="100%", thickness=1, color=c_line, spaceBefore=4, spaceAfter=10))

        # Title
        title_text = content.get("title", "Cybersecurity Advisory")
        story.append(Paragraph(title_text, title_style))

        # Meta grid
        cve_text = content.get("cve") or ", ".join(content.get("cve_ids", [])) or "N/A"
        cvss_text = str(content.get("cvss") or "N/A")
        prod_text = content.get("affectedProduct") or ", ".join(content.get("affected_products", [])) or "N/A"
        ver_text = content.get("affectedVersions") or ", ".join(content.get("affected_versions", [])) or "N/A"

        meta_table_data = [
            [
                Paragraph(f"<b>CVE ID:</b> {cve_text}", body_style),
                Paragraph(f"<b>SEVERITY:</b> <font color='{c_sev.hexval()}'><b>{sev}</b></font>", body_style)
            ],
            [
                Paragraph(f"<b>CVSS SCORE:</b> {cvss_text}", body_style),
                Paragraph(f"<b>VERSION RANGE:</b> {ver_text}", body_style)
            ],
            [
                Paragraph(f"<b>AFFECTED PRODUCT:</b> {prod_text}", body_style),
                Paragraph(f"<b>VERSION:</b> v{metadata.get('version', 1)}", body_style)
            ]
        ]
        meta_table = Table(meta_table_data, colWidths=[266, 266])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), c_gray_bg),
            ("BOX", (0, 0), (-1, -1), 1, c_line),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, c_line),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 10))

        # 1. Executive Summary
        story.append(Paragraph("1. Executive Summary", section_heading))
        story.append(Paragraph(content.get("summary", "No summary provided."), body_style))

        # 2. Technical Details
        story.append(Paragraph("2. Technical Details & Attack Vectors", section_heading))
        tech = content.get("technicalDetails") or content.get("technical_details", "No details provided.")
        story.append(Paragraph(tech, body_style))

        # 3. Impact Analysis
        if content.get("impact"):
            story.append(Paragraph("3. Impact Analysis", section_heading))
            story.append(Paragraph(content.get("impact"), body_style))

        # 4. Indicators of Compromise (IOCs)
        indicators = content.get("indicators", [])
        if indicators:
            story.append(Paragraph("4. Technical Indicators of Compromise (IOCs)", section_heading))
            ioc_rows = [
                [Paragraph("<b>Type / Format</b>", body_style), Paragraph("<b>Indicator Value</b>", body_style)]
            ]
            for ind in indicators:
                ind_str = str(ind).strip()
                ind_type = "IP / Telemetry" if "." in ind_str and not ind_str.startswith("http") else ("File Hash" if len(ind_str) in (32, 40, 64) else "URL / Domain")
                ioc_rows.append([
                    Paragraph(ind_type, body_style),
                    Paragraph(ind_str, mono_style)
                ])
            ioc_table = Table(ioc_rows, colWidths=[150, 382])
            ioc_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("BOX", (0, 0), (-1, -1), 0.5, c_line),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, c_line),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(ioc_table)
            story.append(Spacer(1, 6))

        # 5. Mitigation & Workarounds
        story.append(Paragraph("5. Mitigation & Defensive Measures", section_heading))
        story.append(Paragraph(content.get("mitigation", "No mitigation provided."), body_style))

        # 6. Recommendations
        recommendations = content.get("recommendations", [])
        if recommendations:
            story.append(Paragraph("6. Tactical & Strategic Recommendations", section_heading))
            for i, rec in enumerate(recommendations, 1):
                story.append(Paragraph(f"<b>{i}.</b> {rec}", body_style))

        # 7. References
        references = content.get("references", [])
        if references:
            story.append(Paragraph("7. Authoritative References", section_heading))
            for ref in references:
                story.append(Paragraph(f"• {ref}", ParagraphStyle("Ref", parent=body_style, fontName="Helvetica-Oblique", textColor=c_accent)))

        # Footer Stamp
        story.append(Spacer(1, 14))
        story.append(HRFlowable(width="100%", thickness=0.5, color=c_line, spaceBefore=4, spaceAfter=6))
        doc_hash = metadata.get("content_hash", "N/A")
        footer_text = f"Document Reference: {metadata.get('code', 'TR-ADVISORY')} | Version: v{metadata.get('version', 1)} | Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Integrity Hash (SHA-256): {doc_hash[:24]}..."
        story.append(Paragraph(footer_text, ParagraphStyle("Footer", fontSize=7, textColor=c_muted, fontName="Courier")))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
