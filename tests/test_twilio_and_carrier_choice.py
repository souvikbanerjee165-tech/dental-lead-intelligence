"""
Verification tests for Twilio and Telnyx dual-carrier selection, dispatch routing,
and zero-crash safety fallbacks.
"""

import os
import pytest
from voice_dialer import (
    VoiceDialerEngine,
    get_active_carrier,
    get_twilio_api_key_sid,
    get_twilio_api_key_secret,
    get_telnyx_api_key
)
from settings_manager import SettingsManager
from live_dialer_engine import LiveDialerEngine


def test_carrier_status_reports_dual_options():
    st = VoiceDialerEngine.get_carrier_status()
    assert "active_carrier" in st
    assert st["active_carrier"] in ["TELNYX", "TWILIO", "BROWSER"]
    assert "has_telnyx" in st
    assert "has_twilio" in st
    assert "telnyx_from_phone" in st
    assert "twilio_from_phone" in st
    assert "estimated_cost_per_minute" in st


def test_twilio_credentials_loaded_from_env():
    # Verify the credentials provided by the user are loaded from .env
    key_sid = get_twilio_api_key_sid()
    key_secret = get_twilio_api_key_secret()
    assert key_sid.startswith("SK")
    assert len(key_sid) == 34
    assert bool(key_secret)


def test_settings_manager_carrier_validation():
    current = SettingsManager.get()
    # Valid carrier updates
    SettingsManager.validate_updates(current, {"active_carrier": "TWILIO"})
    SettingsManager.validate_updates(current, {"active_carrier": "TELNYX"})
    SettingsManager.validate_updates(current, {"active_carrier": "BROWSER"})

    # Invalid carrier update must raise ValueError
    with pytest.raises(ValueError, match="Active carrier must be TELNYX, TWILIO, or BROWSER"):
        SettingsManager.validate_updates(current, {"active_carrier": "INVALID_CARRIER"})


def test_twilio_dispatch_graceful_fallback_without_crash():
    lead = {
        "id": "twilio_test_lead",
        "name": "Austin Dental Care",
        "doctor_name": "Dr. Vance",
        "phone": "+15125550199"
    }
    # Dispatches with carrier_override='TWILIO'
    res = VoiceDialerEngine.dispatch_call(lead=lead, carrier_override="TWILIO")
    assert res is not None
    assert "status" in res
    assert res.get("mode") in ["TWILIO_LIVE", "TWILIO_FAILED", "SANDBOX_SIMULATOR"]


def test_live_dialer_manual_session_with_twilio_carrier():
    sess = LiveDialerEngine.start_manual_session(
        phone="+15125550199",
        contact_name="Dr. Vance (Austin Smiles)",
        carrier_mode="TWILIO"
    )
    assert sess is not None
    assert sess["carrier_mode"] == "TWILIO"
    assert sess["status"] == "ACTIVE"
    # End the session cleanly
    fin = LiveDialerEngine.finalize_call_session(sess["session_id"])
    assert fin is not None
    assert fin["status"] == "finalized"
