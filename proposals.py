from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from config import OUTPUT_DIR

PROPOSALS_DIR = OUTPUT_DIR / "proposals"
PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

class ProposalPackage(BaseModel):
    tier: int
    name: str
    tagline: str
    setup_fee: float
    monthly_retainer: float
    deliverables: List[str]
    projected_monthly_patients_recaptured: int
    projected_annual_recapture: float

class ProposalGenerator:
    """Transforms audit findings, financial leakage, and competitor pressure into high-converting client proposals."""

    @classmethod
    def generate_proposal(
        cls,
        scored_lead: Any,
        cohort: Optional[Any] = None,
        agency_name: str = "Apex Practice Growth Partners"
    ) -> Path:
        lead_name = scored_lead.raw_lead.name
        safe_name = "".join(c for c in lead_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        html_file = PROPOSALS_DIR / f"{safe_name}_growth_proposal.html"

        monthly_loss = scored_lead.estimated_missed_revenue_monthly_max or 5000
        annual_loss = scored_lead.estimated_missed_revenue_annual or (monthly_loss * 12)

        # 3 Turnkey Packages
        p1 = ProposalPackage(
            tier=1,
            name="24/7 AI Patient Intake",
            tagline="Eliminate after-hours patient bounce with instant conversational qualification",
            setup_fee=1500.0,
            monthly_retainer=350.0,
            deliverables=[
                "Custom 24/7 Conversational AI Receptionist trained on clinic procedures & insurance",
                "Instant SMS notification to office manager on hot patient inquiries",
                "After-hours inquiry capture dashboard",
                "Direct Google Business Profile & Website chat synchronization"
            ],
            projected_monthly_patients_recaptured=int(scored_lead.estimated_missed_calls_monthly_min or 8),
            projected_annual_recapture=float(annual_loss * 0.45)
        )

        p2 = ProposalPackage(
            tier=2,
            name="Frictionless Self-Scheduling & Intake",
            tagline="Complete 24/7 direct appointment booking synchronized with your practice calendar",
            setup_fee=2500.0,
            monthly_retainer=650.0,
            deliverables=[
                "Everything in Tier 1 (24/7 Conversational AI Receptionist)",
                "Turnkey Online Booking Widget (NexHealth / LocalMed / custom PMS sync)",
                "Automated appointment confirmation & 2-way SMS reminder flow",
                "Mobile-first scheduling CTA integration across all web pages",
                "Zero telephone tag for new patient intake"
            ],
            projected_monthly_patients_recaptured=int(scored_lead.estimated_missed_calls_monthly_max or 18),
            projected_annual_recapture=float(annual_loss * 0.80)
        )

        p3 = ProposalPackage(
            tier=3,
            name="Complete Practice Growth Engine",
            tagline="Full automated intake, CRM pipeline, and competitor-beating patient acquisition",
            setup_fee=4500.0,
            monthly_retainer=950.0,
            deliverables=[
                "Everything in Tier 1 & Tier 2 (AI Intake + Online Booking)",
                "Automated Patient Recall & Reactivation sequence (SMS + Email)",
                "Full CRM Pipeline setup with automated missed-call text-back",
                "Local SEO & Meta Description conversion optimization",
                "Quarterly competitive benchmark audits & monthly ROI reporting"
            ],
            projected_monthly_patients_recaptured=int((scored_lead.estimated_missed_calls_monthly_max or 18) * 1.3),
            projected_annual_recapture=float(annual_loss * 1.15)
        )

        cohort_text = ""
        if cohort and hasattr(cohort, "booking_adoption_pct") and cohort.booking_adoption_pct > 0:
            cohort_text = f"""
            <div class="competitor-box">
                <strong>Hyper-Local Competitor Benchmark ({cohort.geo_query}):</strong><br>
                <span>{int(cohort.booking_adoption_pct)}% of competing dental practices in your area already offer 24/7 direct online scheduling. Continuing to rely exclusively on office telephone intake leaves after-hours searchers no option but to book with nearby peers.</span>
            </div>
            """

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Practice Growth Proposal | {lead_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 40px 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; background: #1e293b; border-radius: 12px; padding: 40px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
        .badge {{ background: #0284c7; color: #fff; padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; }}
        h1 {{ font-size: 32px; margin-top: 15px; color: #ffffff; }}
        .subtitle {{ color: #94a3b8; font-size: 18px; margin-bottom: 30px; }}
        .stat-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 35px; }}
        .stat-card {{ background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 20px; text-align: center; }}
        .stat-val {{ font-size: 28px; font-weight: bold; color: #38bdf8; margin-bottom: 5px; }}
        .stat-lbl {{ font-size: 13px; color: #94a3b8; text-transform: uppercase; }}
        .competitor-box {{ background: #451a03; border-left: 4px solid #f97316; padding: 18px; border-radius: 6px; margin-bottom: 35px; color: #fdba74; line-height: 1.5; }}
        .pricing-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 30px; }}
        .package {{ background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 25px; display: flex; flex-direction: column; justify-content: space-between; }}
        .package.featured {{ border: 2px solid #0ea5e9; background: #0b1e38; position: relative; }}
        .featured-tag {{ position: absolute; top: -12px; right: 20px; background: #0ea5e9; color: white; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; }}
        .pkg-title {{ font-size: 20px; font-weight: bold; color: #fff; margin-bottom: 8px; }}
        .pkg-tagline {{ font-size: 13px; color: #94a3b8; min-height: 40px; margin-bottom: 15px; }}
        .pkg-price {{ font-size: 24px; font-weight: bold; color: #38bdf8; margin-bottom: 5px; }}
        .pkg-retainer {{ font-size: 14px; color: #cbd5e1; margin-bottom: 20px; }}
        .deliverables {{ list-style: none; padding: 0; margin: 0 0 25px 0; }}
        .deliverables li {{ font-size: 13px; color: #cbd5e1; padding: 6px 0; border-bottom: 1px solid #1e293b; }}
        .deliverables li::before {{ content: "✓ "; color: #38bdf8; font-weight: bold; }}
        .roi-badge {{ background: #064e3b; color: #6ee7b7; padding: 8px; border-radius: 6px; font-size: 12px; text-align: center; font-weight: bold; }}
        .footer {{ margin-top: 40px; text-align: center; color: #64748b; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="container">
        <span class="badge">Strategic Growth Proposal</span>
        <h1>Practice Growth & Patient Recapture Proposal</h1>
        <div class="subtitle">Prepared exclusively for <strong>{lead_name}</strong> by {agency_name}</div>

        <div class="stat-grid">
            <div class="stat-card">
                <div class="stat-val">{scored_lead.maturity.overall_score}/100</div>
                <div class="stat-lbl">Digital Maturity Index™</div>
            </div>
            <div class="stat-card">
                <div class="stat-val" style="color: #f87171;">${monthly_loss:,.0f}/mo</div>
                <div class="stat-lbl">Est. Uncaptured Revenue</div>
            </div>
            <div class="stat-card">
                <div class="stat-val" style="color: #4ade80;">&lt; 30 Days</div>
                <div class="stat-lbl">Target ROI Payback</div>
            </div>
        </div>

        {cohort_text}

        <h2 style="color: #fff; margin-bottom: 10px;">Turnkey Patient Recapture Packages</h2>
        <p style="color: #94a3b8; margin-bottom: 25px;">Select the tier that aligns with your practice goals. All tiers include complete white-glove setup and performance tracking.</p>

        <div class="pricing-grid">
            <!-- Tier 1 -->
            <div class="package">
                <div>
                    <div class="pkg-title">{p1.name}</div>
                    <div class="pkg-tagline">{p1.tagline}</div>
                    <div class="pkg-price">${p1.setup_fee:,.0f} <span style="font-size: 13px; color: #94a3b8;">setup</span></div>
                    <div class="pkg-retainer">+ ${p1.monthly_retainer:,.0f}/mo maintenance</div>
                    <ul class="deliverables">
                        {"".join(f"<li>{d}</li>" for d in p1.deliverables)}
                    </ul>
                </div>
                <div class="roi-badge">Recaptures ~${p1.projected_annual_recapture:,.0f}/year</div>
            </div>

            <!-- Tier 2 (Featured) -->
            <div class="package featured">
                <div class="featured-tag">MOST POPULAR</div>
                <div>
                    <div class="pkg-title">{p2.name}</div>
                    <div class="pkg-tagline">{p2.tagline}</div>
                    <div class="pkg-price">${p2.setup_fee:,.0f} <span style="font-size: 13px; color: #94a3b8;">setup</span></div>
                    <div class="pkg-retainer">+ ${p2.monthly_retainer:,.0f}/mo maintenance</div>
                    <ul class="deliverables">
                        {"".join(f"<li>{d}</li>" for d in p2.deliverables)}
                    </ul>
                </div>
                <div class="roi-badge" style="background: #0c4a6e; color: #7dd3fc;">Recaptures ~${p2.projected_annual_recapture:,.0f}/year</div>
            </div>

            <!-- Tier 3 -->
            <div class="package">
                <div>
                    <div class="pkg-title">{p3.name}</div>
                    <div class="pkg-tagline">{p3.tagline}</div>
                    <div class="pkg-price">${p3.setup_fee:,.0f} <span style="font-size: 13px; color: #94a3b8;">setup</span></div>
                    <div class="pkg-retainer">+ ${p3.monthly_retainer:,.0f}/mo maintenance</div>
                    <ul class="deliverables">
                        {"".join(f"<li>{d}</li>" for d in p3.deliverables)}
                    </ul>
                </div>
                <div class="roi-badge">Recaptures ~${p3.projected_annual_recapture:,.0f}/year</div>
            </div>
        </div>

        <div class="footer">
            Confidential Growth Plan generated on {datetime.now().strftime('%B %d, %Y')} • Backed by Empirical Audit Provenance
        </div>
    </div>
</body>
</html>
        """

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return html_file
