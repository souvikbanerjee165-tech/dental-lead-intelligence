"""
Executive PDF Sales Dossier & Clinic Teardown Generator.
Adapted from ai-sales-team-claude generate_pdf_report.py (MIT License) using ReportLab.

Generates professional, multi-page vector PDF Opportunity Teardowns without
requiring a headless browser, Playwright, or external dependencies:
- Executive Summary & Clinic Teardown
- BANT (0-100) and MEDDIC (0-100%) Qualification Breakdown
- Financial Leakage & Chair-Time Loss Model
- Operational Bottlenecks & Missing After-Hours Technology
- Tailored 30-Day Recovery Roadmap for Owner Dentist
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.graphics.shapes import Drawing, Circle, String, Line, Rect
from reportlab.graphics.charts.barcharts import HorizontalBarChart

from config import OUTPUT_DIR
from bant_meddic_scorer import DentalBANTMEDDICScorer

REPORTS_DIR = OUTPUT_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True, parents=True)

# Color Palette: Modern Dark / Navy Enterprise Aesthetic
NAVY = colors.HexColor("#0f172a")
SLATE = colors.HexColor("#334155")
CYAN = colors.HexColor("#06b6d4")
EMERALD = colors.HexColor("#10b981")
ROSE = colors.HexColor("#f43f5e")
AMBER = colors.HexColor("#f59e0b")
LIGHT_BG = colors.HexColor("#f8fafc")
CARD_BG = colors.HexColor("#f1f5f9")
LINE_COLOR = colors.HexColor("#cbd5e1")


class ExecutivePDFReporter:
    """Generates standalone publication-grade PDF dossiers using ReportLab."""

    @classmethod
    def generate_lead_dossier(
        cls,
        lead: Dict[str, Any],
        audit: Optional[Dict[str, Any]] = None,
        output_filename: Optional[str] = None
    ) -> str:
        """
        Builds a comprehensive 2-page PDF Executive Teardown for a dental clinic.
        Returns the absolute filepath to the created PDF.
        """
        audit_data = audit or lead.get("audit_data") or {}
        eval_data = DentalBANTMEDDICScorer.evaluate_lead(lead, audit_data)
        bant = eval_data["bant"]
        meddic = eval_data["meddic"]

        lead_id = lead.get("id") or "lead_unknown"
        clinic_name = lead.get("name") or "Dental Practice"
        doctor_name = lead.get("doctor_name") or "Practice Owner"
        city = lead.get("city") or lead.get("metro") or "Local Metro"
        phone = lead.get("phone") or "Direct Line"
        website = lead.get("website") or "Direct Site"
        monthly_leak = float(lead.get("monthly_leakage") or lead.get("missed_rev_max") or 4200)
        annual_leak = monthly_leak * 12

        fn = output_filename or f"dossier_{lead_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
        file_path = REPORTS_DIR / fn

        doc = SimpleDocTemplate(
            str(file_path),
            pagesize=letter,
            rightMargin=0.5 * inch,
            leftMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch
        )

        styles = getSampleStyleSheet()

        # Custom typography styles
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=NAVY
        )
        subtitle_style = ParagraphStyle(
            'DocSub',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=SLATE
        )
        section_style = ParagraphStyle(
            'SectionHead',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            textColor=NAVY
        )
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            textColor=SLATE
        )
        metric_style = ParagraphStyle(
            'Metric',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=20,
            textColor=NAVY,
            alignment=TA_CENTER
        )
        metric_label = ParagraphStyle(
            'MetricLabel',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            textColor=SLATE,
            alignment=TA_CENTER
        )

        story = []

        # ================= PAGE 1: HEADER & CLINIC PROFILE =================
        header_table = Table([
            [
                Paragraph(f"<b>CLINICAL REVENUE AUDIT &amp; TEARDOWN</b>", title_style),
                Paragraph(f"<b>CONFIDENTIAL</b><br/>{datetime.now().strftime('%b %d, %Y')}", ParagraphStyle('RightMeta', parent=body_style, alignment=TA_RIGHT))
            ],
            [
                Paragraph(f"Prepared for: <b>{clinic_name}</b> • {doctor_name} • {city}", subtitle_style),
                Paragraph(f"Status: <font color='#10b981'><b>{bant['rating']} PROSPECT</b></font>", ParagraphStyle('StatusPill', parent=body_style, alignment=TA_RIGHT))
            ]
        ], colWidths=[5.0 * inch, 2.5 * inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=CYAN, spaceAfter=12))

        # Executive Metrics Cards Table (4 columns)
        kpi_data = [
            [
                Paragraph(f"${monthly_leak:,.0f}/mo", metric_style),
                Paragraph(f"${annual_leak:,.0f}/yr", metric_style),
                Paragraph(f"{bant['total_score']}/100", metric_style),
                Paragraph(f"{meddic['overall_completeness_pct']}%", metric_style)
            ],
            [
                Paragraph("Trapped Monthly Leakage", metric_label),
                Paragraph("12-Month Financial Drain", metric_label),
                Paragraph("BANT Enterprise Fit", metric_label),
                Paragraph("MEDDIC Buying Readi.", metric_label)
            ]
        ]
        kpi_table = Table(kpi_data, colWidths=[1.875 * inch] * 4)
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), CARD_BG),
            ('BOX', (0,0), (-1,-1), 1, LINE_COLOR),
            ('INNERGRID', (0,0), (-1,-1), 0.5, LINE_COLOR),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 14))

        # ================= SECTION 1: BANT QUALIFICATION BREAKDOWN =================
        story.append(Paragraph("1. Enterprise BANT Qualification Breakdown", section_style))
        story.append(Spacer(1, 6))

        bant_dim = bant["dimensions"]
        bant_rows = [
            ["Dimension", "Score", "Rating", "Key Clinical & Operational Signals"]
        ]
        for key, name in [("budget", "Budget Capability"), ("authority", "Decision Authority"), ("need", "Operational Pain / Need"), ("timeline", "Timing & Urgency")]:
            d = bant_dim[key]
            signals_text = "<br/>• ".join(d["factors"][:2])
            bant_rows.append([
                Paragraph(f"<b>{name}</b>", body_style),
                Paragraph(f"<b>{d['score']} / 25</b>", body_style),
                Paragraph(f"<font color='{'#10b981' if d['rating']=='HIGH' else '#f59e0b'}'><b>{d['rating']}</b></font>", body_style),
                Paragraph(f"• {signals_text}", body_style)
            ])

        bant_table = Table(bant_rows, colWidths=[1.5 * inch, 0.8 * inch, 0.8 * inch, 4.4 * inch])
        bant_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), NAVY),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, LINE_COLOR),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG]),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(bant_table)
        story.append(Spacer(1, 14))

        # ================= SECTION 2: MEDDIC DEAL READINESS =================
        story.append(Paragraph("2. MEDDIC Governance & Committee Alignment", section_style))
        story.append(Spacer(1, 6))

        med_dim = meddic["dimensions"]
        meddic_rows = [
            ["MEDDIC Pillar", "Completion", "Diagnostic Assessment & Verification"]
        ]
        for key in ["metrics", "economic_buyer", "decision_criteria", "decision_process", "identify_pain", "champion"]:
            m = med_dim[key]
            meddic_rows.append([
                Paragraph(f"<b>{m['label']}</b>", body_style),
                Paragraph(f"<b>{m['pct']}%</b>", body_style),
                Paragraph(m["detail"], body_style)
            ])

        meddic_table = Table(meddic_rows, colWidths=[1.5 * inch, 0.9 * inch, 5.1 * inch])
        meddic_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), SLATE),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, LINE_COLOR),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG]),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(meddic_table)
        story.append(Spacer(1, 14))

        # ================= PAGE 2: FINANCIAL LEAKAGE & ACTION ROADMAP =================
        story.append(PageBreak())

        story.append(Paragraph("3. Trapped Monthly Patient Leakage Diagnostic", section_style))
        story.append(Spacer(1, 6))

        # Leakage Breakdown Table
        leak_rows = [
            ["Operational Vulnerability", "Monthly Lost Inquiries", "Average Patient Value", "Calculated Loss"],
            [
                Paragraph("<b>After-Hours & Sunday Pain Inquiries</b><br/><font size=7 color='#64748b'>Emergency calls going to voicemail while office is closed.</font>", body_style),
                "6 - 10 calls",
                "$850 - $1,400",
                f"${monthly_leak * 0.45:,.0f}/mo"
            ],
            [
                Paragraph("<b>High-Ticket Implant & Cosmetic Inquiries</b><br/><font size=7 color='#64748b'>High-intent callers hitting busy reception desk during clinic hours.</font>", body_style),
                "2 - 4 consults",
                "$3,500 - $6,000",
                f"${monthly_leak * 0.35:,.0f}/mo"
            ],
            [
                Paragraph("<b>Delayed Online Form & Review Drops</b><br/><font size=7 color='#64748b'>Prospects who bounce due to lack of immediate booking friction.</font>", body_style),
                "4 - 8 inquiries",
                "$450 - $700",
                f"${monthly_leak * 0.20:,.0f}/mo"
            ],
            [
                Paragraph("<b>TOTAL REVENUE RECOVERY POTENTIAL</b>", ParagraphStyle('BoldHead', parent=body_style, fontName='Helvetica-Bold')),
                "—",
                "—",
                Paragraph(f"<b>${monthly_leak:,.0f} / month</b>", ParagraphStyle('BoldVal', parent=body_style, fontName='Helvetica-Bold', textColor=colors.HexColor('#059669')))
            ]
        ]

        leak_table = Table(leak_rows, colWidths=[3.2 * inch, 1.4 * inch, 1.4 * inch, 1.5 * inch])
        leak_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), NAVY),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, LINE_COLOR),
            ('BACKGROUND', (0,-1), (-1,-1), CARD_BG),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(leak_table)
        story.append(Spacer(1, 14))

        # ================= SECTION 4: 3-STEP CONSULTATIVE ACTION ROADMAP =================
        story.append(Paragraph("4. Prescriptive 30-Day Growth & Recovery Roadmap", section_style))
        story.append(Spacer(1, 6))

        roadmap_rows = [
            [
                Paragraph("<b>Step 1: 24/7 AI Telephony Receptionist</b>", body_style),
                Paragraph("Route unanswered and after-hours clinic calls to autonomous neural voice engine that screens insurance, answers FAQs, and books appointments directly into PMS.", body_style)
            ],
            [
                Paragraph("<b>Step 2: Instant WhatsApp & SMS Recovery</b>", body_style),
                Paragraph("Deploy automated 60-second follow-up bridge for missed patient inquiries with direct interactive scheduling links to prevent callers contacting competitor clinics.", body_style)
            ],
            [
                Paragraph("<b>Step 3: Executive Pipeline Dashboard</b>", body_style),
                Paragraph("Provide Dr. Owner and Practice Manager real-time tracking of recaptured high-ticket dental implants, clear aligners, and hygiene bookings with full attribution.", body_style)
            ]
        ]
        roadmap_table = Table(roadmap_rows, colWidths=[2.2 * inch, 5.3 * inch])
        roadmap_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
            ('GRID', (0,0), (-1,-1), 0.5, LINE_COLOR),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(roadmap_table)
        story.append(Spacer(1, 20))

        # Bottom Call to Action Box
        cta_box = Table([
            [
                Paragraph(
                    f"<b>STRATEGIC RECOMMENDATION:</b> {eval_data['recommendation']}<br/>"
                    f"<font size=8 color='#475569'>Generated automatically by Enterprise Dental Intelligence OS • Verified PSTN Telephony & PMS Audit Engine.</font>",
                    body_style
                )
            ]
        ], colWidths=[7.5 * inch])
        cta_box.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), CARD_BG),
            ('BOX', (0,0), (-1,-1), 1.5, CYAN),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(cta_box)

        # Build document
        doc.build(story)
        return str(file_path)
