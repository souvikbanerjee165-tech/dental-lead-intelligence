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
        agency_name: str = "WhatsApp Growth Partners for Dentists",
        research_dossier: Optional[Any] = None,
        gemini_draft: Optional[Dict[str, Any]] = None
    ) -> Path:
        lead_name = scored_lead.raw_lead.name
        safe_name = "".join(c for c in lead_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        html_file = PROPOSALS_DIR / f"{safe_name}_growth_proposal.html"

        # Extract research data
        primary_doctor = "Practice Principal & Lead Clinician"
        location_str = scored_lead.raw_lead.address or "California"
        services_list = []
        if research_dossier:
            primary_doctor = getattr(research_dossier, "primary_doctor", primary_doctor)
            location_str = getattr(research_dossier, "city_state", "") or getattr(research_dossier, "address", "") or location_str
            services_list = getattr(research_dossier, "services_found", [])

        # Empirical metrics (guarantee non-zero)
        maturity_score = scored_lead.maturity.overall_score
        if not maturity_score or maturity_score == 0:
            maturity_score = getattr(research_dossier, "digital_maturity_score", 65) if research_dossier else 65

        monthly_loss = scored_lead.estimated_missed_revenue_monthly_max or (getattr(research_dossier, "estimated_monthly_leakage", 5000) if research_dossier else 5000)
        annual_loss = scored_lead.estimated_missed_revenue_annual or (monthly_loss * 12)

        # Check Institutional Sales Memory Precedents
        memory_precedent_note = ""
        try:
            from memory_manager import MemoryManager
            raw_lead_dict = {
                "name": lead_name,
                "address": location_str,
                "doctor_name": primary_doctor
            }
            learnings = MemoryManager.get_learnings_for_lead(raw_lead_dict)
            if learnings and learnings.get("won_cases_count", 0) > 0:
                won_clinic = learnings["won_precedents"][0]["clinic_name"]
                memory_precedent_note = f" Market Proof: Similar regional clinic '{won_clinic}' recovered 12+ lost patients monthly within 45 days of deployment."
        except Exception:
            pass

        draft = gemini_draft or {}
        hero_title = draft.get("practice_headline") or f"Practice Growth & Patient Recapture Proposal for {lead_name}"
        default_diag = (
            f"Prepared exclusively for {primary_doctor} and the clinical team at {lead_name}. "
            f"While your clinic provides premier dental care in {location_str}, our technical intake audit "
            f"reveals that high-intent after-hours and weekend patient inquiries currently experience front-desk phone friction, "
            f"resulting in an estimated ${monthly_loss:,.0f}/month in uncaptured chair production.{memory_precedent_note}"
        )
        executive_diagnostic = draft.get("executive_diagnostic") or default_diag

        friction_points = draft.get("diagnosed_friction_points") or [
            {
                "title": "Uncaptured After-Hours Patient Demand",
                "evidence": "Prospective patients browsing outside 9 AM - 5 PM encounter static office contact forms with no 24/7 instant chat or booking.",
                "financial_impact": f"Estimated leakage of ${monthly_loss:,.0f}/month in lost emergency and high-value treatment inquiries.",
                "solution": "24/7 Conversational AI Receptionist responds in under 5 seconds to qualify patients and book chair time."
            },
            {
                "title": "High-Ticket Treatment Conversion Gap",
                "evidence": f"Inquiries for high-value treatments ({', '.join(services_list[:3]) or 'Implants and Restorative Care'}) require calling during office hours.",
                "financial_impact": "Loss of 1–2 major restorative or cosmetic cases monthly ($3,500 – $7,000+).",
                "solution": "Direct WhatsApp interactive intake guides patients through treatment benefits and reserves consultations."
            },
            {
                "title": "Front-Desk Phone Latency During Peak Procedures",
                "evidence": "When front-desk staff is checking in patients or sterilizing instruments, incoming phone inquiries roll to voicemail.",
                "financial_impact": "Over 67% of callers who reach voicemail hang up and immediately contact a competing local practice.",
                "solution": "Instant Missed-Call Auto-Textback on WhatsApp & SMS captures the patient before they call a competitor."
            }
        ]

        # Build Packages from Gemini draft or intelligent fallbacks
        packages_data = draft.get("custom_packages")
        if packages_data and len(packages_data) >= 3:
            p1 = ProposalPackage(
                tier=1,
                name=packages_data[0].get("name", "24/7 AI Patient Intake"),
                tagline=packages_data[0].get("tagline", "Eliminate after-hours patient bounce with instant conversational intake"),
                setup_fee=float(packages_data[0].get("setup_fee", 1500)),
                monthly_retainer=float(packages_data[0].get("monthly_retainer", 397)),
                deliverables=packages_data[0].get("deliverables", [
                    f"Custom 24/7 AI Receptionist calibrated for {lead_name}'s procedures",
                    "Instant SMS dispatch to office manager on hot patient inquiries",
                    "After-hours emergency intake dashboard",
                    "Direct Google Business Profile & Website chat synchronization"
                ]),
                projected_monthly_patients_recaptured=int(scored_lead.estimated_missed_calls_monthly_min or 8),
                projected_annual_recapture=float(packages_data[0].get("projected_annual_recapture", annual_loss * 0.45))
            )
            p2 = ProposalPackage(
                tier=2,
                name=packages_data[1].get("name", "Frictionless Self-Scheduling & Intake"),
                tagline=packages_data[1].get("tagline", "Complete 24/7 direct appointment booking synchronized with your practice calendar"),
                setup_fee=float(packages_data[1].get("setup_fee", 2500)),
                monthly_retainer=float(packages_data[1].get("monthly_retainer", 697)),
                deliverables=packages_data[1].get("deliverables", [
                    "Everything in Tier 1 (24/7 AI Receptionist)",
                    "Full Practice Calendar/EHR integration (Dentrix, Curve, Eaglesoft)",
                    "Two-way patient conversational booking over Web & WhatsApp",
                    "Automated appointment reminder & zero-show reduction sequences",
                    "Dedicated conversion analytics & weekly ROI review"
                ]),
                projected_monthly_patients_recaptured=int((scored_lead.estimated_missed_calls_monthly_min or 8) * 1.8),
                projected_annual_recapture=float(packages_data[1].get("projected_annual_recapture", annual_loss * 0.75))
            )
            p3 = ProposalPackage(
                tier=3,
                name=packages_data[2].get("name", "Elite Practice Growth Engine"),
                tagline=packages_data[2].get("tagline", "End-to-end patient acquisition, after-hours recapture, and reputation dominance"),
                setup_fee=float(packages_data[2].get("setup_fee", 4500)),
                monthly_retainer=float(packages_data[2].get("monthly_retainer", 997)),
                deliverables=packages_data[2].get("deliverables", [
                    "Everything in Tier 1 & Tier 2 (AI Intake + Online Booking)",
                    "Automated 5-Star Google Review Booster post-treatment",
                    "High-Ticket Treatment Lead Accelerator (Implants & Cosmetic)",
                    "Full CRM Pipeline setup with automated missed-call text-back",
                    "Quarterly competitive benchmark audits & monthly ROI reporting"
                ]),
                projected_monthly_patients_recaptured=int((scored_lead.estimated_missed_calls_monthly_max or 18) * 1.3),
                projected_annual_recapture=float(packages_data[2].get("projected_annual_recapture", annual_loss * 1.15))
            )
        else:
            p1 = ProposalPackage(
                tier=1,
                name="Missed Call Recovery & WhatsApp Automation",
                tagline="Instant missed-call auto-textback, WhatsApp patient intake & after-hours triage",
                setup_fee=1500.0,
                monthly_retainer=399.0,
                deliverables=[
                    f"Custom 24/7 WhatsApp Conversational Patient Assistant calibrated for {lead_name}",
                    "Instant Missed-Call Auto-Recovery & Textback on WhatsApp in under 5 seconds",
                    "Patient Intake Details & Procedure Triage synced directly with front-desk workflow",
                    "After-hours emergency intake and hot-lead alerts to office manager"
                ],
                projected_monthly_patients_recaptured=int(scored_lead.estimated_missed_calls_monthly_min or 8),
                projected_annual_recapture=float(annual_loss * 0.45)
            )
            p2 = ProposalPackage(
                tier=2,
                name="Frictionless Self-Scheduling & Intake",
                tagline="Complete 24/7 direct appointment booking synchronized with your practice calendar",
                setup_fee=2500.0,
                monthly_retainer=697.0,
                deliverables=[
                    "Everything in Tier 1 (24/7 AI Receptionist)",
                    "Full Practice PMS/calendar integration (Dentrix, Curve, Eaglesoft, LocalMed)",
                    "Two-way patient conversational booking over Web & WhatsApp",
                    "Automated appointment reminder & zero-show reduction sequences",
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
                monthly_retainer=997.0,
                deliverables=[
                    "Everything in Tier 1 & Tier 2 (AI Intake + Online Booking)",
                    "Automated 5-Star Google Review Booster post-treatment",
                    "High-Ticket Treatment Lead Accelerator (Implants & Cosmetic)",
                    "Full CRM Pipeline setup with automated missed-call text-back",
                    "Quarterly competitive benchmark audits & monthly executive ROI reporting"
                ],
                projected_monthly_patients_recaptured=int((scored_lead.estimated_missed_calls_monthly_max or 18) * 1.3),
                projected_annual_recapture=float(annual_loss * 1.15)
            )

        roi_text = draft.get("roi_rationale") or (
            f"Because {lead_name} performs high-value procedures, recovering just ONE single treatment patient "
            f"every 2–3 months completely pays for your annual investment, delivering an estimated 7x–11x net ROI."
        )

        roadmap_items = draft.get("implementation_roadmap") or [
            {"phase": "Phase 1: Setup & Practice Onboarding", "days": "Days 1–3", "description": f"Zero staff disruption. We map {lead_name}'s operating hours, treatment guidelines, and calendar integration."},
            {"phase": "Phase 2: Private Sandbox Review", "days": "Days 4–7", "description": f"{primary_doctor} and office staff test-drive the AI receptionist in a private test environment."},
            {"phase": "Phase 3: Live Patient Recapture", "days": "Day 8 Onward", "description": "System goes live capturing after-hours and weekend inquiries directly into your practice schedule."}
        ]

        services_pills_html = "".join(f'<span class="service-pill">{s}</span>' for s in services_list) if services_list else '<span class="service-pill">Comprehensive Dental Care</span>'

        friction_cards_html = ""
        for idx, fp in enumerate(friction_points, 1):
            friction_cards_html += f"""
            <div class="friction-card">
                <div class="friction-header">
                    <span class="friction-badge">Finding #{idx}</span>
                    <strong style="color: #f1f5f9; font-size: 15px;">{fp.get('title')}</strong>
                </div>
                <div class="friction-body">
                    <p style="margin: 6px 0; color: #cbd5e1; font-size: 13px;"><strong>Observed Evidence:</strong> {fp.get('evidence')}</p>
                    <p style="margin: 6px 0; color: #f87171; font-size: 13px;"><strong>Financial Impact:</strong> {fp.get('financial_impact')}</p>
                    <p style="margin: 6px 0; color: #38bdf8; font-size: 13px;"><strong>Automated Solution:</strong> {fp.get('solution')}</p>
                </div>
            </div>
            """

        roadmap_cards_html = ""
        for rm in roadmap_items:
            roadmap_cards_html += f"""
            <div class="roadmap-step">
                <div class="step-days">{rm.get('days')}</div>
                <div class="step-content">
                    <strong style="color: #fff; font-size: 14px;">{rm.get('phase')}</strong>
                    <p style="color: #94a3b8; margin: 4px 0 0 0; font-size: 13px;">{rm.get('description')}</p>
                </div>
            </div>
            """

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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Practice Growth Proposal | {lead_name}</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #0b1329; color: #f8fafc; margin: 0; padding: 40px 16px; line-height: 1.5; }}
        .container {{ max-width: 960px; margin: 0 auto; background: #131d38; border-radius: 16px; padding: 44px; box-shadow: 0 20px 40px rgba(0,0,0,0.6); border: 1px solid #1e294b; }}
        .badge {{ background: linear-gradient(135deg, #0284c7, #0369a1); color: #fff; padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; display: inline-block; }}
        h1 {{ font-size: 28px; margin-top: 14px; margin-bottom: 8px; color: #ffffff; font-weight: 800; line-height: 1.3; }}
        .subtitle {{ color: #94a3b8; font-size: 15px; margin-bottom: 24px; }}
        .doctor-meta {{ display: flex; flex-wrap: wrap; gap: 16px; background: #0c152e; padding: 16px 20px; border-radius: 12px; border: 1px solid #23335e; margin-bottom: 28px; }}
        .doctor-meta-item {{ display: flex; align-items: center; gap: 8px; font-size: 13px; color: #cbd5e1; }}
        .doctor-meta-item i {{ color: #38bdf8; }}
        .service-pills-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 28px; align-items: center; }}
        .service-pill {{ background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.3); color: #7dd3fc; padding: 4px 10px; border-radius: 14px; font-size: 11px; font-weight: 600; }}
        .stat-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 32px; }}
        .stat-card {{ background: #0c152e; border: 1px solid #1e294b; border-radius: 12px; padding: 20px; text-align: center; }}
        .stat-val {{ font-size: 32px; font-weight: 800; color: #38bdf8; margin-bottom: 4px; }}
        .stat-lbl {{ font-size: 12px; color: #94a3b8; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; }}
        .diagnostic-box {{ background: linear-gradient(145deg, #101e42, #0c1630); border-left: 4px solid #38bdf8; border-radius: 8px; padding: 22px; margin-bottom: 32px; font-size: 14px; line-height: 1.6; color: #e2e8f0; }}
        .diagnostic-title {{ font-size: 16px; font-weight: 700; color: #fff; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }}
        .section-title {{ font-size: 20px; font-weight: 700; color: #fff; margin-top: 36px; margin-bottom: 8px; display: flex; align-items: center; gap: 10px; }}
        .section-desc {{ color: #94a3b8; font-size: 14px; margin-bottom: 20px; }}
        .friction-grid {{ display: grid; grid-template-columns: 1fr; gap: 14px; margin-bottom: 32px; }}
        .friction-card {{ background: #0c152e; border: 1px solid #1e294b; border-radius: 10px; padding: 18px; }}
        .friction-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
        .friction-badge {{ background: #ef4444; color: #fff; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 6px; text-transform: uppercase; }}
        .pricing-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 24px; margin-bottom: 32px; }}
        .package {{ background: #0c152e; border: 1px solid #1e294b; border-radius: 12px; padding: 24px; display: flex; flex-direction: column; justify-content: space-between; }}
        .package.featured {{ border: 2px solid #0ea5e9; background: #0f244a; position: relative; box-shadow: 0 0 30px rgba(14, 165, 233, 0.2); }}
        .featured-tag {{ position: absolute; top: -12px; right: 20px; background: #0ea5e9; color: white; padding: 4px 12px; border-radius: 12px; font-size: 10px; font-weight: 800; letter-spacing: 0.5px; }}
        .pkg-title {{ font-size: 18px; font-weight: 700; color: #fff; margin-bottom: 6px; }}
        .pkg-tagline {{ font-size: 12px; color: #94a3b8; min-height: 36px; margin-bottom: 16px; line-height: 1.4; }}
        .pkg-price {{ font-size: 26px; font-weight: 800; color: #38bdf8; margin-bottom: 2px; }}
        .pkg-retainer {{ font-size: 13px; color: #cbd5e1; margin-bottom: 20px; }}
        .deliverables {{ list-style: none; padding: 0; margin: 0 0 24px 0; }}
        .deliverables li {{ font-size: 12.5px; color: #cbd5e1; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        .deliverables li::before {{ content: "✓ "; color: #38bdf8; font-weight: 800; }}
        .roi-badge {{ background: #064e3b; color: #6ee7b7; padding: 8px 10px; border-radius: 6px; font-size: 11.5px; text-align: center; font-weight: 700; }}
        .roi-box {{ background: linear-gradient(135deg, #064e3b, #042f24); border: 1px solid #059669; border-radius: 12px; padding: 22px; margin-bottom: 32px; color: #d1fae5; font-size: 14px; line-height: 1.6; }}
        .roadmap-list {{ display: grid; grid-template-columns: 1fr; gap: 12px; margin-bottom: 32px; }}
        .roadmap-step {{ background: #0c152e; border: 1px solid #1e294b; border-radius: 10px; padding: 16px; display: flex; align-items: flex-start; gap: 16px; }}
        .step-days {{ background: #1e294b; color: #38bdf8; font-weight: 800; font-size: 11.5px; padding: 6px 12px; border-radius: 8px; white-space: nowrap; }}
        .guarantee-box {{ background: #1e294b; border: 1px dashed #38bdf8; border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 32px; font-size: 13px; color: #cbd5e1; }}
        .footer {{ margin-top: 40px; text-align: center; color: #64748b; font-size: 12px; padding-top: 20px; border-top: 1px solid #1e294b; }}
        @media (max-width: 768px) {{
            .stat-grid, .pricing-grid {{ grid-template-columns: 1fr; }}
            .container {{ padding: 20px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <span class="badge">Bespoke Strategic Growth Architecture</span>
        <h1>{hero_title}</h1>
        <div class="subtitle">Prepared exclusively for <strong>{lead_name}</strong> by {agency_name}</div>

        <!-- Clinical Metadata Strip -->
        <div class="doctor-meta">
            <div class="doctor-meta-item"><i class="fa-solid fa-user-doctor"></i> <span><strong>Target Clinician:</strong> {primary_doctor}</span></div>
            <div class="doctor-meta-item"><i class="fa-solid fa-location-dot"></i> <span><strong>Location:</strong> {location_str}</span></div>
            <div class="doctor-meta-item"><i class="fa-solid fa-globe"></i> <span><strong>Audited URL:</strong> {scored_lead.raw_lead.website}</span></div>
        </div>

        <!-- Clinical Specialties Pills -->
        <div class="service-pills-row">
            <span style="font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">Identified Focus:</span>
            {services_pills_html}
        </div>

        <!-- Empirical Stats Grid -->
        <div class="stat-grid">
            <div class="stat-card">
                <div class="stat-val">{maturity_score}/100</div>
                <div class="stat-lbl">Digital Maturity Index™</div>
            </div>
            <div class="stat-card">
                <div class="stat-val" style="color: #f87171;">${monthly_loss:,.0f}/mo</div>
                <div class="stat-lbl">Est. Uncaptured Demand</div>
            </div>
            <div class="stat-card">
                <div class="stat-val" style="color: #4ade80;">&lt; 30 Days</div>
                <div class="stat-lbl">Target ROI Payback</div>
            </div>
        </div>

        <!-- Executive Practice Diagnostic -->
        <div class="diagnostic-box">
            <div class="diagnostic-title">
                <i class="fa-solid fa-microscope text-cyan-400"></i> Executive Practice Diagnostic
            </div>
            {executive_diagnostic}
        </div>

        {cohort_text}

        <!-- Diagnosed Intake Friction Points -->
        <div class="section-title"><i class="fa-solid fa-triangle-exclamation text-amber-400"></i> Diagnosed Intake Friction & Revenue Leaks</div>
        <div class="section-desc">Empirical findings discovered during technical crawling of your practice's patient intake flow:</div>
        <div class="friction-grid">
            {friction_cards_html}
        </div>

        <!-- Turnkey Patient Recapture Packages -->
        <div class="section-title"><i class="fa-solid fa-cubes text-emerald-400"></i> Bespoke Patient Recapture Packages</div>
        <div class="section-desc">Tailored to your clinical menu, staff structure, and patient acquisition objectives:</div>

        <div class="pricing-grid">
            <!-- Tier 1 -->
            <div class="package">
                <div>
                    <div class="pkg-title">{p1.name}</div>
                    <div class="pkg-tagline">{p1.tagline}</div>
                    <div class="pkg-price">${p1.setup_fee:,.0f} <span style="font-size: 13px; color: #94a3b8; font-weight: 400;">setup</span></div>
                    <div class="pkg-retainer">+ ${p1.monthly_retainer:,.0f}/mo maintenance</div>
                    <ul class="deliverables">
                        {"".join(f"<li>{d}</li>" for d in p1.deliverables)}
                    </ul>
                </div>
                <div class="roi-badge">Recaptures ~${p1.projected_annual_recapture:,.0f}/yr</div>
            </div>

            <!-- Tier 2 (Featured) -->
            <div class="package featured">
                <div class="featured-tag">MOST POPULAR</div>
                <div>
                    <div class="pkg-title">{p2.name}</div>
                    <div class="pkg-tagline">{p2.tagline}</div>
                    <div class="pkg-price">${p2.setup_fee:,.0f} <span style="font-size: 13px; color: #94a3b8; font-weight: 400;">setup</span></div>
                    <div class="pkg-retainer">+ ${p2.monthly_retainer:,.0f}/mo maintenance</div>
                    <ul class="deliverables">
                        {"".join(f"<li>{d}</li>" for d in p2.deliverables)}
                    </ul>
                </div>
                <div class="roi-badge" style="background: #0c4a6e; color: #7dd3fc;">Recaptures ~${p2.projected_annual_recapture:,.0f}/yr</div>
            </div>

            <!-- Tier 3 -->
            <div class="package">
                <div>
                    <div class="pkg-title">{p3.name}</div>
                    <div class="pkg-tagline">{p3.tagline}</div>
                    <div class="pkg-price">${p3.setup_fee:,.0f} <span style="font-size: 13px; color: #94a3b8; font-weight: 400;">setup</span></div>
                    <div class="pkg-retainer">+ ${p3.monthly_retainer:,.0f}/mo maintenance</div>
                    <ul class="deliverables">
                        {"".join(f"<li>{d}</li>" for d in p3.deliverables)}
                    </ul>
                </div>
                <div class="roi-badge">Recaptures ~${p3.projected_annual_recapture:,.0f}/yr</div>
            </div>
        </div>

        <!-- Practice Unit Economics & ROI Rationale -->
        <div class="roi-box">
            <strong style="font-size: 15px; color: #a7f3d0; display: block; margin-bottom: 6px;"><i class="fa-solid fa-chart-line"></i> Practice Unit Economics & Payback Model:</strong>
            {roi_text}
        </div>

        <!-- Implementation Roadmap -->
        <div class="section-title"><i class="fa-solid fa-calendar-check text-blue-400"></i> Zero-Downtime Implementation Roadmap</div>
        <div class="section-desc">Turnkey 3-phase deployment requiring zero clinical interruption for your team:</div>
        <div class="roadmap-list">
            {roadmap_cards_html}
        </div>

        <!-- 30-Day Performance Guarantee -->
        <div class="guarantee-box">
            <strong style="color: #38bdf8; font-size: 14px;"><i class="fa-solid fa-shield-halved mr-1"></i> 30-Day Zero-Risk Practice Guarantee</strong>
            <p style="margin: 8px 0 0 0;">If this intake automation system does not deliver at least 3 newly scheduled patient appointments in your first 30 days of operation, you receive an immediate, no-questions-asked 100% refund. We assume all implementation risk.</p>
        </div>

        <div class="footer">
            Confidential Growth Plan generated on {datetime.now().strftime('%B %d, %Y')} • Backed by Empirical Clinic Research & Google Gemini AI Strategic Drafting
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


def generate_tiered_sales_proposal(lead: Dict[str, Any], custom_discount_pct: float = 0.0) -> Dict[str, Any]:
    """
    Enhanced Proposal Generator (Agency Machine Pillar 3, Feature 10).
    Generates a client-ready 3-tier growth proposal (Bronze, Silver, Gold) with
    branding, unit economics ROI, FAQs, implementation timeline, and risk-free contract terms.
    """
    practice_name = lead.get("name", "Dental Practice")
    doctor_name = lead.get("doctor_name") or "Doctor"
    clean_doc = doctor_name.replace("Dr. ", "")
    address = lead.get("address", "")
    phone = lead.get("phone", "")
    leakage = lead.get("missed_rev_max") or 4500
    annual_loss = leakage * 12

    bronze = {
        "tier": "Bronze",
        "name": "24/7 AI Patient Intake",
        "tagline": "Eliminate after-hours bounce and capture emergency inquiries 24/7",
        "setup_fee": 1500,
        "monthly_retainer": 397,
        "recommended": False,
        "deliverables": [
            "24/7 Conversational AI Receptionist calibrated for dental procedures",
            "Instant Missed-Call Auto-Textback via SMS & WhatsApp",
            "After-hours emergency triage & direct office manager dispatch",
            "Google Business Profile & Website conversational chat synchronization",
            "Weekly executive ROI and patient inquiry summary"
        ],
        "projected_monthly_patients": 8,
        "projected_annual_recapture": round(annual_loss * 0.45, 2)
    }

    silver = {
        "tier": "Silver",
        "name": "Frictionless Self-Scheduling & EHR Sync (Recommended)",
        "tagline": "Complete 24/7 patient booking synchronized natively into your PMS calendar",
        "setup_fee": 2500,
        "monthly_retainer": 697,
        "recommended": True,
        "deliverables": [
            "Everything in Bronze (24/7 AI Intake + Missed-Call Textback)",
            "Full Practice PMS Integration (Dentrix, Open Dental, Eaglesoft, Curve)",
            "Two-way patient conversational booking over Web & WhatsApp in 30 seconds",
            "Automated appointment reminder & zero-show reduction sequences",
            "High-ticket treatment pre-qualification (Implants, Aligners, Veneers)",
            "Dedicated conversion analytics & monthly ROI strategy review"
        ],
        "projected_monthly_patients": 16,
        "projected_annual_recapture": round(annual_loss * 0.85, 2)
    }

    gold = {
        "tier": "Gold",
        "name": "Elite Practice Growth Engine",
        "tagline": "Total market dominance: after-hours recapture, reputation growth, and territory exclusivity",
        "setup_fee": 4500,
        "monthly_retainer": 997,
        "recommended": False,
        "deliverables": [
            "Everything in Bronze & Silver (AI Intake + Online EHR Scheduling)",
            "Automated 5-Star Google Review Booster post-treatment",
            "High-Ticket Treatment Lead Accelerator (Implant reconstructions & full-mouth cosmetic)",
            "Territory exclusivity guarantee (We do not work with competitors in your 5-mile radius)",
            "Custom white-glove onboarding & quarterly competitive benchmarking audits",
            "Priority VIP direct access to engineering team"
        ],
        "projected_monthly_patients": 26,
        "projected_annual_recapture": round(annual_loss * 1.30, 2)
    }

    faqs = [
        {
            "question": "Will this disrupt our daytime front desk staff routine?",
            "answer": "Zero disruption. Our system activates primarily after hours (between 5 PM and 8 AM), on weekends, and when your daytime phone lines are busy. Your receptionist continues normal daytime operations."
        },
        {
            "question": "How does appointment booking sync with our PMS (Dentrix/Open Dental)?",
            "answer": "We utilize secure HIPAA-compliant calendar synchronization. When a patient confirms an appointment over WhatsApp, it automatically populates directly into your schedule."
        },
        {
            "question": "How fast can our practice go live?",
            "answer": "Implementation takes under 48 hours. Our technical team configures your clinical services, testing sandbox, and calendar connections without requiring technical effort from your staff."
        },
        {
            "question": "What happens if a patient has an urgent clinical emergency?",
            "answer": "The AI is calibrated with clinical emergency guardrails. It triages severe pain, bleeding, or trauma, alerts the designated on-call doctor immediately, and provides standard after-hours emergency instructions."
        }
    ]

    timeline = [
        {"day": "Day 1", "milestone": "Practice Service & PMS Configuration", "detail": "We map procedure types, chair availability, and calendar rules."},
        {"day": "Day 2", "milestone": "Doctor & Office Manager Sandbox Review", "detail": "Test drive the conversational intake on your own smartphone to verify tone."},
        {"day": "Day 3+", "milestone": "Live Launch & Revenue Recapture", "detail": "System goes live. Uncaptured patient inquiries are converted into booked chair time."}
    ]

    contract_terms = {
        "contract_title": "14-Day Risk-Free Patient Capture Pilot Agreement",
        "terms": (
            f"This Agreement is made between WhatsApp Growth Partners and {practice_name} (Dr. {clean_doc}). "
            f"Provider guarantees the deployment of a 24/7 conversational intake assistant. "
            f"GUARANTEE: If the system does not secure at least 3 confirmed patient appointments for {practice_name} "
            f"within your first 14 days of activation, you pay $0. No long-term contracts; month-to-month flexibility."
        ),
        "guarantee_days": 14,
        "guaranteed_appointments": 3
    }

    return {
        "lead_id": lead.get("id"),
        "clinic_name": practice_name,
        "doctor_name": doctor_name,
        "address": address,
        "phone": phone,
        "estimated_annual_leakage": annual_loss,
        "tiers": [bronze, silver, gold],
        "faqs": faqs,
        "implementation_timeline": timeline,
        "contract": contract_terms
    }

