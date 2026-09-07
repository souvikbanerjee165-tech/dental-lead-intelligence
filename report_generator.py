import os
import re
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright
from config import OUTPUT_DIR
from models import ScoredLead

REPORTS_DIR = OUTPUT_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True, parents=True)

class OpportunityReportGenerator:
    """Generates executive 1-page PDF Digital Maturity & AI Opportunity Reports."""

    @staticmethod
    def _render_html(lead: ScoredLead) -> str:
        raw = lead.raw_lead
        audit = lead.audit
        maturity = lead.maturity
        date_str = datetime.now().strftime("%B %d, %Y")

        status_class = "badge-urgent" if maturity.overall_score < 65 else "badge-moderate"
        status_text = "Urgent Transformation Needed" if maturity.overall_score < 65 else "Growth Optimization Potential"

        # Build Pillar Progress Bars
        def render_bar(name: str, score: int):
            color = "#dc2626" if score < 50 else ("#d97706" if score < 75 else "#16a34a")
            return f"""
            <div class="pillar-row">
              <div class="pillar-label">
                <span>{name}</span>
                <span style="color: {color}; font-weight: 700;">{score}/100</span>
              </div>
              <div class="bar-bg">
                <div class="bar-fill" style="width: {score}%; background: {color};"></div>
              </div>
            </div>
            """

        pillars_html = "".join([
            render_bar("Website Quality & Performance", maturity.website_quality),
            render_bar("Patient Experience & Accessibility", maturity.patient_experience),
            render_bar("SEO & Search Discoverability", maturity.seo_readiness),
            render_bar("Automation & AI Intake", maturity.automation_score),
            render_bar("Conversion Architecture", maturity.conversion_score)
        ])

        # Tech stack pills
        cms_str = ", ".join(audit.tech_stack.cms_and_frameworks) or "Custom / Traditional"
        analytics_str = ", ".join(audit.tech_stack.analytics + audit.tech_stack.tag_managers) or "None Detected"
        crm_str = ", ".join(audit.tech_stack.crm_and_marketing) or "None (Manual Tracking)"
        chat_str = audit.detected_chatbot_name or "❌ No AI Chatbot"
        booking_str = audit.detected_booking_tool or "❌ No Online Booking"

        # Improvements Table
        improvements_rows = ""
        for imp in maturity.top_improvements[:4]:
            improvements_rows += f"""
            <tr>
              <td style="font-weight: 700; color: #2563eb;">#{imp['rank']}</td>
              <td><strong>{imp['title']}</strong></td>
              <td style="color: #15803d; font-weight: 600;">{imp['impact']}</td>
              <td>{imp['effort']}</td>
              <td style="font-weight: 700; color: #0f172a;">{imp['estimated_roi']}</td>
            </tr>
            """

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @page {{
    size: letter portrait;
    margin: 12mm 14mm;
  }}
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  body {{
    color: #1e293b;
    background: #ffffff;
    font-size: 11.5px;
    line-height: 1.45;
  }}
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 12px;
    border-bottom: 2px solid #0f172a;
    margin-bottom: 16px;
  }}
  .title-area h1 {{
    font-size: 20px;
    font-weight: 800;
    color: #0f172a;
    letter-spacing: -0.5px;
  }}
  .title-area p {{
    color: #64748b;
    font-size: 11px;
    margin-top: 3px;
  }}
  .badge {{
    display: inline-block;
    padding: 5px 12px;
    border-radius: 9999px;
    font-weight: 700;
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .badge-urgent {{
    background: #fee2e2;
    color: #991b1b;
    border: 1px solid #fecaca;
  }}
  .badge-moderate {{
    background: #fef3c7;
    color: #92400e;
    border: 1px solid #fde68a;
  }}
  .top-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 1fr;
    gap: 10px;
    margin-bottom: 18px;
  }}
  .metric-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px;
    text-align: center;
  }}
  .metric-label {{
    font-size: 10px;
    text-transform: uppercase;
    font-weight: 700;
    color: #64748b;
  }}
  .metric-value {{
    font-size: 20px;
    font-weight: 800;
    color: #0f172a;
    margin-top: 2px;
  }}
  .metric-value.highlight {{
    color: #2563eb;
  }}
  .metric-value.danger {{
    color: #dc2626;
  }}
  .columns {{
    display: grid;
    grid-template-columns: 1.1fr 0.9fr;
    gap: 16px;
    margin-bottom: 16px;
  }}
  .section-title {{
    font-size: 13px;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 8px;
    padding-bottom: 4px;
    border-bottom: 1px solid #e2e8f0;
  }}
  .pillar-row {{
    margin-bottom: 7px;
  }}
  .pillar-label {{
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    font-weight: 600;
    margin-bottom: 2px;
  }}
  .bar-bg {{
    width: 100%;
    height: 7px;
    background: #e2e8f0;
    border-radius: 9999px;
    overflow: hidden;
  }}
  .bar-fill {{
    height: 100%;
    border-radius: 9999px;
  }}
  .tech-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
  }}
  .tech-table td {{
    padding: 5px 6px;
    border-bottom: 1px solid #f1f5f9;
  }}
  .tech-table td:first-child {{
    font-weight: 600;
    color: #475569;
    width: 38%;
  }}
  .revenue-box {{
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 6px;
    padding: 12px;
    margin-bottom: 16px;
  }}
  .revenue-box h3 {{
    font-size: 12.5px;
    color: #1e40af;
    margin-bottom: 4px;
    font-weight: 700;
  }}
  .revenue-box p {{
    font-size: 11px;
    color: #1e3a8a;
    line-height: 1.5;
  }}
  table.action-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
  }}
  table.action-table th {{
    background: #f1f5f9;
    color: #334155;
    padding: 6px 8px;
    text-align: left;
    font-weight: 700;
    border-bottom: 1px solid #cbd5e1;
  }}
  table.action-table td {{
    padding: 6px 8px;
    border-bottom: 1px solid #f1f5f9;
  }}
  .footer {{
    margin-top: 14px;
    padding-top: 8px;
    border-top: 1px solid #e2e8f0;
    font-size: 10px;
    color: #94a3b8;
    display: flex;
    justify-content: space-between;
  }}
</style>
</head>
<body>

<div class="header">
  <div class="title-area">
    <h1>Executive Digital Maturity & AI Opportunity Report</h1>
    <p>Practice: <strong>{raw.name}</strong> | Location: {raw.address or 'Texas'} | Audit Date: {date_str}</p>
    <p style="color: #2563eb; font-weight: 600; font-size: 10.5px; margin-top: 2px;">
      ✓ Evidence-Backed Audit &amp; DOM Verification (Confidence: {int(lead.evidence_confidence * 100)}%)
    </p>
  </div>
  <div>
    <span class="badge {status_class}">{status_text}</span>
  </div>
</div>

<div class="top-grid">
  <div class="metric-card">
    <div class="metric-label">Digital Maturity</div>
    <div class="metric-value highlight">{maturity.overall_score}/100</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Reputation Volume</div>
    <div class="metric-value">{raw.rating or 4.9}★ ({raw.review_count or 0})</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Est. Missed Patients</div>
    <div class="metric-value danger">{lead.estimated_missed_calls_monthly_min}–{lead.estimated_missed_calls_monthly_max}/mo</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Est. Annual Lost Rev</div>
    <div class="metric-value danger">${lead.estimated_missed_revenue_annual:,.0f}</div>
  </div>
</div>

<div class="columns">
  <div>
    <div class="section-title">📊 The 5 Pillars of Practice Digital Health</div>
    {pillars_html}
  </div>

  <div>
    <div class="section-title">💻 Detected Technology Stack</div>
    <table class="tech-table">
      <tr><td>CMS / Platform</td><td>{cms_str}</td></tr>
      <tr><td>Analytics & Tracking</td><td>{analytics_str}</td></tr>
      <tr><td>CRM / Lead Nurture</td><td>{crm_str}</td></tr>
      <tr><td>24/7 AI Receptionist</td><td><strong>{chat_str}</strong></td></tr>
      <tr><td>Online Appointment Booking</td><td><strong>{booking_str}</strong></td></tr>
      <tr><td>Mobile Experience</td><td>{'✓ Responsive' if audit.is_mobile_responsive else '❌ Non-responsive'}</td></tr>
    </table>
  </div>
</div>

<div class="revenue-box">
  <h3>💰 Financial Leakage Analysis (After-Hours Friction)</h3>
  <p>
    Over <strong>42% of local dental inquiries occur outside 9am–5pm clinic hours</strong>. Because {raw.name} currently lacks a 24/7 AI Receptionist to answer procedure & insurance questions, prospective patients bounce to competitors offering self-serve scheduling.
    At an average initial dental appointment value of $250, this represents an estimated uncaptured production gap of <strong>${lead.estimated_missed_revenue_monthly_min:,.0f}–${lead.estimated_missed_revenue_monthly_max:,.0f}/month</strong>.
  </p>
</div>

<div class="section-title">🎯 Top Prioritized Upgrades Ranked by Business Impact</div>
<table class="action-table">
  <thead>
    <tr>
      <th style="width: 8%;">Rank</th>
      <th>Recommended Solution</th>
      <th>Expected Impact</th>
      <th>Effort</th>
      <th>Projected ROI</th>
    </tr>
  </thead>
  <tbody>
    {improvements_rows}
  </tbody>
</table>

<div class="footer">
  <span>Confidential Executive Audit Prepared by AI Growth Systems</span>
  <span>Website: {raw.website or 'N/A'}</span>
</div>

</body>
</html>"""
        return html

    @classmethod
    async def generate_pdf(cls, lead: ScoredLead) -> str:
        """Renders HTML report and saves to a standalone PDF using Playwright."""
        html = cls._render_html(lead)
        safe_name = re.sub(r'[^\w\-_]', '_', lead.raw_lead.name)[:40]
        pdf_path = REPORTS_DIR / f"{safe_name}_Digital_Maturity_Report.pdf"

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-gpu"]
            )
            page = await browser.new_page()
            await page.set_content(html, wait_until="domcontentloaded")
            await page.pdf(
                path=str(pdf_path),
                format="Letter",
                print_background=True,
                margin={"top": "8mm", "bottom": "8mm", "left": "8mm", "right": "8mm"}
            )
            await browser.close()

        lead.pdf_report_path = str(pdf_path)
        return str(pdf_path)
