import pytest
from fastapi.testclient import TestClient
from database import DatabaseManager
from live_dialer_engine import LiveDialerEngine
from app import app, db

client = TestClient(app)


def test_manual_dialer_start_and_phone_lookup(tmp_path):
    db_file = tmp_path / "test_dialer.db"
    test_db = DatabaseManager(db_path=db_file)

    # 1. Insert test clinic with phone
    with test_db._get_connection() as conn:
        conn.execute("""
        INSERT INTO leads (id, name, phone, address, website, category, rating, review_count, opportunity_score, doctor_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "lead_manual_dentist", "Oak Hill Family Dental", "+15125559988", "Austin, TX",
            "https://oakhilldental.com", "Dentist", 4.9, 140, 88, "Dr. Sarah Jenkins"
        ))
        conn.commit()

    # 2. Test lookup by phone
    found = test_db.find_lead_by_phone("5125559988")
    assert found is not None
    assert found["name"] == "Oak Hill Family Dental"
    assert found["doctor_name"] == "Dr. Sarah Jenkins"

    # 3. Test manual dialer start session matching clinic
    session = LiveDialerEngine.start_manual_session(
        phone="(512) 555-9988",
        db=test_db
    )
    assert session["session_id"].startswith("call_man_")
    assert session["clinic_name"] == "Oak Hill Family Dental"
    assert session["doctor_name"] == "Dr. Sarah Jenkins"
    assert session["matched_lead"] is True
    assert session["current_mode"] == "HUMAN_FIRST"
    assert len(session["transcript"]) == 0


def test_real_time_copilot_listening_and_objections(tmp_path):
    db_file = tmp_path / "test_copilot.db"
    test_db = DatabaseManager(db_path=db_file)

    session = LiveDialerEngine.start_manual_session(
        phone="+15125551234",
        contact_name="Capital Dental Studio",
        db=test_db
    )
    sid = session["session_id"]

    # Human opens call
    res1 = LiveDialerEngine.process_live_turn(
        session_id=sid,
        text="Hi, I was calling regarding Dr. Miller's after-hours intake.",
        speaker="HUMAN",
        db=test_db
    )
    assert res1["turn"]["speaker"] == "You (Human Rep)"
    assert res1["talk_ratios"]["rep_pct"] == 100

    # Prospect raises Weave software objection
    res2 = LiveDialerEngine.process_live_turn(
        session_id=sid,
        text="We already use Weave for all our front desk communications and Sunday voicemails.",
        speaker="PROSPECT",
        db=test_db
    )
    hud = res2["copilot_hud"]
    assert hud["detected_objection"] == "Existing Software / Front-Desk Platform"
    assert "Weave" in hud["counter_punch"] or "software" in hud["counter_punch"].lower()
    assert len(hud["buying_signals"]) >= 1  # Sunday / voicemails detected
    assert res2["talk_ratios"]["prospect_pct"] > 0


def test_bidirectional_seamless_takeovers(tmp_path):
    db_file = tmp_path / "test_handoff.db"
    test_db = DatabaseManager(db_path=db_file)

    session = LiveDialerEngine.start_manual_session(
        phone="+15125554321",
        contact_name="Sunset Dental Care",
        db=test_db
    )
    sid = session["session_id"]

    # Ingest prospect turn
    LiveDialerEngine.process_live_turn(
        session_id=sid,
        text="Our receptionist is out sick today and we are completely slammed.",
        speaker="PROSPECT",
        db=test_db
    )

    # 1. Human triggers [AI Takeover]
    ai_takeover = LiveDialerEngine.execute_ai_takeover(
        session_id=sid,
        user_prompt_override="Acknowledge they are busy, offer a quick 60-second video.",
        db=test_db
    )
    assert ai_takeover["status"] == "ai_in_control"
    assert ai_takeover["current_mode"] == "AI_CONTROL"
    assert ai_takeover["reply_text"] != ""
    assert ai_takeover["audio_url"] is not None
    assert ai_takeover["handoff_event"]["to_mode"] == "AI_CONTROL"

    # Check session state
    session_state = LiveDialerEngine.get_session(sid)
    assert session_state["current_mode"] == "AI_CONTROL"
    assert session_state["handoff_count"] == 1

    # 2. Human triggers [Human Takeover] to jump back in
    human_takeover = LiveDialerEngine.execute_human_takeover(
        session_id=sid,
        reason="Doctor answered directly; human rep took over."
    )
    assert human_takeover["status"] == "human_in_control"
    assert human_takeover["current_mode"] == "HUMAN_CONTROL"
    assert human_takeover["handoff_event"]["to_mode"] == "HUMAN_CONTROL"

    session_state = LiveDialerEngine.get_session(sid)
    assert session_state["current_mode"] == "HUMAN_CONTROL"
    assert session_state["handoff_count"] == 2


def test_call_recording_and_closed_loop_learning(tmp_path):
    db_file = tmp_path / "test_learning.db"
    test_db = DatabaseManager(db_path=db_file)

    session = LiveDialerEngine.start_manual_session(
        phone="+15125557777",
        contact_name="Lakeline Dental Center",
        db=test_db
    )
    sid = session["session_id"]

    # Conversation sequence
    LiveDialerEngine.process_live_turn(sid, "Hi! I wanted to check how you handle after hours patient requests.", "HUMAN", db=test_db)
    LiveDialerEngine.process_live_turn(sid, "We actually do miss some calls on Sunday. Could we do a quick Zoom on Thursday at 11 AM?", "PROSPECT", db=test_db)
    LiveDialerEngine.process_live_turn(sid, "Thursday at 11 AM works perfect. I will lock that into the calendar right now!", "HUMAN", db=test_db)

    # Finalize call session
    final = LiveDialerEngine.finalize_call_session(
        session_id=sid,
        duration_sec=78,
        db=test_db
    )
    assert final["status"] == "finalized"
    assert final["outcome"] == "MEETING_BOOKED"
    assert final["duration_sec"] == 78
    assert len(final["learnings"]["winning_angles"]) > 0

    # Verify saved in SQLite table call_recordings
    rec = test_db.get_call_recording(sid)
    assert rec is not None
    assert rec["call_id"] == sid
    assert rec["outcome"] == "MEETING_BOOKED"
    assert rec["duration_sec"] == 78
    assert len(rec["transcript"]) == 3

    # Verify Knowledge Base was automatically enriched with winning insight
    kb_insights = test_db.get_knowledge_base_insights(limit=10)
    assert len(kb_insights) > 0
    assert any("Lakeline" in k["key_phrase"] or "Thursday" in k["key_phrase"] or "Software" in k["key_phrase"] for k in kb_insights)


def test_api_manual_dialer_endpoints():
    # 1. Lookup phone
    lookup_res = client.post("/api/dialer/lookup-phone", json={"phone": "512-555-0100"})
    assert lookup_res.status_code == 200

    # 2. Start manual dialer session
    start_res = client.post("/api/dialer/manual/start", json={
        "phone": "+15125556789",
        "contact_name": "API Test Dental",
        "mode": "HUMAN_FIRST"
    })
    assert start_res.status_code == 200
    data = start_res.json()
    sid = data["session_id"]
    assert "call_man_" in sid

    # 3. Ingest turn
    turn_res = client.post("/api/dialer/manual/turn", json={
        "session_id": sid,
        "text": "Hello, we already use Podium for reviews and texting.",
        "speaker": "PROSPECT"
    })
    assert turn_res.status_code == 200
    t_data = turn_res.json()
    assert "copilot_hud" in t_data
    assert t_data["copilot_hud"]["detected_objection"] is not None

    # 4. AI Takeover
    ai_res = client.post("/api/dialer/manual/ai-takeover", json={
        "session_id": sid,
        "user_hint": "Explain that we supplement Podium after hours."
    })
    assert ai_res.status_code == 200
    ai_data = ai_res.json()
    assert ai_data["current_mode"] == "AI_CONTROL"
    assert ai_data["reply_text"] != ""

    # 5. Human Takeover
    human_res = client.post("/api/dialer/manual/human-takeover", json={
        "session_id": sid,
        "reason": "Human rep took over"
    })
    assert human_res.status_code == 200
    assert human_res.json()["current_mode"] == "HUMAN_CONTROL"

    # 6. Finalize session
    fin_res = client.post("/api/dialer/manual/finalize", json={
        "session_id": sid,
        "duration_sec": 65,
        "outcome": "INTERESTED"
    })
    assert fin_res.status_code == 200
    fin_data = fin_res.json()
    assert fin_data["status"] == "finalized"

    # 7. List recordings
    rec_res = client.get("/api/dialer/recordings")
    assert rec_res.status_code == 200
    rec_list = rec_res.json()["recordings"]
    assert any(r["call_id"] == sid for r in rec_list)

    # 8. Single recording retrieval
    single_res = client.get(f"/api/dialer/recordings/{sid}")
    assert single_res.status_code == 200
    assert single_res.json()["call_id"] == sid
