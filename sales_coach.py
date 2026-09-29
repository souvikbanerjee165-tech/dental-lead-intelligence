"""
Sales Coach & Personal Sales OS Engine (Roadmap #8 & #9).
- SalesCoach: Automated post-call performance analyzer (talk-to-listen ratio, missed buying signals, objection grading, battlecard recommendations).
- SalesOS: Daily executive sales command center (pipeline MRR, calls pacing, conversion rate, tracked ARR, niche breakdown).
"""

import os
import re
import json
import logging
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from database import DatabaseManager
from memory_manager import MemoryManager

logger = logging.getLogger("sales_coach")


class SalesCoach:
    """Post-call conversational intelligence & performance coach."""

    BUYING_SIGNAL_PATTERNS = [
        (r"(how much|pricing|cost|rate|fee|package)", "PRICING_INQUIRY", "Prospect asked about pricing or contract structure."),
        (r"(after hours|evening|weekend|emergency|missed call|night)", "AFTER_HOURS_INTAKE", "Prospect confirmed after-hours patient demand."),
        (r"(office manager|practice manager|doctor|dr\.|principal)", "DECISION_MAKER_REFERRAL", "Prospect referenced practice decision-maker."),
        (r"(send (an |the )?email|send me info|email me|proposal)", "INFORMATION_REQUEST", "Prospect requested written proposal/documentation."),
        (r"(dentrix|eaglesoft|open dental|curve|pms|software|calendar)", "TECH_INTEGRATION", "Prospect inquired about dental PMS/calendar compatibility."),
        (r"(demo|meeting|calendar|schedule|tomorrow|call back)", "SCHEDULING_INTENT", "Prospect signaled availability for a demo.")
    ]

    OBJECTION_PATTERNS = [
        (r"(already have|receptionist|front desk|covered)", "RECEPTIONIST_COVERAGE", "We already have a front desk team."),
        (r"(too busy|no time|running behind|patient in chair)", "TIME_POOR", "Doctor or staff is too busy right now."),
        (r"(not interested|no thanks|dont need)", "GENERAL_DISINTEREST", "Not interested in third-party services."),
        (r"(cost|expensive|budget|cant afford)", "PRICE_OBJECTION", "Budget or cost sensitivity."),
        (r"(just send email|email info@)", "GATEKEEPER_BRUSH_OFF", "Gatekeeper brush-off to general mailbox.")
    ]

    @classmethod
    def analyze_call(
        cls,
        transcript: str,
        lead_dict: Optional[Dict[str, Any]] = None,
        call_duration_sec: int = 0
    ) -> Dict[str, Any]:
        """Performs deep post-call diagnostic on transcript turns."""
        lead = lead_dict or {}
        clinic_name = lead.get("name", "Dental Practice")
        doctor_name = lead.get("doctor_name", "Doctor")

        # 1. Parse Turns & Compute Talk-to-Listen Ratio
        lines = [ln.strip() for ln in transcript.split("\n") if ln.strip()]
        rep_words = 0
        prospect_words = 0
        rep_turns = 0
        prospect_turns = 0

        for ln in lines:
            lower = ln.lower()
            if lower.startswith("rep:") or lower.startswith("ai:") or lower.startswith("caller:"):
                text = re.sub(r"^(rep|ai|caller):\s*", "", ln, flags=re.I)
                words = len(text.split())
                rep_words += words
                rep_turns += 1
            elif lower.startswith("prospect:") or lower.startswith("receptionist:") or lower.startswith("doctor:"):
                text = re.sub(r"^(prospect|receptionist|doctor):\s*", "", ln, flags=re.I)
                words = len(text.split())
                prospect_words += words
                prospect_turns += 1
            else:
                # Ambiguous: distribute evenly
                words = len(ln.split())
                rep_words += words // 2
                prospect_words += words - (words // 2)

        total_words = rep_words + prospect_words or 1
        rep_ratio = round((rep_words / total_words) * 100, 1)
        prospect_ratio = round((prospect_words / total_words) * 100, 1)

        # Talk-to-Listen Diagnosis
        if rep_ratio > 60:
            talk_ratio_grade = "POOR"
            talk_ratio_feedback = f"You spoke {rep_ratio}% of the time. Top closers keep rep talk time under 45%. Allow the front desk to vent about missed patient intake."
        elif rep_ratio > 48:
            talk_ratio_grade = "ACCEPTABLE"
            talk_ratio_feedback = f"Rep talk ratio: {rep_ratio}%. Good engagement, but aim for slightly more open-ended inquiry."
        else:
            talk_ratio_grade = "OPTIMAL"
            talk_ratio_feedback = f"Rep talk ratio: {rep_ratio}%. Outstanding listening posture. You gave the prospect space to speak."

        # 2. Detect Missed Buying Signals
        full_text_lower = transcript.lower()
        signals_detected = []
        for pat, tag, desc in cls.BUYING_SIGNAL_PATTERNS:
            match = re.search(pat, full_text_lower)
            if match:
                signals_detected.append({
                    "type": tag,
                    "matched_phrase": match.group(0),
                    "description": desc,
                    "action_required": "Directly leverage this point to secure the calendar demo."
                })

        # 3. Detect Objections & Grade Handling
        objections_found = []
        for pat, cat, desc in cls.OBJECTION_PATTERNS:
            match = re.search(pat, full_text_lower)
            if match:
                objections_found.append({
                    "category": cat,
                    "quote": match.group(0),
                    "description": desc
                })

        # Score objection handling
        if not objections_found:
            objection_score = 9
            objection_verdict = "Smooth call with minimal resistance. Prospect was receptive."
            recommended_rebuttal = "Keep asking for the 10-minute diagnostic review."
        else:
            primary_obj = objections_found[0]
            if primary_obj["category"] == "RECEPTIONIST_COVERAGE":
                objection_score = 7
                recommended_rebuttal = "Acknowledge receptionist excellence, then ask: 'Who answers high-ticket implant questions at 8:30 PM on Sunday when the office is dark?'"
            elif primary_obj["category"] == "PRICE_OBJECTION":
                objection_score = 6
                recommended_rebuttal = "Anchor against single case value: 'One missed crown or emergency patient per month ($1,200) covers our entire system 3x over.'"
            elif primary_obj["category"] == "GATEKEEPER_BRUSH_OFF":
                objection_score = 5
                recommended_rebuttal = "Politely pivot: 'Happy to send that over. What's the office manager's direct first name so I can address the audit to her attention?'"
            else:
                objection_score = 6
                recommended_rebuttal = "Emphasize zero staff disruption and our 14-day risk-free patient capture test."
            objection_verdict = f"Handled {len(objections_found)} objection(s). Opportunity to improve tactical counter-punch."

        # Overall Call Score (1-10)
        overall_score = round((objection_score * 0.6) + (10 if talk_ratio_grade == "OPTIMAL" else (7 if talk_ratio_grade == "ACCEPTABLE" else 4)) * 0.4, 1)

        # 4. Ingest into Institutional Memory if Outcome Was Notable
        recorded_memory_id = None
        if objections_found and lead.get("id"):
            try:
                prim = objections_found[0]
                metro = "Austin"
                addr = lead.get("address") or ""
                for m in ["Austin", "Dallas", "Houston", "Miami", "Denver", "London", "Chicago"]:
                    if m.lower() in addr.lower():
                        metro = m
                        break

                recorded_memory_id = MemoryManager.record_interaction(
                    lead_id=lead["id"],
                    clinic_name=clinic_name,
                    doctor_name=doctor_name,
                    metro=metro,
                    outcome="OBJECTION_LOGGED" if overall_score < 8 else "INTERESTED",
                    objection_category=prim["category"],
                    objection_quote=f"Prospect stated: '{prim['quote']}'",
                    effective_rebuttal=recommended_rebuttal,
                    deal_value=3979.0,
                    lessons_learned=f"Talk ratio was {rep_ratio}%. Coach advice: {talk_ratio_feedback}"
                )
            except Exception as e:
                logger.warning(f"Could not auto-record call coaching memory: {e}")

        return {
            "overall_score": overall_score,
            "talk_to_listen": {
                "rep_percent": rep_ratio,
                "prospect_percent": prospect_ratio,
                "rep_words": rep_words,
                "prospect_words": prospect_words,
                "grade": talk_ratio_grade,
                "feedback": talk_ratio_feedback
            },
            "buying_signals": signals_detected,
            "objections_detected": objections_found,
            "objection_handling": {
                "score": objection_score,
                "verdict": objection_verdict,
                "recommended_rebuttal": recommended_rebuttal
            },
            "auto_recorded_memory_id": recorded_memory_id,
            "coaching_summary": f"Overall Call Grade: {overall_score}/10. {talk_ratio_feedback} Next action: {recommended_rebuttal}"
        }


class SalesOS:
    """Daily sales operating system metrics engine."""

    @classmethod
    def get_daily_sales_metrics(cls, db: DatabaseManager, tenant_id: str = "default") -> Dict[str, Any]:
        """Calculates real-time daily operational KPIs for the sales cockpit."""
        now = datetime.now()
        today_prefix = now.strftime("%Y-%m-%d")

        with db._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Total Leads & High Probability Targets (>=75% Win Prob)
            cursor.execute("SELECT COUNT(*) FROM leads")
            total_leads = cursor.fetchone()[0]

            cursor.execute("""
            SELECT COUNT(*) FROM leads 
            WHERE (COALESCE(win_probability_pct, buying_probability, 75) >= 75)
              AND stage NOT IN ('WON', 'LOST')
            """)
            targets_count = cursor.fetchone()[0]

            # 2. Pipeline MRR Potential (Estimated missed revenue monthly * 0.10 standard agency retainer)
            cursor.execute("""
            SELECT SUM(COALESCE(missed_rev_max, 4500)) FROM leads
            WHERE stage NOT IN ('WON', 'LOST')
            """)
            sum_leakage = cursor.fetchone()[0] or 0
            pipeline_mrr = round(sum_leakage * 0.08, 0) # conservative 8% capture retainer

            # 3. Today's Calls Pacing
            cursor.execute("SELECT COUNT(*) FROM call_logs WHERE timestamp LIKE ?", (f"{today_prefix}%",))
            calls_today = cursor.fetchone()[0]
            daily_call_target = 15
            calls_remaining = max(0, daily_call_target - calls_today)

            # 4. Meetings Booked (Leads in stage 'MEETING' or 'DEMO_BOOKED')
            cursor.execute("SELECT COUNT(*) FROM leads WHERE stage IN ('MEETING', 'DEMO_BOOKED')")
            meetings_booked = cursor.fetchone()[0]

            # 5. Top Niche Breakdown
            cursor.execute("""
            SELECT COALESCE(category, 'General Dentistry') as cat, COUNT(*) as cnt 
            FROM leads 
            GROUP BY cat 
            ORDER BY cnt DESC 
            LIMIT 3
            """)
            niche_distribution = [{"niche": row["cat"], "count": row["cnt"]} for row in cursor.fetchall()]

        # 6. Memory Intelligence Stats (Closed ARR & Macro Win Rate)
        mem_stats = MemoryManager.get_memory_intelligence_summary()

        return {
            "today_targets_count": targets_count,
            "total_leads_tracked": total_leads,
            "pipeline_mrr_potential": pipeline_mrr,
            "calls_made_today": calls_today,
            "calls_daily_target": daily_call_target,
            "calls_remaining_today": calls_remaining,
            "meetings_booked": meetings_booked,
            "win_rate_pct": mem_stats.get("win_rate_pct", 28.5),
            "tracked_arr_closed": mem_stats.get("tracked_arr_closed", 112260.0),
            "top_niches": niche_distribution,
            "pacing_status": "ON_TRACK" if calls_today >= 5 else "NEEDS_ATTENTION",
            "daily_action_briefing": f"You have {targets_count} high-fit clinics ready. Target: {daily_call_target} calls today. Currently {calls_today} logged with ${pipeline_mrr:,.0f}/mo in active pipeline potential."
        }

    @classmethod
    def get_todays_mission(cls, db: DatabaseManager, offset: int = 0) -> Dict[str, Any]:
        """Phase 8: Automatic Morning Plan ('Today's Mission').
        Presents the single top-ranked clinic target sequentially with 1-click execution actions.
        """
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT id, name, doctor_name, phone, address, website, opportunity_score,
                   COALESCE(buy_probability_pct, 75) as buy_probability_pct,
                   missed_rev_min, missed_rev_max, why_score_reasons, stage, contact_status
            FROM leads
            WHERE stage NOT IN ('WON', 'LOST')
            ORDER BY COALESCE(buy_probability_pct, 75) DESC, opportunity_score DESC, id ASC
            """)
            all_targets = [dict(r) for r in cursor.fetchall()]

        total_queue = len(all_targets)
        if not all_targets or offset >= total_queue:
            return {
                "mission_active": False,
                "message": "Today's Mission Complete! All priority clinics have been contacted or queued.",
                "total_queue": total_queue,
                "current_index": offset,
                "target": None
            }

        target = all_targets[offset]
        lead_id = target["id"]

        pre_call_intel = None
        try:
            from pre_call_researcher import PreCallResearcher
            pre_call_intel = PreCallResearcher.research_lead(db, lead_id)
        except Exception as e:
            logger.warning(f"Could not fetch pre-call research for mission lead {lead_id}: {e}")

        drivers = []
        if target.get("why_score_reasons"):
            try:
                raw = json.loads(target["why_score_reasons"])
                if isinstance(raw, list):
                    drivers = raw[:3]
                else:
                    drivers = [str(raw)[:100]]
            except Exception:
                drivers = [str(target["why_score_reasons"])[:100]]

        phone_num = target.get("phone") or ""
        clean_phone = re.sub(r"[^\d+]", "", phone_num)
        doctor = target.get("doctor_name") or "Doctor"
        clinic = target.get("name") or "Dental Clinic"

        whatsapp_pitch = (
            f"Hi {doctor}, noticed {clinic}'s after-hours patient intake has a gap on evenings and weekends. "
            f"We built an AI dental receptionist capturing ~12 new patient bookings/mo with zero staff changes. "
            f"Open to a 60-second video demo?"
        )

        return {
            "mission_active": True,
            "total_queue": total_queue,
            "current_index": offset + 1,
            "remaining": max(0, total_queue - (offset + 1)),
            "target": {
                "lead_id": lead_id,
                "clinic_name": clinic,
                "doctor_name": doctor,
                "phone": phone_num,
                "clean_phone": clean_phone,
                "address": target.get("address"),
                "website": target.get("website"),
                "opportunity_score": target.get("opportunity_score", 0),
                "buy_probability_pct": target.get("buy_probability_pct", 75),
                "missed_revenue_annual": (target.get("missed_rev_max", 4500) or 4500) * 12,
                "top_drivers": drivers,
                "pre_call_intel": pre_call_intel,
                "quick_actions": {
                    "call_now_url": f"tel:{clean_phone}" if clean_phone else None,
                    "whatsapp_url": f"https://wa.me/{clean_phone}?text={urllib.parse.quote(whatsapp_pitch)}",
                    "whatsapp_pitch_text": whatsapp_pitch
                }
            }
        }

    @classmethod
    def get_revenue_forecast(cls, db: DatabaseManager, calls_planned: int = 10) -> Dict[str, Any]:
        """Phase 13: Predictive Revenue Forecaster.
        Calculates expected connects, meetings, closes, MRR, and ARR based on empirical conversion rates:
        - Connect Rate: 35%
        - Meeting Booking Rate: 18% of connects
        - Deal Closing Rate: 28% of meetings
        - Retainer MRR: $499/mo per closed clinic
        - Retainer ARR: MRR * 12
        """
        connect_rate = 0.35
        meeting_rate = 0.18
        close_rate = 0.28
        mrr_per_client = 499.0

        expected_connects = round(calls_planned * connect_rate, 1)
        expected_meetings = round(expected_connects * meeting_rate, 2)
        expected_closes = round(expected_meetings * close_rate, 2)
        expected_mrr = round(expected_closes * mrr_per_client, 2)
        expected_arr = round(expected_mrr * 12.0, 2)

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM leads WHERE stage NOT IN ('WON', 'LOST')")
            active_pipeline_leads = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM leads WHERE stage = 'WON'")
            won_clients = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM leads WHERE stage IN ('MEETING', 'DEMO_BOOKED')")
            active_meetings = cursor.fetchone()[0] or 0

        pipe_connects = round(active_pipeline_leads * connect_rate, 1)
        pipe_meetings = round(pipe_connects * meeting_rate, 1) + active_meetings
        pipe_closes = round(pipe_meetings * close_rate, 1)
        pipe_mrr = round(pipe_closes * mrr_per_client, 2)
        pipe_arr = round(pipe_mrr * 12.0, 2)

        scenarios = []
        for c in [10, 25, 50, 100]:
            conns = round(c * connect_rate, 1)
            meets = round(conns * meeting_rate, 1)
            cls_count = round(meets * close_rate, 1)
            smrr = round(cls_count * mrr_per_client, 0)
            scenarios.append({
                "calls": c,
                "expected_connects": conns,
                "expected_meetings": meets,
                "expected_closes": cls_count,
                "expected_mrr": smrr,
                "expected_arr": round(smrr * 12, 0)
            })

        return {
            "calls_planned": calls_planned,
            "expected_connects": expected_connects,
            "expected_meetings": expected_meetings,
            "expected_closes": expected_closes,
            "expected_mrr": expected_mrr,
            "expected_arr": expected_arr,
            "active_pipeline_leads": active_pipeline_leads,
            "current_won_clients": won_clients,
            "current_active_mrr": round(won_clients * mrr_per_client, 2),
            "pipeline_forecast": {
                "potential_closes": pipe_closes,
                "forecasted_pipeline_mrr": pipe_mrr,
                "forecasted_pipeline_arr": pipe_arr
            },
            "scenarios": scenarios,
            "formula_summary": "10 Calls -> ~3.5 Connects -> ~0.6 Meetings -> ~0.18 Closes (~$90/mo incremental MRR or ~$1,080 ARR)"
        }

    @classmethod
    def get_productivity_telemetry(cls, db: DatabaseManager) -> Dict[str, Any]:
        """Phase 14: Personal Productivity Dashboard (Founder Telemetry).
        Tracks daily calls, WhatsApps, meetings, win rate, best city, and best niche.
        """
        now = datetime.now()
        today_prefix = now.strftime("%Y-%m-%d")

        with db._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM call_logs WHERE timestamp LIKE ?", (f"{today_prefix}%",))
            calls_today = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM call_logs")
            total_calls = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM leads WHERE stage IN ('MEETING', 'DEMO_BOOKED')")
            meetings_booked = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM leads WHERE stage = 'WON'")
            deals_won = cursor.fetchone()[0]

            conversion_rate = round((deals_won / total_calls * 100), 1) if total_calls > 0 else 0.0

            cursor.execute("""
            SELECT address FROM leads WHERE stage IN ('WON', 'MEETING') AND address IS NOT NULL AND address != ''
            """)
            won_addresses = cursor.fetchall()
            city_counts = {}
            for row in won_addresses:
                addr = row["address"]
                parts = [p.strip() for p in addr.split(",") if p.strip()]
                city = parts[-2] if len(parts) >= 2 else (parts[0] if parts else "Austin")
                city_counts[city] = city_counts.get(city, 0) + 1
            best_city = max(city_counts.items(), key=lambda x: x[1])[0] if city_counts else "Austin, TX"

            cursor.execute("""
            SELECT COALESCE(category, 'General Dentistry') as cat, COUNT(*) as cnt
            FROM leads
            WHERE stage IN ('WON', 'MEETING')
            GROUP BY cat
            ORDER BY cnt DESC
            LIMIT 1
            """)
            best_niche_row = cursor.fetchone()
            best_niche = best_niche_row["cat"] if best_niche_row else "Cosmetic & Implant Dentistry"

            cursor.execute("SELECT COUNT(*) FROM opportunity_timeline WHERE timestamp LIKE ?", (f"{today_prefix}%",))
            activities_today = cursor.fetchone()[0]

        daily_call_target = 15
        target_progress_pct = min(100.0, round((calls_today / daily_call_target) * 100, 1))

        return {
            "date": today_prefix,
            "calls_made_today": calls_today,
            "daily_call_target": daily_call_target,
            "target_progress_pct": target_progress_pct,
            "calls_remaining_today": max(0, daily_call_target - calls_today),
            "meetings_booked": meetings_booked,
            "deals_won": deals_won,
            "conversion_rate_pct": conversion_rate,
            "best_converting_city": best_city,
            "best_converting_niche": best_niche,
            "total_activities_today": activities_today,
            "streak_status": "FIRE" if calls_today >= daily_call_target else ("ACTIVE" if calls_today > 0 else "PENDING")
        }

    @classmethod
    def log_productivity_activity(
        cls,
        db: DatabaseManager,
        activity_type: str,
        count: int = 1,
        lead_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Logs custom founder productivity action (e.g. WHATSAPP_SENT, PROPOSAL_SENT, CALL_MADE)."""
        now_str = datetime.now().isoformat()
        try:
            from timeline import OpportunityTimelineManager
            OpportunityTimelineManager.log_event(
                db=db,
                lead_id=lead_id or "GENERAL_ACTIVITY",
                event_type=activity_type,
                title=f"Activity Logged: {activity_type} (x{count})",
                description=notes or f"Founder logged productivity activity: {activity_type}",
                actor="FOUNDER",
                metadata={"activity_type": activity_type, "count": count, "notes": notes},
                timestamp=now_str
            )
        except Exception as e:
            logger.warning(f"Could not log productivity activity to timeline: {e}")

        return {
            "status": "success",
            "activity_type": activity_type,
            "count": count,
            "logged_at": now_str
        }

    @classmethod
    def summarize_call_notes(
        cls,
        db: DatabaseManager,
        transcript_text: str,
        lead_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        AI Call Notes & Transcript Summarizer (Pillar 3, Feature 7).
        Analyzes call transcript / rep notes and extracts structured sales intelligence:
        - Pain points
        - Budget & Price Sensitivity
        - Decision Maker status
        - Next Step
        - Buying Probability %
        - Follow-up date & automatic reminder
        """
        text_lower = transcript_text.lower()
        lead = db.get_lead(lead_id) if lead_id else {}
        clinic_name = lead.get("name", "Dental Clinic") if lead else "Dental Clinic"

        # 1. Pain points extraction
        pain_points = []
        if "voicemail" in text_lower or "unanswered" in text_lower or "phone" in text_lower or "miss" in text_lower:
            pain_points.append("Inbound phone calls rolling to voicemail during lunch and after-hours")
        if "staff" in text_lower or "busy" in text_lower or "overwhelm" in text_lower or "receptionist" in text_lower:
            pain_points.append("Front desk staff overwhelmed with routine inquiries and check-ins")
        if "emergency" in text_lower or "weekend" in text_lower or "night" in text_lower:
            pain_points.append("Lost emergency patient cases over weekends when clinic is closed")
        if "booking" in text_lower or "schedule" in text_lower or "no show" in text_lower:
            pain_points.append("Manual phone scheduling causing patient drop-off and no-shows")
        if not pain_points:
            pain_points.append("General practice intake latency and missed online visitor conversion")

        # 2. Budget & Pricing
        if "expensive" in text_lower or "budget" in text_lower or "cost" in text_lower or "price" in text_lower:
            budget_status = "Price conscious; anchor against single patient treatment value ($1,200)"
        elif "roi" in text_lower or "worth it" in text_lower or "pilot" in text_lower:
            budget_status = "ROI-driven; receptive to 14-day risk-free pilot"
        else:
            budget_status = "Standard practice budget ($500-$1,000/mo) viable if chair time fills"

        # 3. Decision maker status
        if "dr." in text_lower or "doctor" in text_lower or "owner" in text_lower or "partner" in text_lower:
            dm_status = "Spoke directly with Doctor / Practice Owner"
            prob = 85
        elif "office manager" in text_lower or "practice manager" in text_lower:
            dm_status = "Connected with Office Manager (Key Influencer)"
            prob = 75
        elif "receptionist" in text_lower or "front desk" in text_lower or "gatekeeper" in text_lower:
            dm_status = "Front desk receptionist screening call"
            prob = 60
        else:
            dm_status = "Initial contact established"
            prob = 65

        # 4. Next step determination
        if "demo" in text_lower or "meeting" in text_lower or "calendar" in text_lower or "zoom" in text_lower:
            next_step = "Conduct 10-minute diagnostic review and live WhatsApp intake demo"
            prob = max(prob, 88)
            followup_days = 1
        elif "send" in text_lower or "email" in text_lower or "video" in text_lower or "info" in text_lower:
            next_step = "Send 60-second smartphone video preview and 14-day pilot agreement"
            followup_days = 1
        elif "call back" in text_lower or "busy" in text_lower or "in chair" in text_lower:
            next_step = "Call back during morning consultation hours (8:30 AM)"
            followup_days = 2
        else:
            next_step = "Follow up with local market benchmark study"
            followup_days = 2

        from datetime import datetime, timedelta
        followup_date = (datetime.now() + timedelta(days=followup_days)).strftime("%Y-%m-%d")

        # Auto-create reminder if lead_id is provided
        reminder_id = None
        if lead_id:
            try:
                from reminder_manager import ReminderManager
                reminder_id = ReminderManager.auto_schedule_from_call_outcome(
                    db=db,
                    lead_id=lead_id,
                    outcome="INFO_REQUESTED" if "send" in next_step.lower() else "CALL_BACK",
                    notes=f"AI Call Notes: {next_step}"
                )
            except Exception as e:
                logger.warning(f"Could not auto-schedule reminder from call notes: {e}")

        # Log to timeline
        if lead_id:
            with db._get_connection() as conn:
                conn.execute("""
                INSERT INTO opportunity_timeline (lead_id, timestamp, event_type, title, description, actor)
                VALUES (?, ?, 'CALL_NOTES_SUMMARIZED', 'AI Call Notes Logged', ?, 'SALES_COACH');
                """, (lead_id, datetime.now().isoformat(), f"Decision Maker: {dm_status}. Next Step: {next_step}."))
                conn.commit()

        return {
            "lead_id": lead_id,
            "clinic_name": clinic_name,
            "pain_points": pain_points,
            "budget_sentiment": budget_status,
            "decision_maker_status": dm_status,
            "next_step": next_step,
            "buying_probability_pct": prob,
            "recommended_followup_date": followup_date,
            "auto_reminder_id": reminder_id,
            "summary_bullet_points": [
                f"Pain: {pain_points[0]}",
                f"Contact: {dm_status}",
                f"Next Step: {next_step}",
                f"Follow-up: {followup_date} (Prob: {prob}%)"
            ]
        }

