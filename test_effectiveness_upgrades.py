"""
Focused integration & unit tests for the 3 high-ROI platform upgrades:
1. Carrier Reputation Shield (DNC, area-code matching, throttling) + TeXML Auth & Switchboard Sync
2. Cal.com Booking Webhook + Instant Cooldown-Guarded Speed-to-Lead Rep Alert
3. Deep Headless Extraction Fallback in WebsiteAuditor + Verified Telnyx AMD Mystery Shopper Probes
"""

import os
import hmac
import json
import time
import base64
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient

import app as app_module
from database import DatabaseManager
from models import RawLead
from crm import CRMStage
from auditor import WebsiteAuditor
from mystery_shopper import MysteryShopperAuditor
from carrier_reputation_manager import CarrierReputationManager
from voice_dialer import VoiceDialerEngine
from ai_door_opener import AIDoorOpenerEngine
from multiline_switchboard import switchboard_engine
from live_intercept import LiveInterceptRadar


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Provides an isolated temporary SQLite database patched into app_module."""
    db_file = tmp_path / "test_dental_upgrades.db"
    test_db = DatabaseManager(db_path=str(db_file))
    monkeypatch.setattr(app_module, "db", test_db)
    # Reset switchboard lines & radar cooldowns cleanly per test
    for ch in switchboard_engine.channels.values():
        ch.status = "completed"
        ch.transcript = []
        ch.call_control_id = None
        ch.context_briefing_card = None
    switchboard_engine._call_id_to_line.clear()
    LiveInterceptRadar._active_viewers.clear()
    LiveInterceptRadar._alert_cooldowns.clear()
    return test_db


def _seed_sample_lead(db: DatabaseManager, lead_id: str = "lead_test_001") -> dict:
    with db._get_connection() as conn:
        conn.execute(
            """
            INSERT INTO leads (
                id, name, phone, website, address, rating, review_count,
                stage, contact_status, opportunity_score, doctor_name, direct_emails
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lead_id,
                "Bright Smile Austin",
                "+1 (512) 555-8899",
                "https://brightsmileaustin.example.com",
                "400 Congress Ave, Austin, TX 78701",
                4.8,
                142,
                "SENT",
                "CONTACTED",
                88,
                "Dr. Elena Vance",
                "dr.vance@brightsmileaustin.example.com",
            ),
        )
        conn.commit()
    return db.get_lead(lead_id)


# ---------------------------------------------------------------------------
# Improvement 1: Carrier Compliance + TeXML Signature + Switchboard Sync
# ---------------------------------------------------------------------------


def test_carrier_reputation_area_code_dnc_and_throttle(isolated_db, monkeypatch):
    monkeypatch.setenv("CALLER_ID_POOL", "+12145550101,+15125550202")
    monkeypatch.setenv("TELNYX_API_KEY", "test_key")
    monkeypatch.setenv("TELNYX_CONNECTION_ID", "conn_test")

    lead = _seed_sample_lead(isolated_db)
    mgr = CarrierReputationManager(db=isolated_db)

    # Local presence area code match for Austin 512
    assert mgr.match_local_caller_id("+15125558899") == "+15125550202"

    # DNC blocks BOTH VoiceDialerEngine.dispatch_call and AIDoorOpenerEngine.dispatch_telnyx_sms
    isolated_db.add_to_dnc("+15125558899", "Bright Smile Austin", "PROSPECT_REQUESTED")
    voice_res = VoiceDialerEngine.dispatch_call(lead=lead, to_phone="+15125558899", db=isolated_db)
    assert voice_res["blocked"] is True
    assert voice_res["status"] == "blocked"
    assert "DNC_BLACKLISTED" in voice_res["reason"]

    import asyncio
    sms_res = asyncio.run(
        AIDoorOpenerEngine.dispatch_telnyx_sms("+15125558899", "Hello", lead_id=lead["id"], db=isolated_db)
    )
    assert sms_res["blocked"] is True
    assert "DNC_BLACKLISTED" in sms_res["reason"]

    # Hourly velocity throttling at MAX_CALLS_PER_HOUR_PER_NUMBER (18)
    for _ in range(CarrierReputationManager.MAX_CALLS_PER_HOUR_PER_NUMBER):
        mgr.log_call_attempt("+15125550202", "+15125559999", lead_id=lead["id"])
    throttled_res = VoiceDialerEngine.dispatch_call(lead=lead, to_phone="+15125557777", db=isolated_db)
    assert throttled_res["blocked"] is True
    assert "VELOCITY_THROTTLED" in throttled_res["reason"]


def test_texml_ed25519_verification_and_switchboard_sync(isolated_db, monkeypatch):
    priv = Ed25519PrivateKey.generate()
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    monkeypatch.setenv("TELNYX_PUBLIC_KEY", base64.b64encode(pub_bytes).decode("utf-8"))
    monkeypatch.setenv("STRICT_WEBHOOK_VERIFY", "true")

    client = TestClient(app_module.app)

    # 1. Unsigned / invalid signature rejected cleanly with 403
    bad_resp = client.post("/telnyx/inbound", data={"CallControlId": "call_bad", "From": "+15125551111"})
    assert bad_resp.status_code == 403

    def _signed_headers(body_bytes: bytes) -> dict:
        ts = str(int(time.time()))
        sig = base64.b64encode(priv.sign(f"{ts}|".encode("utf-8") + body_bytes)).decode("utf-8")
        return {
            "telnyx-timestamp": ts,
            "telnyx-signature-ed25519": sig,
            "Content-Type": "application/x-www-form-urlencoded",
        }

    # 2. Valid signed /telnyx/inbound registers PSTN line on Switchboard
    in_body = b"CallControlId=call_pstn_01&From=%2B15125551234&CallerName=John+Doe"
    ok_in = client.post("/api/v1/voice/telnyx/inbound", content=in_body, headers=_signed_headers(in_body))
    assert ok_in.status_code == 200
    assert "<Gather" in ok_in.text
    assert switchboard_engine.get_line_for_call("call_pstn_01") is not None

    # 3. Routine/Billing speech produces empathetic patient speech (not raw internal EDI directive)
    bill_body = b"CallControlId=call_pstn_01&From=%2B15125551234&SpeechResult=What+is+my+copay+or+insurance+deductible"
    ok_bill = client.post("/api/v1/voice/telnyx/respond", content=bill_body, headers=_signed_headers(bill_body))
    assert ok_bill.status_code == 200
    assert "EDI 271" not in ok_bill.text
    assert "benefits" in ok_bill.text.lower() or "insurance" in ok_bill.text.lower()

    # 4. Urgent speech updates switchboard triage and initiates warm transfer + Context Briefing Card
    urg_body = b"CallControlId=call_pstn_01&From=%2B15125551234&SpeechResult=I+have+severe+throbbing+pain+and+broken+tooth"
    ok_urg = client.post("/api/v1/voice/telnyx/respond", content=urg_body, headers=_signed_headers(urg_body))
    assert ok_urg.status_code == 200
    assert "<Dial" in ok_urg.text
    line_id = switchboard_engine.get_line_for_call("call_pstn_01")
    line_data = switchboard_engine.get_line(line_id)
    assert line_data["status"] == "warm_transfer_pending"
    assert line_data["triage_category"] == "EMERGENCY_URGENT"
    assert line_data["context_briefing_card"] is not None


def test_telnyx_transcript_opt_out_adds_dnc(isolated_db, monkeypatch):
    monkeypatch.setenv("STRICT_WEBHOOK_VERIFY", "false")
    lead = _seed_sample_lead(isolated_db)
    client = TestClient(app_module.app)

    cs = base64.b64encode(json.dumps({
        "lead_id": lead["id"],
        "name": lead["name"],
        "phone": "+15125558899",
        "initial_mode": "AI_FIRST",
    }).encode()).decode()

    payload = {
        "data": {
            "event_type": "call.transcription",
            "payload": {
                "call_control_id": "cc_optout_01",
                "client_state": cs,
                "transcription_data": {"transcript": "Please remove my number and stop calling", "is_final": True},
            },
        }
    }
    with patch("voice_dialer.send_telnyx_speak") as mock_speak:
        resp = client.post("/api/voice/webhook/telnyx", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "dnc_opt_out_processed"
        mock_speak.assert_called_once()
        assert isolated_db.is_dnc_phone("+15125558899") is True


# ---------------------------------------------------------------------------
# Improvement 2: Cal.com Webhook & Speed-to-Lead Rep Alert
# ---------------------------------------------------------------------------


def test_calcom_webhook_signature_stage_and_cancellation(isolated_db, monkeypatch):
    monkeypatch.setenv("CAL_COM_WEBHOOK_SECRET", "cal_secret_123")
    lead = _seed_sample_lead(isolated_db)
    client = TestClient(app_module.app)

    created_payload = {
        "triggerEvent": "BOOKING_CREATED",
        "payload": {
            "uid": "cal_uid_999",
            "startTime": "2026-11-20T16:00:00Z",
            "responses": {
                "name": "Dr. Elena Vance",
                "email": "personal@gmail.com",
                "notes": f"Practice: Bright Smile Austin [LeadID:{lead['id']}]",
            },
        },
    }
    raw = json.dumps(created_payload).encode("utf-8")

    # Invalid signature must return 403
    bad = client.post("/api/webhooks/calcom", content=raw, headers={"X-Cal-Signature-256": "deadbeef", "Content-Type": "application/json"})
    assert bad.status_code == 403

    valid_sig = "sha256=" + hmac.new(b"cal_secret_123", raw, hashlib.sha256).hexdigest()
    ok = client.post("/api/webhooks/calcom", content=raw, headers={"X-Cal-Signature-256": valid_sig, "Content-Type": "application/json"})
    assert ok.status_code == 200
    data = ok.json()
    assert data["matched_lead_id"] == lead["id"]

    updated = isolated_db.get_lead(lead["id"])
    assert updated["stage"] == CRMStage.MEETING.value
    assert updated["contact_status"] == "BOOKED"
    assert updated["cadence_status"] == "PAUSED_BOOKED"

    # Cancellation resumes cadence
    cancel_raw = json.dumps({
        "triggerEvent": "BOOKING_CANCELLED",
        "payload": {
            "uid": "cal_uid_999",
            "responses": {"email": "dr.vance@brightsmileaustin.example.com"},
        },
    }).encode("utf-8")
    cancel_sig = hmac.new(b"cal_secret_123", cancel_raw, hashlib.sha256).hexdigest()
    c_resp = client.post("/api/webhooks/calcom", content=cancel_raw, headers={"X-Cal-Signature-256": cancel_sig, "Content-Type": "application/json"})
    assert c_resp.status_code == 200
    reopened = isolated_db.get_lead(lead["id"])
    assert reopened["cadence_status"] == "ACTIVE"


def test_pitch_viewed_dispatches_rep_alert_with_cooldown(isolated_db, monkeypatch):
    monkeypatch.setenv("REP_ALERT_PHONE", "+15125550009")
    monkeypatch.setenv("REP_ALERT_COOLDOWN_SECONDS", "900")
    lead = _seed_sample_lead(isolated_db)
    client = TestClient(app_module.app)

    mock_sms = AsyncMock(return_value={"success": True, "message_id": "msg_rep_1"})
    with patch.object(AIDoorOpenerEngine, "dispatch_telnyx_sms", mock_sms):
        r1 = client.post(f"/api/pitch/{lead['id']}/viewed")
        assert r1.status_code == 200
        # Repeat view immediately after must be suppressed by cooldown
        r2 = client.post(f"/api/pitch/{lead['id']}/viewed")
        assert r2.status_code == 200

    assert mock_sms.await_count == 1
    assert mock_sms.call_args.kwargs["to_phone"] == "+15125550009"
    assert mock_sms.call_args.kwargs["bypass_compliance"] is True
    assert mock_sms.call_args.kwargs["is_internal_alert"] is True


# ---------------------------------------------------------------------------
# Improvement 3: Deep Headless Fallback & Real Verified Mystery Shopper Probes
# ---------------------------------------------------------------------------


def test_auditor_triggers_headless_fallback_on_sparse_spa_dom():
    auditor = WebsiteAuditor(timeout=5.0)
    sparse_html = "<html><head><title>Austin Dental</title></head><body><div id='root'></div></body></html>"

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.text = sparse_html
    fake_resp.url = "https://example-dental.com"
    fake_resp.headers = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def get(self, url):
            return fake_resp

    deep_profile_mock = MagicMock(
        primary_doctor="Dr. Maya Patel, DDS",
        doctors=["Dr. Maya Patel, DDS"],
        has_online_booking=True,
        detected_booking_tool="Nexhealth",
        has_ai_chat=True,
        detected_chat_tool="Podium",
        phone="(512) 555-3434",
        after_hours_policy="Directs after-hours callers to voicemail",
    )

    import asyncio
    with patch("auditor.httpx.AsyncClient", FakeClient), \
         patch("security.validate_external_url", return_value=(True, "OK")), \
         patch("clinic_researcher.ClinicResearcher.extract_deep_clinic_profile", AsyncMock(return_value=deep_profile_mock)) as mock_deep:
        result, graph, _ = asyncio.run(auditor._crawl_and_analyze("https://example-dental.com"))

    mock_deep.assert_awaited_once()
    assert result.doctor_name == "Dr. Maya Patel, DDS"
    assert result.has_online_booking is True
    assert result.detected_booking_tool == "Nexhealth"
    assert result.has_ai_chatbot is True
    assert any(e.evidence_type == "headless_dom_extraction" for e in graph.evidence)


def test_mystery_shopper_separates_benchmark_and_verified_telnyx_probe(isolated_db, monkeypatch):
    monkeypatch.setenv("STRICT_WEBHOOK_VERIFY", "false")
    lead = _seed_sample_lead(isolated_db)
    client = TestClient(app_module.app)

    # 1. GET before any live call returns explicit unverified market benchmark
    b_resp = client.get(f"/api/leads/{lead['id']}/mystery-audit")
    assert b_resp.status_code == 200
    b_data = b_resp.json()
    assert b_data["verified"] is False
    assert b_data["status"] == "BENCHMARK_ESTIMATE"
    assert b_data["verification_status"] == "UNVERIFIED_BENCHMARK"

    # 2. Trigger live probe (mock VoiceDialerEngine.dispatch_call) -> PROBE_PENDING
    with patch.object(VoiceDialerEngine, "dispatch_call", return_value={
        "status": "initiated", "mode": "TELNYX_LIVE", "call_id": "cc_probe_77"
    }):
        p_resp = client.post(f"/api/leads/{lead['id']}/mystery-shop", json={"live_probe": True})
    assert p_resp.status_code == 200
    p_data = p_resp.json()
    assert p_data["verification_status"] == "PROBE_PENDING"
    assert p_data["call_control_id"] == "cc_probe_77"

    # 3. Simulated Telnyx AMD machine webhook verifies probe, hangs up immediately, and persists to DB
    cs = base64.b64encode(json.dumps({
        "probe_type": "mystery_shopper",
        "probe_started_ms": int(time.time() * 1000) - 18000,
        "lead_id": lead["id"],
        "name": lead["name"],
        "doctor_name": lead["doctor_name"],
        "phone": "+15125558899",
    }).encode()).decode()

    amd_webhook = {
        "data": {
            "event_type": "call.machine.detection.ended",
            "payload": {
                "call_control_id": "cc_probe_77",
                "result": "machine",
                "client_state": cs,
            },
        }
    }
    with patch("voice_dialer.hangup_telnyx_call") as mock_hangup, \
         patch("voice_dialer.send_telnyx_speak") as mock_speak:
        w_resp = client.post("/api/voice/webhook/telnyx", json=amd_webhook)
        assert w_resp.status_code == 200
        assert w_resp.json()["status"] == "probe_verified"
        mock_hangup.assert_called_once_with("cc_probe_77")
        mock_speak.assert_not_called()

    persisted = client.get(f"/api/leads/{lead['id']}/mystery-audit").json()
    assert persisted["verified"] is True
    assert persisted["verification_method"] == "TELNYX_AMD_LIVE_PROBE"
    assert persisted["status"] == "CONFIRMED_PHONE_FRICTION"
    assert persisted["amd_result"] == "machine"
