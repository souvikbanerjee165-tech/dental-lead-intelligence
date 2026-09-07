"""
AI ROI Calculator & Tailored Proposal Customizer.
Transforms audit evidence and practice metrics into dentist-specific unit economics
and client-ready 1-click sales proposals.
"""

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
                "Everything in Tier 1 (24/7 AI Receptionist)",
                "Full Practice EHR/PMS calendar integration (Dentrix, Curve, Eaglesoft)",
                "Two-way patient conversational booking over Web & SMS",
                "Automated appointment reminder & reschedule sequences",
                "Dedicated conversion analytics & weekly ROI review"
            ],
            projected_monthly_patients_recaptured=int((scored_lead.estimated_missed_calls_monthly_min or 8) * 1.8),
            projected_annual_recapture=float(annual_loss * 0.75)
        )

        p3 = ProposalPackage(
            tier=3,
            name="Practice Growth Engine",
            tagline="End-to-end patient acquisition, after-hours recapture, and reputation defense",
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


# --- AI ROI Calculator & Customizer (Phase 1 Revenue OS) ---

def calculate_practice_roi(
    lead_data: Dict[str, Any],
    recovered_patients_per_month: int = 5,
    avg_case_value: int = 900,
    monthly_fee: int = 299
) -> Dict[str, Any]:
    """
    Computes precise dental practice unit economics and annual ROI multiplier.
    """
    recovered_patients = max(1, int(recovered_patients_per_month))
    case_val = max(100, int(avg_case_value))
    fee = max(50, int(monthly_fee))

    monthly_revenue = recovered_patients * case_val
    annual_revenue = monthly_revenue * 12

    monthly_cost = fee
    annual_cost = monthly_cost * 12

    net_annual_profit = annual_revenue - annual_cost
    roi_multiple = round(annual_revenue / annual_cost, 1) if annual_cost > 0 else 10.0

    daily_cost = round(annual_cost / 365, 2)

    return {
        "recovered_patients_per_month": recovered_patients,
        "avg_case_value": case_val,
        "monthly_fee": fee,
        "monthly_revenue_recovered": monthly_revenue,
        "annual_revenue_recovered": annual_revenue,
        "annual_cost": annual_cost,
        "net_annual_profit": net_annual_profit,
        "roi_multiplier": roi_multiple,
        "daily_cost": daily_cost,
        "breakeven_summary": f"Recovering just 1 patient every {max(1, round(case_val / fee))} months completely pays for your investment.",
        "headline_roi": f"{roi_multiple}x Projected Return on Investment"
    }


def generate_tailored_proposal(
    lead: Dict[str, Any],
    custom_roi: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generates a structured, client-facing sales proposal tailored to a specific dental clinic.
    """
    practice_name = lead.get("name", "Dental Practice")
    doctor_name = lead.get("doctor_name") or "Practice Owner & Lead Clinician"
    phone = lead.get("phone", "Primary Line")
    address = lead.get("address", "Local Practice")
    website = lead.get("website", "")
    rating = float(lead.get("rating") or 4.8)
    review_count = int(lead.get("review_count") or 35)

    roi = custom_roi or calculate_practice_roi(lead)

    now_formatted = datetime.now().strftime("%B %d, %Y")

    # Diagnosed friction points
    friction_points = []
    missed_max = int(lead.get("missed_rev_max") or 4500)
    if missed_max > 0:
        friction_points.append({
            "issue": "Uncaptured After-Hours Patient Demand",
            "impact": f"Patients inquiring between 5 PM and 8 AM receive voicemail or abandoned contact forms, risking ${int(lead.get('missed_rev_min', 2000)):,}-${missed_max:,}/mo in unbooked chairs.",
            "solution": "24/7 AI Receptionist responds instantly in 4 seconds over Web & SMS to secure bookings."
        })
    else:
        friction_points.append({
            "issue": "Missed Call Latency During Chair Hours",
            "impact": "When front-desk is checking in patients or sterilizing equipment, phone calls roll to voicemail where 67% never leave a message.",
            "solution": "Instant Missed-Call Auto-Textback with a 1-click booking link before the patient dials a competitor."
        })

    friction_points.append({
        "issue": "Mobile Friction on Website",
        "impact": "Prospective patients browsing on mobile phones abandon complex forms or multi-step booking portals.",
        "solution": "1-click conversational chat intake natively on WhatsApp and Mobile Web."
    })

    friction_points.append({
        "issue": "Review Velocity Gap",
        "impact": f"Currently at {review_count} reviews ({rating}★). Local competitors actively capture 5-8 new 5-star reviews monthly.",
        "solution": "Automated post-appointment review booster via SMS to dominate local Google Maps search rank."
    })

    # Implementation roadmap
    clean_doc = doctor_name.replace("Dr. ", "")
    roadmap = [
        {
            "phase": "Phase 1: Setup & Practice Onboarding",
            "days": "Days 1 – 3",
            "description": "Zero staff disruption. We map your clinic operating hours, service menu (implants, clear aligners, hygiene), and configure calendar sync."
        },
        {
            "phase": "Phase 2: Private Sandbox Review",
            "days": "Days 4 – 7",
            "description": f"Dr. {clean_doc} and the office manager test-drive the AI receptionist to verify conversational tone and clinical accuracy."
        },
        {
            "phase": "Phase 3: Live Patient Capture & Review Booster",
            "days": "Day 8 Onward",
            "description": "System goes live. After-hours visitors, weekend inquiries, and missed calls are automatically captured and booked directly into open chair slots."
        }
    ]

    pricing_options = [
        {
            "name": "Intake Essentials",
            "price": 299,
            "billing": "per month",
            "features": [
                "24/7 Website AI Chat Receptionist",
                "Instant Missed-Call Auto-Textback",
                "Direct Calendar / Appointment Sync",
                "After-Hours Patient Triage",
                "Weekly Performance Digest"
            ],
            "recommended": False
        },
        {
            "name": "Growth Acceleration (Recommended)",
            "price": 497,
            "billing": "per month",
            "features": [
                "Everything in Essentials",
                "Omnichannel WhatsApp & SMS Patient Intake",
                "High-Value Treatment Qualification (Implants/Invisalign)",
                "Automated 5-Star Google Review Booster",
                "VIP Priority Support & Monthly Optimization Call",
                "100% Done-For-You Practice Customization"
            ],
            "recommended": True
        }
    ]

    return {
        "lead_id": lead.get("id"),
        "practice_name": practice_name,
        "doctor_name": doctor_name,
        "address": address,
        "phone": phone,
        "website": website,
        "date_prepared": now_formatted,
        "screenshot_url": lead.get("screenshot_path") or "/static/img/dental-mockup.png",
        "hero_title": f"Patient Intake & Revenue Optimization Proposal for {practice_name}",
        "executive_summary": f"A targeted action plan for Dr. {clean_doc} to eliminate front-desk phone friction, capture after-hours patient inquiries, and generate an estimated ${roi['annual_revenue_recovered']:,}/year in net new chair production.",
        "roi_breakdown": roi,
        "diagnosed_friction": friction_points,
        "implementation_roadmap": roadmap,
        "pricing_options": pricing_options,
        "guarantee": "30-Day Zero-Risk Guarantee: If this system does not deliver at least 3 newly scheduled patient appointments in your first 30 days, you receive a complete 100% refund. We assume all the risk."
    }
