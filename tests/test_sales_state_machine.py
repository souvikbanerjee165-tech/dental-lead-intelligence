import pytest
from sales_state_machine import SalesStateMachine, CallState, DeepSeekIntelligenceEngine
from database import DatabaseManager

TEST_DB_PATH = "test_sales_state_machine.db"

@pytest.fixture
def clean_db():
    db = DatabaseManager(db_path=TEST_DB_PATH)
    # Clear test table
    with db._get_connection() as conn:
        conn.execute("DELETE FROM sales_memory WHERE lead_id = 'test_lead_sdr'")
        conn.execute("DELETE FROM leads WHERE id = 'test_lead_sdr'")
        conn.execute("""
        INSERT INTO leads (id, name, doctor_name, phone, stage)
        VALUES ('test_lead_sdr', 'Lone Star Smiles', 'Dr. Adams', '+15125550199', 'FOUND')
        """)
        conn.commit()
    yield db
    # Cleanup
    with db._get_connection() as conn:
        conn.execute("DELETE FROM sales_memory WHERE lead_id = 'test_lead_sdr'")
        conn.execute("DELETE FROM leads WHERE id = 'test_lead_sdr'")
        conn.commit()

def test_state_machine_initialization(clean_db):
    lead = {"id": "test_lead_sdr", "name": "Lone Star Smiles", "doctor_name": "Dr. Adams"}
    sm = SalesStateMachine(lead=lead, db=clean_db)

    assert sm.current_state == CallState.INTRO
    assert not sm.is_terminal
    instructions = sm.get_state_prompt_instructions()
    assert "Alex" in instructions
    assert "AI sales assistant" in instructions
    assert "Lone Star Smiles" in instructions

def test_state_machine_flow_to_booking(clean_db):
    lead = {"id": "test_lead_sdr", "name": "Lone Star Smiles", "doctor_name": "Dr. Adams"}
    sm = SalesStateMachine(lead=lead, db=clean_db)

    # 1. Receptionist answers
    res1 = sm.process_prospect_input("Hello, thanks for calling Lone Star Smiles, this is Mary at the front desk.")
    assert sm.current_state == CallState.GATEKEEPER

    # 2. Gatekeeper transfers to office manager
    res2 = sm.process_prospect_input("One moment, I can transfer you to our office manager.")
    assert sm.current_state == CallState.DISCOVERY

    # 3. Manager admits after-hours weakness
    res3 = sm.process_prospect_input("When we are closed, calls just go to our voicemail.")
    assert sm.current_state == CallState.PAIN_PROBE

    # 4. Pain probe automatically transitions to Value Offer
    res4 = sm.process_prospect_input("Right, and emergency patients just hang up.")
    assert sm.current_state == CallState.VALUE_OFFER

    # 5. Value offer leads to Demo Ask
    res5 = sm.process_prospect_input("Tell me more about how that works.")
    assert sm.current_state == CallState.DEMO_ASK

    # 6. Agrees to meeting
    res6 = sm.process_prospect_input("Sure, Thursday morning works great.")
    assert sm.current_state == CallState.BOOKING or sm.current_state == CallState.TERMINATED
    assert sm.outcome == "MEETING_BOOKED"

def test_tool_gating_security(clean_db):
    lead = {"id": "test_lead_sdr", "name": "Lone Star Smiles", "doctor_name": "Dr. Adams"}
    sm = SalesStateMachine(lead=lead, db=clean_db)

    # While in INTRO state, calendar booking tool MUST fail
    tool_res = sm.execute_tool("book_calendar_slot", {"slot": "Tomorrow at 10 AM"})
    assert not tool_res["success"]
    assert "not permitted" in tool_res["error"]

    # Transition to BOOKING state via transition_to
    sm.current_state = CallState.DEMO_ASK
    sm.transition_to(CallState.BOOKING, reason="Agreed to book")

    # In BOOKING state, tool is allowed
    tool_res_ok = sm.execute_tool("book_calendar_slot", {"slot": "Friday 1:00 PM"})
    assert tool_res_ok["success"]
    assert sm.booked_slot == "Friday 1:00 PM"
    assert sm.outcome == "MEETING_BOOKED"

def test_dnc_immediate_exit_and_compliance(clean_db):
    lead = {"id": "test_lead_sdr", "name": "Lone Star Smiles", "doctor_name": "Dr. Adams"}
    sm = SalesStateMachine(lead=lead, db=clean_db)

    res = sm.process_prospect_input("Do not call this number again!")
    assert sm.current_state == CallState.DNC_EXIT
    assert sm.is_terminal
    assert sm.outcome == "DO_NOT_CALL"
    assert "taking your practice off our list" in res["reply"].lower()

    # Verify DB marked as LOST / DNC
    updated_lead = clean_db.get_lead("test_lead_sdr")
    assert updated_lead["stage"] == "LOST"
    assert "DNC" in updated_lead.get("notes", "")

def test_graceful_exit_when_practice_closing(clean_db):
    lead = {"id": "test_lead_sdr", "name": "Lone Star Smiles", "doctor_name": "Dr. Adams"}
    sm = SalesStateMachine(lead=lead, db=clean_db)

    res = sm.process_prospect_input("Dr. Adams is retiring and we are shutting down the clinic next month.")
    assert sm.current_state == CallState.GRACEFUL_EXIT
    assert sm.is_terminal
    assert "appreciate your time" in res["reply"].lower()

def test_deepseek_pre_and_post_call_intelligence(clean_db, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    lead = {"id": "test_lead_sdr", "name": "Lone Star Smiles", "doctor_name": "Dr. Adams"}

    # Pre-call synthesis
    intel = DeepSeekIntelligenceEngine.generate_pre_call_intelligence(lead)
    assert len(intel["likely_pain_points"]) >= 2
    assert "opening_angle" in intel
    assert len(intel["discovery_questions"]) >= 3

    # Post-call transcript evaluation
    transcript = [
        {"speaker": "Prospect", "text": "We already have a front desk team."},
        {"speaker": "AI", "text": "They do a great job, but what happens when you are closed on Sunday?"},
        {"speaker": "Prospect", "text": "That's true, we miss those calls."}
    ]
    eval_res = DeepSeekIntelligenceEngine.evaluate_post_call(transcript, outcome="MEETING_BOOKED", db=clean_db)
    assert "objection_detected" in eval_res
    assert "better_response_recommendation" in eval_res
