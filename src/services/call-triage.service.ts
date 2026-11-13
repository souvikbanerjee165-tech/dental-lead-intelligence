/**
 * 4-Channel Multi-Line Concurrency Switchboard & Clinical Triage Service
 * Blueprint V1.0.0 Section 3, 4, and 5 Specification
 */

import { TurnController } from '../core/turn-controller';

export type TriageCategory =
  | 'EMERGENCY_URGENT'
  | 'NEW_CUSTOMER_INTAKE'
  | 'EXISTING_CUSTOMER_RESCHEDULE'
  | 'BILLING_PAYMENT_INQUIRY'
  | 'POST_SERVICE_FOLLOWUP'
  | 'HOURS_LOCATION_INFO';

export type ChannelStatus =
  | 'ringing'
  | 'active_ai'
  | 'warm_transfer_pending'
  | 'completed'
  | 'on_hold';

export interface TriageClassification {
  intent_category: TriageCategory;
  category: TriageCategory;
  priority: string;
  priority_level: string;
  detected_symptoms: string[];
  automated_action_directive: string;
  action_directive: string;
}

export interface TranscriptTurn {
  speaker: 'customer' | 'ai_agent' | 'human_receptionist';
  text: string;
  timestampIso: string;
  audioUrl?: string;
}

export interface ContextBriefingCard {
  callerSummary: string;
  identifiedNeed: string;
  suggestedResolution: string;
  transferredTo: string;
  timestampIso: string;
}

export interface ChannelLine {
  id: string; // line-1 to line-4
  status: ChannelStatus;
  caller_name: string;
  caller_phone: string;
  member_id?: string;
  started_at_ms: number | null;
  duration_seconds: number;
  triage_category: TriageCategory | null;
  triage_priority: string | null;
  action_directive: string | null;
  context_briefing_card: ContextBriefingCard | null;
  transcript: TranscriptTurn[];
  call_control_id: string | null;
  target_operator: string;
  operator_phone: string;
}

export const TRIAGE_RULES: Record<
  TriageCategory,
  { priority: string; keywords: string[]; action: string }
> = {
  EMERGENCY_URGENT: {
    priority: 'CRITICAL URGENT',
    keywords: [
      'severe pain',
      'throbbing',
      'swollen jaw',
      'trauma',
      'cannot chew',
      'broken tooth',
      'abscess',
      'unbearable pain',
      'emergency',
      'urgent',
      'bleeding heavily',
    ],
    action: 'Reserve emergency buffer slot; advise cold compress; no aspirin on tissue.',
  },
  NEW_CUSTOMER_INTAKE: {
    priority: 'HIGH PRODUCTION',
    keywords: [
      'new patient',
      'just moved',
      'establish care',
      'first exam',
      'first visit',
      'switch dentist',
      'accepting new patients',
      'looking for a dentist',
    ],
    action: 'Capture insurance ID; book 60-min comprehensive initial onboarding slot.',
  },
  EXISTING_CUSTOMER_RESCHEDULE: {
    priority: 'ROUTINE / MEDIUM',
    keywords: [
      'work conflict',
      'push back',
      'move appointment',
      'different date',
      'reschedule',
      'change my time',
      'cant make it',
      'running late',
    ],
    action: 'Offer next open recall slot matching preferences without cancellation fee.',
  },
  BILLING_PAYMENT_INQUIRY: {
    priority: 'MEDIUM',
    keywords: [
      'copay',
      'coinsurance',
      'deductible',
      'out of pocket',
      'insurance breakdown',
      'how much will it cost',
      'statement',
      'bill',
      'claim',
      'carecredit',
    ],
    action: 'Verify payer eligibility via EDI 271; calculate exact out-of-pocket balance.',
  },
  POST_SERVICE_FOLLOWUP: {
    priority: 'CRITICAL / MEDIUM',
    keywords: [
      'yesterday',
      'gauze bleeding',
      'tooth pulled',
      'stitches',
      'swelling',
      'post op',
      'surgery yesterday',
      'dry socket',
      'extraction pain',
    ],
    action: 'Check post-op protocol. If bleeding persists > 4 hrs, trigger doctor callback.',
  },
  HOURS_LOCATION_INFO: {
    priority: 'ROUTINE',
    keywords: [
      'hours',
      'address',
      'parking directions',
      'open on weekends',
      'saturday hours',
      'where are you located',
      'directions',
      'suite number',
      'closing time',
    ],
    action: 'Provide clinic address, operating hours, and link to self-scheduling portal.',
  },
};

export class CallTriageService {
  private channels: Map<string, ChannelLine> = new Map();
  private turnControllers: Map<string, TurnController> = new Map();

  constructor() {
    this.seedChannels();
  }

  /**
   * Seed exactly 4 concurrent channels (line-1 to line-4)
   */
  private seedChannels(): void {
    for (let i = 1; i <= 4; i++) {
      const lineId = `line-${i}`;
      this.channels.set(lineId, {
        id: lineId,
        status: 'completed',
        caller_name: '',
        caller_phone: '',
        member_id: undefined,
        started_at_ms: null,
        duration_seconds: 0,
        triage_category: null,
        triage_priority: null,
        action_directive: null,
        context_briefing_card: null,
        transcript: [],
        call_control_id: null,
        target_operator: 'Front Desk Coordinator (Sarah)',
        operator_phone: process.env.FRONT_DESK_TRANSFER_PHONE || '+15559876543',
      });
      this.turnControllers.set(lineId, new TurnController());
    }
  }

  public getLines(): ChannelLine[] {
    const nowMs = Date.now();
    const result: ChannelLine[] = [];
    for (const ch of this.channels.values()) {
      const copy = { ...ch };
      if (
        ['ringing', 'active_ai', 'warm_transfer_pending', 'on_hold'].includes(copy.status) &&
        copy.started_at_ms
      ) {
        copy.duration_seconds = Math.max(0, Math.floor((nowMs - copy.started_at_ms) / 1000));
      }
      result.push(copy);
    }
    return result;
  }

  public getLine(lineId: string): ChannelLine | null {
    const ch = this.channels.get(lineId);
    if (!ch) return null;
    const copy = { ...ch };
    if (
      ['ringing', 'active_ai', 'warm_transfer_pending', 'on_hold'].includes(copy.status) &&
      copy.started_at_ms
    ) {
      copy.duration_seconds = Math.max(0, Math.floor((Date.now() - copy.started_at_ms) / 1000));
    }
    return copy;
  }

  public findAvailableLine(): string | null {
    for (const [id, ch] of this.channels.entries()) {
      if (ch.status === 'completed') {
        return id;
      }
    }
    return null;
  }

  /**
   * 6-Category Intent & Urgency Triage Classifier
   */
  public classifyCall(text: string): TriageClassification {
    const lower = text.toLowerCase();
    let bestCategory: TriageCategory = 'HOURS_LOCATION_INFO';
    let maxScore = 0;
    let matchedKeywords: string[] = [];

    for (const [cat, meta] of Object.entries(TRIAGE_RULES)) {
      let score = 0;
      const hits: string[] = [];
      for (const kw of meta.keywords) {
        if (lower.includes(kw)) {
          score += kw.includes(' ') ? 2 : 1;
          hits.push(kw);
        }
      }
      if (score > maxScore) {
        maxScore = score;
        bestCategory = cat as TriageCategory;
        matchedKeywords = hits;
      }
    }

    const meta = TRIAGE_RULES[bestCategory];
    return {
      intent_category: bestCategory,
      category: bestCategory,
      priority: meta.priority,
      priority_level: meta.priority,
      detected_symptoms: matchedKeywords.length > 0 ? matchedKeywords : ['general inquiry'],
      automated_action_directive: meta.action,
      action_directive: meta.action,
    };
  }

  /**
   * Simulates an inbound call across available channel lines
   */
  public simulateInboundCall(
    callerName: string = 'Amanda Cole',
    callerPhone: string = '+1 555-332-9011',
    initialMessage: string = 'Hi, I have severe throbbing pain in my lower left molar and I cannot chew.',
    lineOverride?: string,
    memberId: string = 'MET-987654321'
  ): { success: boolean; line_id?: string; channel?: ChannelLine; triage?: TriageClassification; error?: string } {
    const lineId = lineOverride || this.findAvailableLine();
    if (!lineId || !this.channels.has(lineId)) {
      return {
        success: false,
        error: 'SWITCHBOARD_AT_CAPACITY: All 4 concurrency lines engaged.',
      };
    }

    const triage = this.classifyCall(initialMessage);
    const nowIso = new Date().toISOString();
    const ch = this.channels.get(lineId)!;

    ch.status = 'active_ai';
    ch.caller_name = callerName;
    ch.caller_phone = callerPhone;
    ch.member_id = memberId;
    ch.started_at_ms = Date.now();
    ch.duration_seconds = 0;
    ch.triage_category = triage.intent_category;
    ch.triage_priority = triage.priority;
    ch.action_directive = triage.automated_action_directive;
    ch.context_briefing_card = null;
    ch.call_control_id = `call_${lineId}_${Date.now()}`;

    ch.transcript = [
      {
        speaker: 'ai_agent',
        text: 'Thank you for calling Apex Dental Studio, this is Emily. How can I help you today?',
        timestampIso: nowIso,
      },
      {
        speaker: 'customer',
        text: initialMessage,
        timestampIso: nowIso,
      },
    ];

    const tc = this.turnControllers.get(lineId);
    if (tc) tc.reset();

    return {
      success: true,
      line_id: lineId,
      channel: this.getLine(lineId)!,
      triage,
    };
  }

  /**
   * Adds an attributed conversational turn
   */
  public addTurn(
    lineId: string,
    speaker: 'customer' | 'ai_agent' | 'human_receptionist',
    text: string,
    audioUrl?: string
  ): boolean {
    const ch = this.channels.get(lineId);
    if (!ch) return false;

    ch.transcript.push({
      speaker,
      text,
      timestampIso: new Date().toISOString(),
      audioUrl,
    });

    if (speaker === 'customer') {
      const triage = this.classifyCall(text);
      if (['CRITICAL URGENT', 'HIGH PRODUCTION'].includes(triage.priority)) {
        ch.triage_category = triage.intent_category;
        ch.triage_priority = triage.priority;
        ch.action_directive = triage.automated_action_directive;
      }
    }
    return true;
  }

  /**
   * Zero-Repetition Warm Transfer Protocol
   */
  public initiateWarmTransfer(
    lineId: string,
    transferredTo: string = 'Front Desk Coordinator (Sarah)',
    operatorPhone: string = process.env.FRONT_DESK_TRANSFER_PHONE || '+15559876543'
  ): { success: boolean; context_briefing_card?: ContextBriefingCard; texml_xml?: string; error?: string } {
    const ch = this.channels.get(lineId);
    if (!ch || ch.status === 'completed') {
      return { success: false, error: 'Line not active or invalid' };
    }

    const customerTurns = ch.transcript.filter((t) => t.speaker === 'customer');
    const latestNeed = customerTurns.length > 0 ? customerTurns[customerTurns.length - 1].text : 'Patient inquiry';

    let callerSummary = `${ch.caller_name || 'Caller'} (${ch.caller_phone || '+1 555-000-0000'}`;
    if (ch.member_id) callerSummary += `, Member ID ${ch.member_id}`;
    callerSummary += ')';

    let resolution = 'Provide clinic hours and self-scheduling portal.';
    if (ch.triage_category === 'EMERGENCY_URGENT') {
      resolution = 'Patient in acute distress. Offer today buffer at 2:00 PM; advise cold compress.';
    } else if (ch.triage_category === 'NEW_CUSTOMER_INTAKE') {
      resolution = 'New patient onboarding. Book 60-min comprehensive initial exam & verify coverage.';
    } else if (ch.triage_category === 'BILLING_PAYMENT_INQUIRY') {
      resolution = 'MetLife covers 50% after $50 deductible. True estimated copay is $650.';
    } else if (ch.triage_category === 'POST_SERVICE_FOLLOWUP') {
      resolution = 'Follow up post-op protocol. Bleeding/swelling review; trigger doctor callback if needed.';
    } else if (ch.triage_category === 'EXISTING_CUSTOMER_RESCHEDULE') {
      resolution = 'Reschedule without fee. Next available recall hygiene slot is Thursday at 11:00 AM.';
    }

    const briefingCard: ContextBriefingCard = {
      callerSummary,
      identifiedNeed: latestNeed,
      suggestedResolution: resolution,
      transferredTo,
      timestampIso: new Date().toISOString(),
    };

    ch.status = 'warm_transfer_pending';
    ch.context_briefing_card = briefingCard;
    ch.target_operator = transferredTo;
    ch.operator_phone = operatorPhone;

    const texml_xml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna-Neural" language="en-US">
    Connecting you directly to our front desk coordinator right now. Please hold.
  </Say>
  <Dial timeout="25">${operatorPhone}</Dial>
</Response>`;

    return {
      success: true,
      context_briefing_card: briefingCard,
      texml_xml,
    };
  }

  public completeCall(lineId: string, reason: string = 'Normal clearing'): boolean {
    const ch = this.channels.get(lineId);
    if (!ch) return false;

    if (ch.started_at_ms) {
      ch.duration_seconds = Math.max(0, Math.floor((Date.now() - ch.started_at_ms) / 1000));
    }
    ch.status = 'completed';

    const tc = this.turnControllers.get(lineId);
    if (tc) tc.reset();
    return true;
  }

  public setHold(lineId: string, onHold: boolean): boolean {
    const ch = this.channels.get(lineId);
    if (!ch) return false;
    ch.status = onHold ? 'on_hold' : 'active_ai';
    return true;
  }

  public getTurnController(lineId: string): TurnController | undefined {
    return this.turnControllers.get(lineId);
  }
}

export const callTriageService = new CallTriageService();
