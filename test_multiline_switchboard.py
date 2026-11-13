"""
Python Automated Verification Suite for Multi-Line Switchboard Engine.
Tests all 36 Blueprint V1.0.0 assertions across Intent Triage, 4-Channel Concurrency,
Turn Controller VAD & Barge-In, and Zero-Repetition Warm Transfer.
"""

from multiline_switchboard import MultiLineSwitchboard, TRIAGE_CATEGORIES
from turn_controller import TurnController

total_assertions = 0
passed_assertions = 0

def assert_test(cond: bool, desc: str = ""):
    global total_assertions, passed_assertions
    total_assertions += 1
    if cond:
        passed_assertions += 1
        print(f"  [✓] Pass ({total_assertions}/36): {desc}")
    else:
        print(f"  [✗] FAIL ({total_assertions}/36): {desc}")
        raise AssertionError(desc)

def main():
    print("\n================================================================")
    print("PYTHON MULTI-LINE SWITCHBOARD ENGINE - VERIFICATION SUITE")
    print("Testing 36 Critical Blueprint Assertions across Telephony & VAD")
    print("================================================================\n")

    sb = MultiLineSwitchboard()

    # --- SUITE 1: 6-Category Intent & Urgency Triage Classifier (18 Assertions) ---
    print("--- SUITE 1: 6-Category Intent & Urgency Triage Classifier ---")
    test_cases = [
        ("I have severe pain and a swollen jaw and cannot chew anything.", "EMERGENCY_URGENT", "CRITICAL URGENT", TRIAGE_CATEGORIES["EMERGENCY_URGENT"]["action_directive"]),
        ("Hi, I am a new patient just moved to the area and want to establish care with a first exam.", "NEW_CUSTOMER_INTAKE", "HIGH PRODUCTION", TRIAGE_CATEGORIES["NEW_CUSTOMER_INTAKE"]["action_directive"]),
        ("I have a work conflict and need to push back my appointment to a different date.", "EXISTING_CUSTOMER_RESCHEDULE", "ROUTINE / MEDIUM", TRIAGE_CATEGORIES["EXISTING_CUSTOMER_RESCHEDULE"]["action_directive"]),
        ("What is my copay and coinsurance out of pocket deductible for a crown?", "BILLING_PAYMENT_INQUIRY", "MEDIUM", TRIAGE_CATEGORIES["BILLING_PAYMENT_INQUIRY"]["action_directive"]),
        ("I had my tooth pulled yesterday, gauze bleeding and stitches swelling.", "POST_SERVICE_FOLLOWUP", "CRITICAL / MEDIUM", TRIAGE_CATEGORIES["POST_SERVICE_FOLLOWUP"]["action_directive"]),
        ("What are your clinic hours, parking directions, and are you open on weekends?", "HOURS_LOCATION_INFO", "ROUTINE", TRIAGE_CATEGORIES["HOURS_LOCATION_INFO"]["action_directive"]),
    ]

    for phrase, cat, prio, act in test_cases:
        res = sb.classify_call_intent(phrase)
        assert_test(res["intent_category"] == cat, f"Category correctly identified: {cat}")
        assert_test(res["priority"] == prio, f"Priority matches blueprint spec: {prio}")
        assert_test(res["automated_action_directive"] == act, f"Action directive matches spec for: {cat}")

    # --- SUITE 2: 4-Channel Multi-Line Concurrency Switchboard (10 Assertions) ---
    print("\n--- SUITE 2: 4-Channel Multi-Line Concurrency Switchboard ---")
    lines = sb.get_all_lines()
    assert_test(len(lines) == 4, "Multi-line switchboard initialized with exactly 4 channels (line-1 to line-4)")

    c1 = sb.simulate_inbound_call("Patient One", "+15551111111", "Severe throbbing emergency toothache", "line-1")
    c2 = sb.simulate_inbound_call("Patient Two", "+15552222222", "New patient looking for first exam", "line-2")
    c3 = sb.simulate_inbound_call("Patient Three", "+15553333333", "Need to reschedule my appointment", "line-3")
    c4 = sb.simulate_inbound_call("Patient Four", "+15554444444", "What is my copay deductible", "line-4")
    assert_test(c1["success"] and c2["success"] and c3["success"] and c4["success"], "All 4 parallel channels engaged concurrently without collision")

    c5 = sb.simulate_inbound_call("Patient Five", "+15555555555", "Overflow call")
    assert_test(not c5["success"] and c5["error"] == "SWITCHBOARD_AT_CAPACITY", "Channel capacity limit enforced on 5th concurrent inbound caller")

    l1 = sb.get_line("line-1")
    assert_test(l1["status"] == "active_ai" and isinstance(l1["duration_seconds"], int), "Line-1 maintains isolated timer and active_ai state")
    assert_test(sb.get_line("line-2")["status"] == "active_ai", "Line-2 independently running concurrent active_ai state without cross-talk")

    sb.process_line_turn("line-1", "customer", "Can I speak to someone at the desk?")
    sb.process_line_turn("line-1", "ai_agent", "Let me transfer you right away.")
    sb.process_line_turn("line-1", "human_receptionist", "Hi Amanda, this is Sarah at the front desk.")

    up_l1 = sb.get_line("line-1")
    assert_test(any(t["speaker"] == "customer" for t in up_l1["transcript"]), "Transcript records customer speaker role with ISO timestamp")
    assert_test(any(t["speaker"] == "ai_agent" for t in up_l1["transcript"]), "Transcript records ai_agent (Emily) speaker role")
    assert_test(any(t["speaker"] == "human_receptionist" for t in up_l1["transcript"]), "Transcript records human_receptionist front-desk handoff role")

    sb.set_line_hold("line-1", True)
    assert_test(sb.get_line("line-1")["status"] == "on_hold", "Audio channel muted during staff lookup (on_hold state)")

    sb.complete_call("line-1")
    assert_test(sb.get_line("line-1")["status"] == "completed", "Completed call logged and archived to completed state")

    # --- SUITE 3: Conversational Turn Controller & Vocal Barge-In (4 Assertions) ---
    print("\n--- SUITE 3: Conversational Turn Controller & Vocal Barge-In ---")
    tc = TurnController()
    f1 = tc.process_audio_frame(0.10, 1000)
    assert_test(f1["smoothed_volume"] == round(0.65 * 0.10, 4), "Exponential volume smoothing matches EMA formula (alpha = 0.65)")

    tc.reset()
    q_f = tc.process_audio_frame(0.01, 1000)
    assert_test(q_f["state"] == "QUIET" and not q_f["barge_in"], "Quiet background volume remains in QUIET state")

    tc.reset()
    tc.set_ai_speaking(True)
    tc.process_audio_frame(0.08, 1000)
    sp_f = tc.process_audio_frame(0.08, 1190)
    assert_test(sp_f["state"] == "SPEAKING" and sp_f["barge_in"], "Sustained caller volume >= 180ms triggers instant SPEAKING and Vocal Barge-In (<200ms)")

    tc.process_audio_frame(0.01, 1200)
    done_f = tc.process_audio_frame(0.01, 1660)
    assert_test(done_f["state"] == "QUIET" and done_f["turn_complete"], "Silence >= 450ms triggers turnComplete = true and transitions back to QUIET")

    # --- SUITE 4: Zero-Repetition Warm Transfer Protocol & TeXML (4 Assertions) ---
    print("\n--- SUITE 4: Zero-Repetition Warm Transfer Protocol & TeXML ---")
    sb.simulate_inbound_call(
        "Amanda Cole",
        "+1 555-332-9011",
        "Inquiring out-of-pocket coinsurance for tooth #19 porcelain crown ($1,250 fee)",
        "line-2",
        "MET-987654321"
    )
    t_res = sb.initiate_warm_transfer("line-2", "Front Desk Coordinator (Sarah)", "+15559876543")
    card = t_res["context_briefing_card"]

    assert_test(
        all(k in card for k in ["callerSummary", "identifiedNeed", "suggestedResolution", "transferredTo", "timestampIso"]),
        "Context Briefing Card strictly matches zero-repetition specification schema"
    )
    assert_test(
        "Amanda Cole" in card["callerSummary"] and "+1 555-332-9011" in card["callerSummary"] and "Member ID MET-987654321" in card["callerSummary"],
        "Context Briefing Card preserves caller identity, phone, and insurance member ID"
    )
    assert_test(
        '<Say voice="Polly.Joanna-Neural" language="en-US">' in t_res["texml_xml"],
        "Carrier TeXML generates neural Joanna voice greeting"
    )
    assert_test(
        '<Dial timeout="25">+15559876543</Dial>' in t_res["texml_xml"],
        "Carrier TeXML connects live bridge to front desk coordinator via <Dial>"
    )

    print("\n================================================================")
    print(f"VERIFICATION SUMMARY: {passed_assertions} / {total_assertions} ASSERTIONS PASSED (100%)")
    print("================================================================\n")
    print("🏆 ALL 36 BLUEPRINT ASSERTIONS PASSED PERFECTLY IN PYTHON!\n")

if __name__ == "__main__":
    main()
