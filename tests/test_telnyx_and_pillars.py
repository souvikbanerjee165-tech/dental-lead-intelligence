import pytest
from fastapi.testclient import TestClient
from app import app
from voice_dialer import verify_telnyx_diagnostics
from calendar_sync import CalendarSyncEngine

client = TestClient(app)

def test_verify_telnyx_diagnostics_unconfigured():
    # When no key or mock key
    diag = verify_telnyx_diagnostics("mock_key")
    assert diag["status"] == "unconfigured"
    assert "error" in diag

def test_api_voice_telnyx_verify_endpoint():
    resp = client.get("/api/voice/telnyx/verify")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data

def test_api_telephony_test_telnyx():
    resp = client.post("/api/settings/telephony/test", json={"carrier": "TELNYX"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["carrier"] == "TELNYX"
    assert "message" in data

def test_api_calendar_slots_and_booking():
    # 1. Get Slots
    slot_resp = client.get("/api/calendar/slots?days=3")
    assert slot_resp.status_code == 200
    slot_data = slot_resp.json()
    assert slot_data["status"] == "success"
    assert len(slot_data["slots"]) > 0
    test_slot = slot_data["slots"][0]["slot_key"]

    # 2. Book Slot
    book_resp = client.post("/api/calendar/book", json={
        "lead_id": "test_lead_cal",
        "slot": test_slot,
        "clinic_name": "Test Dental Care",
        "doctor_name": "Dr. Sarah Test",
        "phone": "+15125550199"
    })
    assert book_resp.status_code == 200
    book_data = book_resp.json()
    assert book_data["status"] == "success"
    assert "meet.google.com" in book_data["booking"]["meet_link"]

    # 3. List Bookings
    list_resp = client.get("/api/calendar/bookings")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["bookings"]) >= 1

def test_api_whatsapp_sandbox_turn():
    resp = client.post("/api/whatsapp/turn", json={
        "lead_id": "preview",
        "message": "Hi, I have severe toothache and broken tooth.",
        "clinic_name": "Smile Houston",
        "doctor_name": "Dr. Miller"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "reply" in data
    assert len(data["reply"]) > 5

def test_sales_state_machine_calendar_tool():
    from sales_state_machine import SalesStateMachine, CallState
    lead = {"id": "lead_sm_test", "name": "Dental Clinic", "doctor_name": "Dr. Smith"}
    sm = SalesStateMachine(lead)
    sm.transition_to(CallState.DISCOVERY, reason="Passed gatekeeper")
    sm.transition_to(CallState.PAIN_PROBE, reason="Probing pain")
    sm.transition_to(CallState.DEMO_ASK, reason="Asking for demo")

    # Check availability tool
    avail = sm.execute_tool("check_calendar_availability", {})
    assert avail["success"] is True
    assert "available_slots" in avail

    # Book tool
    sm.transition_to(CallState.BOOKING, reason="Booking slot")
    res = sm.execute_tool("book_calendar_slot", {"slot": "Thursday at 11:00 AM"})
    assert res["success"] is True
    assert res["status"] == "CONFIRMED"
    assert "meet.google.com" in res["meet_link"]

def test_hangup_live_call_atomic_guard():
    from live_dialer_engine import LiveDialerEngine

    # 1. Register active session
    sess = LiveDialerEngine.start_manual_session(
        phone="+15125550199",
        mode="AI_FIRST",
        carrier_mode="TELNYX",
        carrier_call_id="mock_carrier_test_leg",
        dispatch_carrier=False
    )
    assert sess["status"] == "CONNECTED"
    assert sess["carrier_call_id"] == "mock_carrier_test_leg"

    # 2. Call hangup via API with empty payload (testing fallback sweep)
    resp = client.post("/api/voice/call/hangup", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "hung_up"

    # 3. Verify session was marked COMPLETED
    updated = LiveDialerEngine.get_session(sess["session_id"])
    assert updated["status"] == "COMPLETED"

def test_start_manual_session_no_duplicate_dispatch():
    from live_dialer_engine import LiveDialerEngine

    sess = LiveDialerEngine.start_manual_session(
        phone="+15125550188",
        mode="HUMAN_FIRST",
        carrier_mode="TELNYX",
        carrier_call_id="mock_existing_leg_999",
        dispatch_carrier=False
    )
    assert sess["carrier_call_id"] == "mock_existing_leg_999"
    assert sess["status"] == "CONNECTED"
    # Verify indexable by carrier_call_id
    assert LiveDialerEngine.get_session("mock_existing_leg_999") is not None
