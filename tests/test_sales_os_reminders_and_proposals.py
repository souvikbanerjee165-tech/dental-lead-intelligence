"""
Tests for Pillar 3: Complete Personal Sales OS & Client Retention.
Verifies:
1. AI Call Notes Summarizer (pasting transcript -> extracts Pain, Budget, DM, Next Step, Follow-up).
2. Automated Follow-Up Reminders & Snooze Engine (auto-triggering 2-day reminder on No Answer).
3. 3-Tier Proposal Generator (Bronze, Silver, Gold with FAQs, timeline, and contract terms).
4. Interactive Dental ROI Calculator (lost revenue, patient recapture, net ROI multiple).
5. Post-Sale Client Health Scorecard (messages answered, appointments booked, revenue generated, retention status).
"""

import pytest
from database import DatabaseManager
from sales_coach import SalesOS
from reminder_manager import ReminderManager
from proposals import generate_tiered_sales_proposal
from roi_calculator import ROICalculator
from client_health import ClientHealthTracker


@pytest.fixture
def clean_db(tmp_path):
    db_file = tmp_path / "test_pillar3.db"
    return DatabaseManager(db_path=str(db_file))


def test_ai_call_notes_summarizer(clean_db):
    """Verifies structured intelligence extraction from pasted call notes and auto-reminder generation."""
    lead_id = "test-call-lead-01"
    clean_db.save_lead({
        "id": lead_id,
        "name": "Mueller Dental Studio",
        "doctor_name": "Dr. Angela Martin",
        "phone": "512-555-0303",
        "opportunity_score": 85
    })

    transcript = """
    Rep: Hi, this is Alex following up on patient inquiries for Mueller Dental.
    Dr. Martin: Hi Alex. We get a ton of calls rolling to voicemail after 5 PM, and the front desk is totally overwhelmed checking in patients.
    Rep: Exactly, we automate after-hours emergency bookings directly on WhatsApp.
    Dr. Martin: That sounds interesting, but we're somewhat price conscious right now. Can you send me a quick video preview to my email?
    Rep: Absolutely, I'll email you the 60-second video walkthrough today and follow up tomorrow afternoon.
    """

    summary = SalesOS.summarize_call_notes(clean_db, transcript_text=transcript, lead_id=lead_id)
    assert summary["clinic_name"] == "Mueller Dental Studio"
    assert len(summary["pain_points"]) > 0
    assert any("voicemail" in p.lower() or "overwhelmed" in p.lower() for p in summary["pain_points"])
    assert "Doctor" in summary["decision_maker_status"] or "Dr." in summary["decision_maker_status"]
    assert "video" in summary["next_step"].lower() or "preview" in summary["next_step"].lower()
    assert summary["buying_probability_pct"] >= 75
    assert summary["recommended_followup_date"] is not None
    assert summary["auto_reminder_id"] is not None

    # Check reminder was logged in database
    due_reminders = ReminderManager.get_due_reminders(clean_db)
    assert len(due_reminders) >= 1
    assert due_reminders[0]["lead_id"] == lead_id


def test_automated_followup_reminders_and_snooze(clean_db):
    """Verifies outcome-based automatic follow-up reminders and snooze operations."""
    lead_id = "test-rem-lead-02"
    clean_db.save_lead({
        "id": lead_id,
        "name": "Arboretum Dental Care",
        "doctor_name": "Dr. Kevin Scott"
    })

    # Auto-schedule on "No Answer"
    rem_id = ReminderManager.auto_schedule_from_call_outcome(
        clean_db,
        lead_id=lead_id,
        outcome="NO_ANSWER",
        notes="Rang 5 times, reached voicemail"
    )
    assert rem_id is not None

    # Verify due list
    due = ReminderManager.get_due_reminders(clean_db)
    assert any(r["id"] == rem_id for r in due)

    # Snooze reminder by 3 days
    snoozed = ReminderManager.snooze_reminder(clean_db, rem_id, days=3)
    assert snoozed is True

    # Complete reminder
    completed = ReminderManager.complete_reminder(clean_db, rem_id)
    assert completed is True

    # Should no longer be pending
    active_due = ReminderManager.get_due_reminders(clean_db)
    assert not any(r["id"] == rem_id for r in active_due)


def test_3_tier_proposal_generator():
    """Verifies generation of Bronze, Silver, Gold proposal with FAQs, timeline, and risk-free contract."""
    lead = {
        "id": "prop-lead-01",
        "name": "Apex Implant & Cosmetic Dentistry",
        "doctor_name": "Dr. Bruce Wayne",
        "address": "1000 Colorado St, Austin, TX",
        "phone": "512-555-0909",
        "missed_rev_max": 6500
    }

    proposal = generate_tiered_sales_proposal(lead)
    assert proposal["clinic_name"] == "Apex Implant & Cosmetic Dentistry"
    assert len(proposal["tiers"]) == 3

    tier_names = [t["tier"] for t in proposal["tiers"]]
    assert "Bronze" in tier_names
    assert "Silver" in tier_names
    assert "Gold" in tier_names

    silver_tier = next(t for t in proposal["tiers"] if t["tier"] == "Silver")
    assert silver_tier["monthly_retainer"] == 697
    assert silver_tier["recommended"] is True

    assert len(proposal["faqs"]) >= 3
    assert len(proposal["implementation_timeline"]) >= 3
    assert "14-Day Risk-Free" in proposal["contract"]["contract_title"]


def test_interactive_roi_calculator():
    """Verifies empirical dental ROI unit economics model."""
    calc = ROICalculator.calculate(
        monthly_appointments=200,
        average_treatment_value=1250.0,
        estimated_missed_calls_monthly=18,
        monthly_software_cost=697.0
    )

    losses = calc["unrecovered_losses"]
    assert losses["annual_lost_revenue"] > 40000.0  # Demonstrates significant annual loss

    recapture = calc["projected_recapture"]
    assert recapture["patients_recaptured_monthly"] >= 2
    assert recapture["recaptured_annual_revenue"] > 25000.0

    roi = calc["economic_roi"]
    assert "x" in roi["roi_multiple"]
    assert len(calc["summary_headline"]) > 20


def test_post_sale_client_health_scorecard(clean_db):
    """Verifies retention telemetry, health score, and monthly ROI proof statements for paying clients."""
    client_id = "client-austin-cosmetic-01"
    clean_db.save_client_account({
        "client_id": client_id,
        "clinic_name": "Austin Premier Dental Spa",
        "doctor_name": "Dr. Rachel Ray",
        "plan_tier": "GOLD",
        "monthly_retainer": 997.0,
        "messages_answered": 312,
        "appointments_booked": 38,
        "revenue_generated": 45600.0,
        "patients_recovered": 24,
        "health_score": 98
    })

    dashboard = ClientHealthTracker.get_client_dashboard(clean_db, client_id)
    assert dashboard["clinic_name"] == "Austin Premier Dental Spa"
    assert dashboard["health_score"] == 98
    assert dashboard["health_status"] == "EXCELLENT_RETENTION"
    assert "45,600" in dashboard["monthly_retention_statement"]
    assert "roi_multiple" in dashboard

    # Test metric increment
    incremented = clean_db.log_client_metric(client_id, "appointments_booked", delta=2)
    assert incremented is True
    updated = clean_db.get_client_account(client_id)
    assert updated["appointments_booked"] == 40

    # Test portfolio overview
    overview = ClientHealthTracker.get_portfolio_overview(clean_db)
    assert overview["active_clients_count"] >= 1
    assert overview["portfolio_mrr"] >= 997.0
