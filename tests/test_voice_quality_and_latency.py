import os
import pytest
from live_dialer_engine import LiveDialerEngine
from empathy_voice_prompts import EmpathyVoicePromptEngine
from voice_dialer import normalize_speech_text_for_human_voice, INSTANT_FILLERS, generate_google_cloud_tts_mp3


def test_speech_normalization():
    raw = "Hi Dr. Miller! Cost is $1,500 setup and $399/mo. We connect to your EHR at 11:00 AM."
    cleaned = normalize_speech_text_for_human_voice(raw)
    assert "fifteen hundred dollars" in cleaned
    assert "three ninety-nine a month" in cleaned
    assert "Doctor" in cleaned
    assert "eleven A-M" in cleaned


def test_acoustic_fillers_exist():
    assert len(INSTANT_FILLERS) >= 6
    for f in INSTANT_FILLERS:
        assert "audio_url" in f
        assert "text" in f
        # Verify file exists on disk
        local_path = f["audio_url"].lstrip("/")
        assert os.path.exists(local_path), f"Missing filler audio file: {local_path}"


def test_dynamic_objection_variation_matrix():
    dossier = {"doctor_display": "Dr. Vance", "clinic_name": "Austin Smiles", "city": "Austin"}
    rebuttals = []
    for i in range(4):
        r = EmpathyVoicePromptEngine.get_empathy_rebuttal("doctor_busy", dossier, used_phrases=rebuttals)
        assert r not in rebuttals, f"Duplicate rebuttal generated on turn {i+1}: {r}"
        rebuttals.append(r)


def test_multi_turn_live_dialer_anti_repetition():
    sess = LiveDialerEngine.start_manual_session(phone="+15125550199", contact_name="Dr. Vance (Austin Smiles)")
    sid = sess["session_id"]

    prospect_turns = [
        "Good morning, Austin Smiles, how can I help you?",
        "Dr. Vance is in surgery with a patient right now.",
        "Just send an email to info@austinsmiles.com.",
        "How much does this setup cost?"
    ]

    ai_replies = []
    for turn in prospect_turns:
        LiveDialerEngine.process_live_turn(sid, text=turn, speaker="PROSPECT")
        ans = LiveDialerEngine.execute_ai_takeover(sid)
        reply = ans["reply_text"]
        assert reply not in ai_replies, f"Repetition detected! AI repeated: '{reply}'"
        assert len(reply.split()) <= 26, f"Reply exceeded conversational brevity limit: '{reply}'"
        assert ans.get("filler_audio_url"), "Expected instant filler audio url to be returned"
        ai_replies.append(reply)


if __name__ == "__main__":
    test_speech_normalization()
    test_acoustic_fillers_exist()
    test_dynamic_objection_variation_matrix()
    test_multi_turn_live_dialer_anti_repetition()
    print("ALL TESTS PASSED SUCCESSFULLY!")
