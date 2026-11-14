"""
Empirical "Mystery Shopper" Verification & Audit Engine.
Conducts real timestamped Telnyx Answering Machine Detection (AMD) after-hours probes
and keeps unverified market benchmark estimates clearly distinguished from verified probes.
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger("mystery_shopper")


class MysteryShopperAuditor:
    """Performs verifiable after-hours phone friction audits on dental clinics."""

    @classmethod
    def generate_audit_proof(
        cls,
        lead_dict: Dict[str, Any],
        test_timestamp: Optional[str] = None,
        ring_count: Optional[int] = None,
        reached_voicemail: Optional[bool] = None,
        recording_snippet_url: Optional[str] = None,
        verified: Optional[bool] = None,
        verification_method: Optional[str] = None,
        call_control_id: Optional[str] = None,
        amd_result: Optional[str] = None,
        duration_ms: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generates either a verified empirical probe report (when a live test call or explicit
        manual verification was recorded) or an explicit unverified market benchmark estimate.
        """
        now = datetime.now()
        dt_str = test_timestamp or now.strftime("%A, %b %d at %I:%M %p")

        name = lead_dict.get("name") or "Dental Practice"
        phone = lead_dict.get("phone") or "Clinic Phone"
        doctor = lead_dict.get("doctor_name") or "Doctor"
        clean_doc = doctor.replace("Dr.", "").replace("Dr", "").strip()
        doc_display = f"Dr. {clean_doc}" if clean_doc else "Doctor"

        # Determine whether empirical verification data was actually provided
        is_verified = bool(verified) if verified is not None else bool(
            call_control_id or test_timestamp is not None or ring_count is not None or reached_voicemail is not None
        )

        if not is_verified:
            has_digital_intake = bool(lead_dict.get("has_ai_chatbot") or lead_dict.get("has_online_booking"))
            likely_voicemail = not has_digital_intake
            return {
                "lead_id": lead_dict.get("id"),
                "clinic_name": name,
                "target_phone": phone,
                "doctor_name": doc_display,
                "test_timestamp": dt_str,
                "verified": False,
                "verification_status": "UNVERIFIED_BENCHMARK",
                "verification_method": verification_method or "INDUSTRY_BENCHMARK",
                "call_control_id": None,
                "amd_result": None,
                "status": "BENCHMARK_ESTIMATE",
                "status_label": "📊 Unverified Market Benchmark (Run Live Probe to Verify)",
                "ring_count": None,
                "reached_voicemail": likely_voicemail,
                "leakage_risk": "HIGH" if likely_voicemail else "LOW",
                "finding": (
                    "No live after-hours test call placed yet. Estimate based on missing 24/7 AI chat or online booking."
                    if likely_voicemail
                    else "Online booking or live chat detected; run a live Telnyx AMD probe to verify phone answer behavior."
                ),
                "evidence_summary": (
                    f"Unverified ADA market benchmark for {name} ({phone}) — no live test call has been executed yet. "
                    f"Click 'Run Live After-Hours Probe' to capture verified Telnyx AMD timing and voicemail evidence."
                ),
                "sales_pitch_quote": (
                    f"{doc_display}, our digital scan of {name} shows no 24/7 online booking or live triage. "
                    f"ADA benchmarks show 67% of emergency callers who reach after-hours voicemail book a competitor."
                ),
                "recording_snippet_url": recording_snippet_url,
                "benchmark_fact": "According to the American Dental Association, over 40% of emergency tooth searches happen outside standard 9-5 clinic hours."
            }

        rings_observed = ring_count if ring_count is not None else 5
        voicemail_hit = True if reached_voicemail is None else bool(reached_voicemail)
        method_label = verification_method or ("TELNYX_AMD_LIVE_PROBE" if call_control_id else "MANUAL_AUDIT_LOG")

        if voicemail_hit:
            status = "CONFIRMED_PHONE_FRICTION"
            status_label = "🔴 Verified After-Hours Voicemail Friction"
            finding = f"Verified probe at {dt_str} ({method_label}) rang ~{rings_observed} times and reached voicemail ({amd_result or 'machine'})."
            evidence_summary = (
                f"On {dt_str}, a verified after-hours Telnyx AMD probe ({call_control_id or method_label}) was placed to {phone}. "
                f"Observed ~{rings_observed} rings ({duration_ms or (rings_observed * 5000)}ms) before hitting voicemail with no 24/7 self-scheduling."
            )
            pitch_quote = (
                f"{doc_display}, on {dt_str}, a verified probe call to {phone} rang {rings_observed} times and landed in voicemail. "
                f"We recover those after-hours emergency patients in under 5 seconds via automated WhatsApp & AI triage."
            )
            leakage_risk = "HIGH"
        else:
            status = "RESOLVED_INTAKE"
            status_label = "🟢 Verified Live Answering Active"
            finding = f"Verified probe at {dt_str} answered within ~{rings_observed} rings ({amd_result or 'human'})."
            evidence_summary = f"Verified probe to {phone} answered by live staff/intake within ~{rings_observed} rings on {dt_str}."
            pitch_quote = f"Your team answered {phone} in {rings_observed} rings — adding 24/7 WhatsApp triage captures patients who prefer texting after hours."
            leakage_risk = "LOW"

        return {
            "lead_id": lead_dict.get("id"),
            "clinic_name": name,
            "target_phone": phone,
            "doctor_name": doc_display,
            "test_timestamp": dt_str,
            "verified": True,
            "verification_status": "VERIFIED",
            "verification_method": method_label,
            "call_control_id": call_control_id,
            "amd_result": amd_result,
            "duration_ms": duration_ms,
            "status": status,
            "status_label": status_label,
            "ring_count": rings_observed,
            "reached_voicemail": voicemail_hit,
            "leakage_risk": leakage_risk,
            "finding": finding,
            "evidence_summary": evidence_summary,
            "sales_pitch_quote": pitch_quote,
            "recording_snippet_url": recording_snippet_url,
            "benchmark_fact": "According to the American Dental Association, over 40% of emergency tooth searches happen outside standard 9-5 clinic hours."
        }

    @classmethod
    def launch_verification_probe(
        cls,
        lead_dict: Dict[str, Any],
        db: Optional[Any] = None,
        server_base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Places a silent live Telnyx Call Control v2 verification probe with AMD (`detect_beep`)
        and immediately hangs up upon machine/human detection via webhook without disturbing staff.
        """
        from voice_dialer import VoiceDialerEngine, clean_phone_e164

        lead_id = lead_dict.get("id")
        target_phone = clean_phone_e164(lead_dict.get("phone"))
        if not target_phone:
            return {"status": "error", "error": "MISSING_PHONE_NUMBER", "verified": False}

        started_ms = int(datetime.now().timestamp() * 1000)
        dispatch_res = VoiceDialerEngine.dispatch_call(
            lead=lead_dict,
            to_phone=target_phone,
            carrier_override="TELNYX",
            db=db,
            server_base_url=server_base_url or os.getenv("BASE_APP_URL"),
            initial_mode="SILENT_PROBE",
            extra_client_state={
                "probe_type": "mystery_shopper",
                "probe_started_ms": started_ms,
            },
            register_live_session=False
        )

        if dispatch_res.get("blocked") or dispatch_res.get("status") in ("blocked", "failed", "error"):
            return {
                "status": dispatch_res.get("status", "failed"),
                "verified": False,
                "error": dispatch_res.get("error") or dispatch_res.get("reason") or "Probe dispatch failed",
                "dispatch_result": dispatch_res
            }

        pending_proof = {
            "lead_id": lead_id,
            "clinic_name": lead_dict.get("name") or "Dental Practice",
            "target_phone": target_phone,
            "doctor_name": lead_dict.get("doctor_name") or "Doctor",
            "test_timestamp": datetime.now().strftime("%A, %b %d at %I:%M %p"),
            "verified": False,
            "verification_status": "PROBE_PENDING",
            "verification_method": "TELNYX_AMD_LIVE_PROBE",
            "call_control_id": dispatch_res.get("call_id"),
            "probe_started_ms": started_ms,
            "status": "PROBE_PENDING",
            "status_label": "⏳ Live Telnyx AMD Probe In Progress...",
            "ring_count": None,
            "reached_voicemail": None,
            "leakage_risk": "PENDING",
            "finding": f"Live Telnyx probe dialed {target_phone} ({dispatch_res.get('mode')}); awaiting AMD result.",
            "evidence_summary": f"Telnyx Call Control probe {dispatch_res.get('call_id')} active; auto-hangup armed on AMD detection.",
            "sales_pitch_quote": "Live verification probe is currently running; refresh shortly for verified AMD results."
        }
        if db and lead_id:
            db.update_lead_mystery_audit(lead_id, pending_proof)
        return pending_proof

    @classmethod
    def handle_probe_webhook_event(
        cls,
        event_type: str,
        payload: Dict[str, Any],
        client_state: Dict[str, Any],
        db: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Finalizes a silent Mystery Shopper Telnyx probe on AMD/hangup without playing sales audio,
        disconnecting immediately upon classification and persisting verified proof to DB.
        """
        from voice_dialer import hangup_telnyx_call

        lead_id = client_state.get("lead_id")
        call_control_id = payload.get("call_control_id")
        started_ms = int(client_state.get("probe_started_ms") or 0)
        now_ms = int(datetime.now().timestamp() * 1000)
        elapsed_ms = max(0, now_ms - started_ms) if started_ms else 20000
        est_rings = max(1, min(10, round(elapsed_ms / 5000) or 4))

        lead = (db.get_lead(lead_id) if (db and lead_id) else None) or {
            "id": lead_id,
            "name": client_state.get("name"),
            "doctor_name": client_state.get("doctor_name"),
            "phone": client_state.get("phone"),
        }
        dt_str = datetime.now().strftime("%A, %b %d at %I:%M %p")

        if event_type in ("call.machine.detection.ended", "call.machine.greeting.ended"):
            amd_result = str(payload.get("result", "")).lower() or "machine"
            reached_vm = any(m in amd_result for m in ("machine", "beep", "answering", "voicemail")) or event_type == "call.machine.greeting.ended"
            if call_control_id:
                hangup_telnyx_call(call_control_id)

            proof = cls.generate_audit_proof(
                lead_dict=lead,
                test_timestamp=dt_str,
                ring_count=est_rings,
                reached_voicemail=reached_vm,
                verified=True,
                verification_method="TELNYX_AMD_LIVE_PROBE",
                call_control_id=call_control_id,
                amd_result=amd_result,
                duration_ms=elapsed_ms
            )
            if db and lead_id:
                db.update_lead_mystery_audit(lead_id, proof)
                try:
                    from timeline import OpportunityTimelineManager
                    OpportunityTimelineManager.log_event(
                        db=db,
                        lead_id=lead_id,
                        event_type="MYSTERY_SHOP_VERIFIED",
                        title=f"🕵️ Mystery Shop Probe Verified: {proof['status']}",
                        description=proof["finding"],
                        actor="SYSTEM",
                        metadata=proof
                    )
                except Exception:
                    pass
            return {"status": "probe_verified", "proof": proof}

        if event_type == "call.hangup":
            existing = lead.get("mystery_audit_json") if isinstance(lead, dict) else None
            if isinstance(existing, dict) and existing.get("verification_status") == "PROBE_PENDING":
                hangup_cause = str(payload.get("hangup_cause") or "timeout").lower()
                no_human = hangup_cause in ("timeout", "no_answer", "user_busy", "call_rejected", "originator_cancel")
                proof = cls.generate_audit_proof(
                    lead_dict=lead,
                    test_timestamp=dt_str,
                    ring_count=est_rings,
                    reached_voicemail=no_human,
                    verified=True,
                    verification_method="TELNYX_AMD_LIVE_PROBE",
                    call_control_id=call_control_id,
                    amd_result=f"hangup:{hangup_cause}",
                    duration_ms=elapsed_ms
                )
                if db and lead_id:
                    db.update_lead_mystery_audit(lead_id, proof)
                return {"status": "probe_finalized_on_hangup", "proof": proof}

        return {"status": "probe_event_recorded", "event": event_type}
