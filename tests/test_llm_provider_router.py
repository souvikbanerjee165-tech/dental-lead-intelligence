import pytest
import time
from llm_router import (
    LLMRouter,
    ProviderHealthState,
    ProviderHealthTracker,
    GeminiLiveProvider,
    OpenAIRealtimeProvider,
    ModularKokoroProvider,
    VoiceModelBenchmark
)
from database import DatabaseManager

TEST_DB_PATH = "test_llm_benchmarks.db"

@pytest.fixture
def clean_db():
    db = DatabaseManager(db_path=TEST_DB_PATH)
    with db._get_connection() as conn:
        conn.execute("DELETE FROM model_performance")
        conn.commit()
    yield db
    with db._get_connection() as conn:
        conn.execute("DELETE FROM model_performance")
        conn.commit()

def test_provider_health_tracker_state_transitions():
    tracker = ProviderHealthTracker("TEST_GEMINI")
    assert tracker.state == ProviderHealthState.AVAILABLE
    assert tracker.is_usable()

    # Record 429 with 1-second backoff
    tracker.record_429(cooldown_seconds=1, err_msg="HTTP 429 Quota Exceeded")
    assert tracker.state == ProviderHealthState.RATE_LIMITED
    assert not tracker.is_usable()
    assert tracker.rate_limit_429s == 1

    # Wait for backoff expiry
    time.sleep(1.1)
    assert tracker.is_usable()
    assert tracker.state == ProviderHealthState.AVAILABLE

    # Record success
    tracker.record_success(latency_ms=250, tokens=100, audio_sec=30)
    assert tracker.total_requests == 1
    assert tracker.audio_minutes == 0.5
    assert tracker.get_latency_p50() == 250

def test_multi_project_keys_and_status(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key_project_a")
    monkeypatch.setenv("GEMINI_API_KEY_PROJECT_B", "key_project_b")
    monkeypatch.setenv("GEMINI_API_KEY_PROJECT_C", "key_project_c")

    keys = LLMRouter.get_gemini_keys()
    assert len(keys) == 3
    assert keys[0][0] == "GEMINI_PROJECT_A"
    assert keys[1][0] == "GEMINI_PROJECT_B"
    assert keys[2][0] == "GEMINI_PROJECT_C"

    status = LLMRouter.get_provider_status()
    assert status["gemini_projects_configured"] == 3
    assert "circuit_breakers" in status

def test_decoupled_adapters():
    gemini_live = GeminiLiveProvider()
    openai_rt = OpenAIRealtimeProvider()
    modular_kokoro = ModularKokoroProvider()

    assert gemini_live.architecture == "NATIVE_LIVE"
    assert openai_rt.architecture == "NATIVE_LIVE"
    assert modular_kokoro.architecture == "MODULAR_TTS"

    # Test reply generation via deterministic fallback
    res = modular_kokoro.generate_reply(
        user_message="How much does it cost?",
        state_instructions="State pricing concisely.",
        allowed_tools=["book_calendar_slot"]
    )
    assert "reply" in res
    assert res["latency_ms"] > 0
    assert "MODULAR" in res["provider"]

def test_voice_benchmark_harness(clean_db):
    lead = {
        "id": "lead_bench_1",
        "name": "Apex Dental Clinic",
        "doctor_name": "Dr. Miller",
        "phone": "+15125550188"
    }

    # Run 6-call mini-cycle across providers
    bench_res = VoiceModelBenchmark.run_benchmark_cycle(
        lead_dict=lead,
        total_calls=6,
        provider_split={"GEMINI_LIVE": 3, "OPENAI": 2, "MODULAR_KOKORO": 1},
        db=clean_db
    )

    assert bench_res["benchmark_run_size"] == 6
    summary = bench_res["summary"]
    assert summary["total_benchmark_calls_recorded"] == 6
    assert len(summary["models"]) >= 1

    # Verify database persistence
    perf_records = clean_db.get_model_performance_summary()
    assert perf_records["total_benchmark_calls_recorded"] == 6
    for m in perf_records["models"]:
        assert "cost_per_booked_demo_usd" in m
        assert "conversion_rate_pct" in m
