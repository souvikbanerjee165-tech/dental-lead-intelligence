import pytest
from fastapi.testclient import TestClient
from app import app, db
from timeline import OpportunityTimelineManager, TimelineEvent
from simulator import AICallSimulator, SimulatorTurnResponse
from scheduler import AutonomousScheduler

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_lead():
    # Insert or update a clean test practice
    test_id = "lead_test_moat_practice"
    with db._get_connection() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO leads (id, name, phone, address, website, category, rating, review_count, first_seen, buying_probability, opportunity_score, expected_value)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_id, "Sunset Valley Dental", "5125559876", "Austin, TX", "https://sunsetvalleydental.com",
            "Dentist", 4.8, 185, "2026-09-01T08:00:00", 80, 85, 3183.20
        ))
        conn.commit()
    yield test_id

def test_opportunity_timeline_logging_and_retrieval(setup_test_lead):
    lead_id = setup_test_lead

    # 1. Log explicit timeline event
    log_id = OpportunityTimelineManager.log_event(
        db=db,
        lead_id=lead_id,
        event_type="STACK_CHANGE",
        title="Removed Legacy Contact Form",
        description="Site updated; patient contact form dropped from footer.",
        actor="AI_MONITOR",
        metadata={"prior_tech": "ContactForm7"}
    )
    assert log_id > 0

    # 2. Retrieve unified timeline
    timeline = OpportunityTimelineManager.get_unified_timeline(db=db, lead_id=lead_id)
    assert len(timeline) >= 1
    event_titles = [e["title"] for e in timeline]
    assert any("Removed Legacy Contact Form" in t for t in event_titles)
    # Check FIRST_DISCOVERED was synthesized from lead.first_seen
    assert any("Discovered on Google Maps" in t for t in event_titles)

def test_timeline_integration_with_calls_and_stage_shifts(setup_test_lead):
    lead_id = setup_test_lead

    # 1. Log a phone call outcome
    call_log_id = db.log_call_outcome(
        lead_id=lead_id,
        outcome="INTERESTED",
        rep_notes="Spoke with Dr. Sunset; excited about after-hours emergency bookings.",
        duration_sec=145
    )
    assert call_log_id > 0

    # 2. Advance CRM Stage
    db.update_lead_stage(lead_id, new_stage="MEETING", notes="Scheduled demo for Thursday at 12:30 PM")

    # 3. Add a sales note
    db.add_lead_note(lead_id, note_text="Targeting $497/mo retainer package.")

    # 4. Fetch unified timeline
    timeline = db.get_lead_timeline(lead_id)
    event_types = [e["event_type"] for e in timeline]

    assert "CALL_LOGGED" in event_types
    assert "STAGE_TRANSITION" in event_types
    assert "NOTE_ADDED" in event_types

def test_expected_value_financial_prioritization(setup_test_lead):
    lead_id = setup_test_lead

    # Update qualification with 90% buying probability
    db.update_lead_qualification(
        lead_id=lead_id,
        buying_probability=90,
        should_call="YES",
        pain_level="CRITICAL",
        practice_type="INDEPENDENT_OWNER",
        decision_accessibility="DIRECT_DOCTOR",
        buying_triggers=["Critical missed weekend emergency volume"],
        sales_verdict="Immediate A-tier priority call."
    )

    lead = db.get_lead(lead_id)
    # $EV = 3979.0 * (90 / 100) = $3,581.10
    assert lead["expected_value"] == 3581.10

    # Fetch Top EV Queue
    queue = db.get_top_ev_queue(limit=10)
    assert len(queue) > 0
    # Leads should be sorted descending by expected_value
    for i in range(len(queue) - 1):
        assert (queue[i].get("expected_value") or 0) >= (queue[i+1].get("expected_value") or 0)

def test_ai_call_simulator_personas_and_turns(setup_test_lead):
    lead_dict = {
        "id": setup_test_lead,
        "name": "Sunset Valley Dental",
        "doctor_name": "Dr. Vance",
        "annual_gap": 48000
    }

    # 1. Start Session as Gatekeeper
    gk_session = AICallSimulator.start_session(lead_dict, persona="GATEKEEPER_RECEPTIONIST")
    assert gk_session["persona"] == "GATEKEEPER_RECEPTIONIST"
    assert "Front Desk" in gk_session["speaker_name"]
    assert "Sunset Valley Dental" in gk_session["initial_message"]

    # 2. Start Session as Busy Doctor
    doc_session = AICallSimulator.start_session(lead_dict, persona="BUSY_DOCTOR")
    assert doc_session["persona"] == "BUSY_DOCTOR"
    assert "Dr. Vance" in doc_session["speaker_name"]
    assert "Make it quick" in doc_session["initial_message"]

    # 3. Simulate high-performing turn
    high_pitch = "Dr. Vance, I noticed you have over 180 reviews but no 24/7 online booking. When an emergency patient calls at 8 PM with a cracked molar, who captures them today?"
    turn_res = AICallSimulator.simulate_turn(
        lead_dict=lead_dict,
        persona="BUSY_DOCTOR",
        conversation_history=doc_session["history"],
        user_pitch=high_pitch
    )
    assert isinstance(turn_res, SimulatorTurnResponse)
    assert turn_res.evaluation.hook_score >= 7
    assert turn_res.evaluation.value_score >= 8
    assert turn_res.evaluation.overall_score >= 7
    assert turn_res.evaluation.tactical_feedback != ""
    assert turn_res.evaluation.suggested_pivot != ""

def test_api_timeline_and_simulator_endpoints(setup_test_lead):
    lead_id = setup_test_lead

    # Test GET /api/leads/{id}/timeline
    res = client.get(f"/api/leads/{lead_id}/timeline")
    assert res.status_code == 200
    data = res.json()
    assert "events" in data
    assert data["lead_id"] == lead_id

    # Test POST /api/leads/{id}/timeline
    post_res = client.post(f"/api/leads/{lead_id}/timeline", json={
        "event_type": "NOTE_ADDED",
        "title": "Custom Test Milestone",
        "description": "Founder checked website after-hours behavior.",
        "actor": "SALES_REP"
    })
    assert post_res.status_code == 200
    assert post_res.json()["status"] == "success"

    # Test POST /api/leads/{id}/simulate-call/start
    sim_start = client.post(f"/api/leads/{lead_id}/simulate-call/start", json={
        "persona": "GATEKEEPER_RECEPTIONIST"
    })
    assert sim_start.status_code == 200
    sim_data = sim_start.json()
    assert "initial_message" in sim_data

    # Test POST /api/leads/{id}/simulate-call/turn
    sim_turn = client.post(f"/api/leads/{lead_id}/simulate-call/turn", json={
        "persona": "GATEKEEPER_RECEPTIONIST",
        "user_pitch": "Hi Sarah, could you help me for 10 seconds? I had a quick question regarding Dr. Vance's after-hours patient inquiries.",
        "history": sim_data.get("history", [])
    })
    assert sim_turn.status_code == 200
    turn_data = sim_turn.json()
    assert "evaluation" in turn_data
    assert "overall_score" in turn_data["evaluation"]

    # Test GET /api/queue/top-ev
    ev_res = client.get("/api/queue/top-ev")
    assert ev_res.status_code == 200
    ev_data = ev_res.json()
    assert isinstance(ev_data, list)
    if len(ev_data) > 0:
        assert "expected_value" in ev_data[0]

    # Test GET /api/scheduler/daemon and toggle
    daemon_status = client.get("/api/scheduler/daemon")
    assert daemon_status.status_code == 200
    assert "running" in daemon_status.json()

    # Toggle daemon
    toggle_res = client.post("/api/scheduler/daemon/toggle", json={
        "enable": False
    })
    assert toggle_res.status_code == 200
    assert toggle_res.json()["running"] is False
