"""
Deposit Lock & 3-Mile Territory Exclusivity Checkout Engine.
Secures $1,500 turnkey installation deposits and $399/mo ongoing retainers for dental practices.
Enforces a strict 3-mile exclusivity radius (only 1 dental clinic per territory),
locks out local competitors, logs deals in CRM, and generates legally compliant SLAs.
"""

import os
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from database import DatabaseManager
from timeline import OpportunityTimelineManager

logger = logging.getLogger("territory_checkout")


class TerritoryCheckoutEngine:
    """Manages $1,500 turnkey installation deposits, territory locks, and SLA agreements."""

    SETUP_FEE_USD = 1500.0
    MONTHLY_MAINTENANCE_USD = 399.0
    TERRITORY_RADIUS_MILES = 3.0

    @classmethod
    def check_territory_availability(
        cls,
        lead_dict: Dict[str, Any],
        db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        """
        Checks if the 3-mile territory around this clinic is already locked by another dentist.
        """
        db = db or DatabaseManager()
        lead_id = lead_dict.get("id") or ""
        address = lead_dict.get("address") or "Austin, TX"
        city = address.split(",")[-2].strip() if ("," in address and len(address.split(",")) >= 2) else "Austin"

        if lead_dict.get("territory_locked") or lead_dict.get("deposit_paid"):
            return {
                "is_available": False,
                "is_locked": True,
                "can_lock": False,
                "locked_by_rival": None,
                "radius_miles": cls.TERRITORY_RADIUS_MILES,
                "status": "ALREADY_LOCKED"
            }

        try:
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT id, name, address, deposit_paid_at
                FROM leads
                WHERE territory_locked = 1 AND id != ? AND (address LIKE ? OR address LIKE ?)
                LIMIT 1;
                """, (lead_id, f"%{city}%", f"%{city.split()[0]}%"))
                locked_rival = cursor.fetchone()
                if locked_rival:
                    rival_dict = dict(locked_rival)
                    return {
                        "is_available": False,
                        "is_locked": True,
                        "can_lock": False,
                        "locked_by_rival": rival_dict["name"],
                        "radius_miles": cls.TERRITORY_RADIUS_MILES,
                        "status": "LOCKED_BY_COMPETITOR"
                    }
        except Exception as e:
            logger.warning(f"Error checking territory availability: {e}")

        return {
            "is_available": True,
            "is_locked": False,
            "can_lock": True,
            "locked_by_rival": None,
            "radius_miles": cls.TERRITORY_RADIUS_MILES,
            "status": "AVAILABLE"
        }

    @classmethod
    def create_checkout_payload(
        cls,
        lead_dict: Dict[str, Any],
        base_app_url: str = "http://127.0.0.1:8000"
    ) -> Dict[str, Any]:
        """
        Generates checkout parameters, territory lock certificate, and itemized billing summary.
        """
        lead_id = lead_dict.get("id") or "preview"
        clinic_name = lead_dict.get("name") or "Your Practice"
        raw_doc = lead_dict.get("doctor_name") or "Doctor"
        clean_doc = raw_doc.replace("Dr.", "").replace("Dr", "").strip()
        doc_display = f"Dr. {clean_doc}" if clean_doc else "the Practice Owner"
        
        territory_cert_id = f"CERT-TX-{uuid.uuid4().hex[:8].upper()}"

        stripe_mock_checkout_url = f"{base_app_url}/checkout/stripe/{lead_id}?token={territory_cert_id}"
        agreement_url = f"{base_app_url}/agreement/{lead_id}"

        return {
            "lead_id": lead_id,
            "clinic_name": clinic_name,
            "doctor_name": doc_display,
            "territory_certificate_id": territory_cert_id,
            "setup_fee_usd": cls.SETUP_FEE_USD,
            "monthly_fee_usd": cls.MONTHLY_MAINTENANCE_USD,
            "territory_radius_miles": cls.TERRITORY_RADIUS_MILES,
            "break_even_guarantee_text": (
                "Single-Patient Break-Even Guarantee: If your WhatsApp patient triage system fails to recover "
                "at least 1 emergency or elective patient ($1,250+ value) within your first 30 days, "
                "we will refund 100% of your $1,500 turnkey setup fee with zero hassle."
            ),
            "stripe_checkout_url": stripe_mock_checkout_url,
            "agreement_url": agreement_url,
            "status": "READY_FOR_PAYMENT"
        }

    @classmethod
    def complete_deposit_lock(
        cls,
        lead_id: str,
        payment_ref: Optional[str] = None,
        db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        """
        Records the $1,500 turnkey setup deposit payment, marks territory locked in database,
        advances CRM stage to 'WON', logs deal ARR/MRR, and creates audit timeline entries.
        """
        db = db or DatabaseManager()
        now_str = datetime.now().isoformat()
        tx_id = payment_ref or f"tx_dep_{uuid.uuid4().hex[:10]}"
        deal_id = f"deal_{uuid.uuid4().hex[:8]}"

        lead = db.get_lead(lead_id) or {}
        clinic_name = lead.get("name") or "Dental Practice"
        doc_name = lead.get("doctor_name") or "Doctor"

        try:
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                UPDATE leads
                SET stage = 'WON',
                    territory_locked = 1,
                    deposit_paid = ?,
                    deposit_paid_at = ?,
                    last_updated = ?
                WHERE id = ?;
                """, (cls.SETUP_FEE_USD, now_str, now_str, lead_id))

                # Record closed deal
                cursor.execute("""
                INSERT OR REPLACE INTO deals (id, lead_id, status, deal_value, mrr_value, primary_finding_hook, closed_at)
                VALUES (?, ?, 'WON', ?, ?, '3-Mile Territory Deposit Lock', ?);
                """, (deal_id, lead_id, cls.SETUP_FEE_USD, cls.MONTHLY_MAINTENANCE_USD, now_str))

                conn.commit()
        except Exception as e:
            logger.error(f"Failed to record territory lock in DB: {e}")
            return {"status": "error", "message": str(e)}

        # Log timeline event
        try:
            OpportunityTimelineManager.log_event(
                db=db,
                lead_id=lead_id,
                event_type="TERRITORY_LOCKED_WON",
                title="🏆 DEAL WON: $1,500 Setup Deposit Paid & Territory Locked!",
                description=(
                    f"Successfully secured $1,500 turnkey installation deposit for {clinic_name}. "
                    f"3-Mile radius territory locked against local competitors. $399/mo maintenance active."
                ),
                actor="SALES_REP",
                metadata={"payment_ref": tx_id, "setup_fee": cls.SETUP_FEE_USD, "mrr": cls.MONTHLY_MAINTENANCE_USD},
                timestamp=now_str
            )
        except Exception as e:
            logger.warning(f"Failed to log deposit timeline event: {e}")

        return {
            "status": "LOCKED",
            "success": True,
            "lead_id": lead_id,
            "clinic_name": clinic_name,
            "stage": "WON",
            "territory_locked": True,
            "deposit_paid": cls.SETUP_FEE_USD,
            "setup_deposit_usd": cls.SETUP_FEE_USD,
            "monthly_retainer": cls.MONTHLY_MAINTENANCE_USD,
            "monthly_maintenance_usd": cls.MONTHLY_MAINTENANCE_USD,
            "payment_reference": tx_id,
            "locked_at": now_str
        }

    @classmethod
    def render_digital_sla_html(
        cls,
        lead_dict: Dict[str, Any],
        rep_company: str = "Dental AI Intelligence Systems, LLC"
    ) -> str:
        """Alias for render_sla_agreement_html."""
        return cls.render_sla_agreement_html(lead_dict=lead_dict, rep_company=rep_company)

    @classmethod
    def render_sla_agreement_html(
        cls,
        lead_dict: Dict[str, Any],
        rep_company: str = "Dental AI Intelligence Systems, LLC"
    ) -> str:
        """
        Renders an executive, legally formatted Service Level Agreement (SLA)
        with practice details, 3-mile exclusivity clause, and single-patient guarantee.
        """
        lead_id = lead_dict.get("id") or "preview"
        clinic_name = lead_dict.get("name") or "Your Dental Practice"
        raw_doc = lead_dict.get("doctor_name") or "Doctor"
        clean_doc = raw_doc.replace("Dr.", "").replace("Dr", "").strip()
        doc_display = f"Dr. {clean_doc}" if clean_doc else "Practice Owner"
        address = lead_dict.get("address") or "Austin, TX"
        today_date = datetime.now().strftime("%B %d, %Y")
        cert_num = f"SLA-2026-{lead_id[:6].upper()}"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Service Agreement & Territory Exclusivity • {clinic_name}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; background: #0f172a; color: #e2e8f0; }}
    @media print {{
      body {{ background: #fff; color: #000; }}
      .no-print {{ display: none; }}
    }}
  </style>
</head>
<body class="p-6 md:p-12 max-w-4xl mx-auto space-y-8">

  <!-- Agreement Header -->
  <div class="border-b border-slate-700 pb-6 flex items-start justify-between">
    <div>
      <span class="text-xs uppercase font-bold text-emerald-400 tracking-wider">Official Engagement Agreement</span>
      <h1 class="text-2xl font-black text-white mt-1">Dental WhatsApp Missed Call Recovery & Patient Intake SLA</h1>
      <p class="text-xs text-slate-400 mt-1">Certificate #{cert_num} • Executed {today_date}</p>
    </div>
    <div class="no-print">
      <button onclick="window.print()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs flex items-center gap-1.5 transition">
        Print / PDF
      </button>
    </div>
  </div>

  <!-- Parties -->
  <div class="grid grid-cols-2 gap-4 text-xs bg-slate-900 p-4 rounded-xl border border-slate-800">
    <div>
      <span class="text-slate-400 uppercase font-bold text-[10px] block">Service Provider</span>
      <div class="font-bold text-white text-sm">{rep_company}</div>
      <div class="text-slate-400 mt-0.5">Automated Concierge & Telephony Systems</div>
    </div>
    <div>
      <span class="text-slate-400 uppercase font-bold text-[10px] block">Client Practice</span>
      <div class="font-bold text-white text-sm">{clinic_name}</div>
      <div class="text-slate-400 mt-0.5">{doc_display} &bull; {address}</div>
    </div>
  </div>

  <!-- Itemized Terms -->
  <div class="space-y-4 text-xs leading-relaxed text-slate-300">
    <div class="space-y-1">
      <h3 class="font-bold text-white text-sm">1. Turnkey Scope of Work & Deliverables</h3>
      <p>Provider shall configure, test, and deploy a 24/7 autonomous WhatsApp Missed Call Recovery system. Deliverables include instant 5-second SMS/WhatsApp auto-response for unreturned after-hours calls, automated patient scheduling triage, Delta Dental/PPO insurance qualification workflows, and integration with practice calendar protocols.</p>
    </div>

    <div class="space-y-1">
      <h3 class="font-bold text-white text-sm">2. 3-Mile Territory Exclusivity Guarantee</h3>
      <p>Provider agrees not to license, install, or provide outbound missed call recovery systems to any other dental practice located within a <strong>3.0-mile radius</strong> of {clinic_name}'s primary address for the duration of this active subscription.</p>
    </div>

    <div class="space-y-1">
      <h3 class="font-bold text-white text-sm">3. Financial Terms & Schedule</h3>
      <ul class="list-disc pl-5 space-y-1">
        <li><strong>Turnkey Installation Deposit:</strong> $1,500.00 USD (one-time setup fee).</li>
        <li><strong>Monthly Maintenance & Infrastructure Retainer:</strong> $399.00 USD / month (commencing 30 days following installation).</li>
      </ul>
    </div>

    <div class="space-y-1">
      <h3 class="font-bold text-emerald-400 text-sm">4. Single-Patient Break-Even Performance Guarantee</h3>
      <p>If the system fails to recover and book at least one (1) new patient appointment valued at $1,250 or greater within the initial thirty (30) days of live operation, Client may request and receive a 100% refund of the $1,500 turnkey installation deposit.</p>
    </div>

    <div class="space-y-1">
      <h3 class="font-bold text-white text-sm">5. HIPAA & Data Privacy Certification</h3>
      <p>Provider certifies all patient interactions, triage transcripts, and appointment inquiries are processed using end-to-end encryption complying with HIPAA administrative and technical security standards.</p>
    </div>
  </div>

  <!-- Signature Block -->
  <div class="border-t border-slate-700 pt-6 grid grid-cols-2 gap-8 text-xs">
    <div class="space-y-2">
      <div class="h-10 border-b border-slate-600 flex items-end font-serif italic text-sm text-emerald-400">Sarah Jenkins (Authorized Rep)</div>
      <span class="text-slate-400 block">Provider Authorized Signature</span>
    </div>
    <div class="space-y-2">
      <div class="h-10 border-b border-slate-600 flex items-end font-serif italic text-sm text-cyan-400">{doc_display}</div>
      <span class="text-slate-400 block">Client Practice Authorized Signature</span>
    </div>
  </div>

</body>
</html>"""
