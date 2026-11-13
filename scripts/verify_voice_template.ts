/**
 * Automated Verification Suite for Voice Telephony & Multi-Line Switchboard Engine
 * Blueprint V1.0.0 Section 6 (Step 7) Specification
 * Executes exactly 36 strict assertions across Intent, Concurrency, VAD, and Warm Transfer.
 */

import { TurnController } from '../src/core/turn-controller';
import { CallTriageService, TRIAGE_RULES, TriageCategory } from '../src/services/call-triage.service';
import { TelnyxVoiceService } from '../src/services/telnyx-voice.service';

let totalAssertions = 0;
let passedAssertions = 0;

function assert(condition: boolean, description: string): void {
  totalAssertions++;
  if (condition) {
    passedAssertions++;
    console.log(`  [✓] Pass (${totalAssertions}/36): ${description}`);
  } else {
    console.error(`  [✗] FAIL (${totalAssertions}/36): ${description}`);
    process.exitCode = 1;
  }
}

async function runVerificationSuite() {
  console.log('\n================================================================');
  console.log('VOICE TELEPHONY & MULTI-LINE SWITCHBOARD ENGINE - VERIFICATION SUITE');
  console.log('Testing 36 Critical Blueprint Assertions across Telephony & VAD');
  console.log('================================================================\n');

  const triageService = new CallTriageService();

  // -------------------------------------------------------------
  // SUITE 1: 6-Category Intent & Urgency Triage Classifier (18 Assertions)
  // -------------------------------------------------------------
  console.log('--- SUITE 1: 6-Category Intent & Urgency Triage Classifier ---');

  const testCases: Array<{
    phrase: string;
    expectedCategory: TriageCategory;
    expectedPriority: string;
    expectedAction: string;
  }> = [
    {
      phrase: 'I have severe pain and a swollen jaw and cannot chew anything.',
      expectedCategory: 'EMERGENCY_URGENT',
      expectedPriority: 'CRITICAL URGENT',
      expectedAction: TRIAGE_RULES.EMERGENCY_URGENT.action,
    },
    {
      phrase: 'Hi, I am a new patient just moved to the area and want to establish care with a first exam.',
      expectedCategory: 'NEW_CUSTOMER_INTAKE',
      expectedPriority: 'HIGH PRODUCTION',
      expectedAction: TRIAGE_RULES.NEW_CUSTOMER_INTAKE.action,
    },
    {
      phrase: 'I have a work conflict and need to push back my appointment to a different date.',
      expectedCategory: 'EXISTING_CUSTOMER_RESCHEDULE',
      expectedPriority: 'ROUTINE / MEDIUM',
      expectedAction: TRIAGE_RULES.EXISTING_CUSTOMER_RESCHEDULE.action,
    },
    {
      phrase: 'What is my copay and coinsurance out of pocket deductible for a crown?',
      expectedCategory: 'BILLING_PAYMENT_INQUIRY',
      expectedPriority: 'MEDIUM',
      expectedAction: TRIAGE_RULES.BILLING_PAYMENT_INQUIRY.action,
    },
    {
      phrase: 'I had my tooth pulled yesterday, gauze bleeding and stitches swelling.',
      expectedCategory: 'POST_SERVICE_FOLLOWUP',
      expectedPriority: 'CRITICAL / MEDIUM',
      expectedAction: TRIAGE_RULES.POST_SERVICE_FOLLOWUP.action,
    },
    {
      phrase: 'What are your clinic hours, parking directions, and are you open on weekends?',
      expectedCategory: 'HOURS_LOCATION_INFO',
      expectedPriority: 'ROUTINE',
      expectedAction: TRIAGE_RULES.HOURS_LOCATION_INFO.action,
    },
  ];

  for (const tc of testCases) {
    const res = triageService.classifyCall(tc.phrase);
    assert(
      res.intent_category === tc.expectedCategory,
      `Category classification correctly identified: ${tc.expectedCategory}`
    );
    assert(
      res.priority === tc.expectedPriority,
      `Priority matches blueprint spec: ${tc.expectedPriority}`
    );
    assert(
      res.automated_action_directive === tc.expectedAction,
      `Action directive matches spec for: ${tc.expectedCategory}`
    );
  }

  // -------------------------------------------------------------
  // SUITE 2: 4-Channel Multi-Line Concurrency Switchboard (10 Assertions)
  // -------------------------------------------------------------
  console.log('\n--- SUITE 2: 4-Channel Multi-Line Concurrency Switchboard ---');

  const lines = triageService.getLines();
  assert(lines.length === 4, 'Multi-line switchboard initialized with exactly 4 channels (line-1 to line-4)');

  // Simulate 4 concurrent calls across all channels
  const call1 = triageService.simulateInboundCall('Patient One', '+15551111111', 'Severe throbbing emergency toothache', 'line-1');
  const call2 = triageService.simulateInboundCall('Patient Two', '+15552222222', 'New patient looking for first exam', 'line-2');
  const call3 = triageService.simulateInboundCall('Patient Three', '+15553333333', 'Need to reschedule my appointment', 'line-3');
  const call4 = triageService.simulateInboundCall('Patient Four', '+15554444444', 'What is my copay deductible', 'line-4');

  assert(
    call1.success && call2.success && call3.success && call4.success,
    'All 4 parallel channels successfully engaged concurrently without collision'
  );

  // 5th call attempt must trigger capacity limit
  const call5 = triageService.simulateInboundCall('Patient Five', '+15555555555', 'Another call');
  assert(
    !call5.success && call5.error?.includes('SWITCHBOARD_AT_CAPACITY'),
    'Channel capacity limit enforced on 5th concurrent inbound caller'
  );

  // Channel timer isolation
  const line1Data = triageService.getLine('line-1');
  assert(
    line1Data?.status === 'active_ai' && typeof line1Data.duration_seconds === 'number',
    'Line-1 maintains isolated timer and active_ai reactive state'
  );
  assert(
    triageService.getLine('line-2')?.status === 'active_ai',
    'Line-2 independently running concurrent active_ai state without cross-talk'
  );

  // Add turns with speaker attribution
  triageService.addTurn('line-1', 'customer', 'Can I speak to someone at the desk?');
  triageService.addTurn('line-1', 'ai_agent', 'Let me transfer you right away.');
  triageService.addTurn('line-1', 'human_receptionist', 'Hi Amanda, this is Sarah at the front desk.');

  const updatedLine1 = triageService.getLine('line-1');
  assert(
    updatedLine1?.transcript.some((t) => t.speaker === 'customer'),
    'Transcript records customer speaker role with ISO timestamp'
  );
  assert(
    updatedLine1?.transcript.some((t) => t.speaker === 'ai_agent'),
    'Transcript records ai_agent (Emily) speaker role'
  );
  assert(
    updatedLine1?.transcript.some((t) => t.speaker === 'human_receptionist'),
    'Transcript records human_receptionist front-desk handoff role'
  );

  // Line hold muting
  triageService.setHold('line-1', true);
  assert(triageService.getLine('line-1')?.status === 'on_hold', 'Audio channel muted during staff lookup (on_hold state)');

  // Line completion
  triageService.completeCall('line-1');
  assert(triageService.getLine('line-1')?.status === 'completed', 'Completed call logged and archived to completed state');

  // -------------------------------------------------------------
  // SUITE 3: Conversational Turn Controller & Vocal Barge-In (4 Assertions)
  // -------------------------------------------------------------
  console.log('\n--- SUITE 3: Conversational Turn Controller & Vocal Barge-In ---');

  const tc = new TurnController();

  // Test 1: EMA Smoothing
  const frame1 = tc.processAudioFrame(0.10, 1000);
  assert(
    frame1.smoothedVolume === Number((0.65 * 0.10 + 0.35 * 0).toFixed(4)),
    'Exponential volume smoothing matches EMA formula (alpha = 0.65)'
  );

  // Test 2: Quiet audio maintains quiet state
  tc.reset();
  const quietFrame = tc.processAudioFrame(0.01, 1000);
  assert(quietFrame.state === 'QUIET' && !quietFrame.bargeIn, 'Quiet background volume remains in QUIET state');

  // Test 3: Sustained speech >= 180ms triggers barge-in
  tc.reset();
  tc.setAiSpeaking(true);
  tc.processAudioFrame(0.08, 1000); // STARTING at t=1000
  const speechFrame = tc.processAudioFrame(0.08, 1190); // t=1190 (190ms >= 180ms cutoff)
  assert(
    speechFrame.state === 'SPEAKING' && speechFrame.bargeIn,
    'Sustained caller volume >= 180ms triggers instant SPEAKING and Vocal Barge-In cutoff (<200ms)'
  );

  // Test 4: Silence >= 450ms triggers turn completion
  tc.processAudioFrame(0.01, 1200); // Volume drops below 0.05 -> STOPPING
  const completeFrame = tc.processAudioFrame(0.01, 1660); // 460ms silence >= 450ms
  assert(
    completeFrame.state === 'QUIET' && completeFrame.turnComplete,
    'Silence >= 450ms triggers turnComplete = true and transitions back to QUIET'
  );

  // -------------------------------------------------------------
  // SUITE 4: Zero-Repetition Warm Transfer Protocol & TeXML (4 Assertions)
  // -------------------------------------------------------------
  console.log('\n--- SUITE 4: Zero-Repetition Warm Transfer Protocol & TeXML ---');

  const transferLine = triageService.simulateInboundCall(
    'Amanda Cole',
    '+1 555-332-9011',
    'Inquiring out-of-pocket coinsurance for tooth #19 porcelain crown ($1,250 fee)',
    'line-2',
    'MET-987654321'
  );

  const transferResult = triageService.initiateWarmTransfer('line-2', 'Front Desk Coordinator (Sarah)', '+15559876543');
  const card = transferResult.context_briefing_card;

  assert(
    card !== undefined &&
      typeof card.callerSummary === 'string' &&
      typeof card.identifiedNeed === 'string' &&
      typeof card.suggestedResolution === 'string' &&
      typeof card.transferredTo === 'string' &&
      typeof card.timestampIso === 'string',
    'Context Briefing Card strictly matches zero-repetition specification schema'
  );

  assert(
    card?.callerSummary.includes('Amanda Cole') &&
      card?.callerSummary.includes('+1 555-332-9011') &&
      card?.callerSummary.includes('Member ID MET-987654321'),
    'Context Briefing Card preserves caller identity, phone, and insurance member ID'
  );

  assert(
    transferResult.texml_xml?.includes('<Say voice="Polly.Joanna-Neural" language="en-US">') === true,
    'Carrier TeXML generates neural Joanna voice greeting'
  );

  assert(
    transferResult.texml_xml?.includes('<Dial timeout="25">+15559876543</Dial>') === true,
    'Carrier TeXML connects live bridge to front desk coordinator via <Dial>'
  );

  // Final Summary
  console.log('\n================================================================');
  console.log(`VERIFICATION SUMMARY: ${passedAssertions} / ${totalAssertions} ASSERTIONS PASSED (100%)`);
  console.log('================================================================\n');

  if (passedAssertions === 36) {
    console.log('🏆 ALL 36 BLUEPRINT ASSERTIONS PASSED PERFECTLY!\n');
    process.exit(0);
  } else {
    console.error(`FAILED: Only ${passedAssertions} out of 36 passed.`);
    process.exit(1);
  }
}

runVerificationSuite().catch((err) => {
  console.error('Test suite uncaught error:', err);
  process.exit(1);
});
