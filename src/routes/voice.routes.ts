/**
 * REST Endpoints & Webhooks Router for Multi-Line Switchboard
 * Blueprint V1.0.0 Section 6 (Step 5) Specification
 */

import { Router, Request, Response } from 'express';
import { callTriageService } from '../services/call-triage.service';
import { TelnyxVoiceService } from '../services/telnyx-voice.service';

export const voiceRouter = Router();

// GET /lines (and /api/v1/voice/triage/lines)
const handleGetLines = (req: Request, res: Response) => {
  const lines = callTriageService.getLines();
  res.json({ success: true, count: lines.length, lines });
};
voiceRouter.get('/lines', handleGetLines);
voiceRouter.get('/api/v1/voice/triage/lines', handleGetLines);

// POST /classify
const handleClassify = (req: Request, res: Response) => {
  const text = req.body?.text || '';
  if (!text) {
    return res.status(400).json({ error: 'Missing text parameter' });
  }
  const result = callTriageService.classifyCall(text);
  res.json({ success: true, ...result });
};
voiceRouter.post('/classify', handleClassify);
voiceRouter.post('/api/v1/voice/triage/classify', handleClassify);

// POST /simulate-call
const handleSimulateCall = (req: Request, res: Response) => {
  const { caller_name, caller_phone, message, text, line_override, member_id } = req.body || {};
  const initialText = message || text || 'Hi, I have severe throbbing pain in my molar and cannot chew.';
  const result = callTriageService.simulateInboundCall(
    caller_name || 'Amanda Cole',
    caller_phone || '+1 555-332-9011',
    initialText,
    line_override,
    member_id || 'MET-987654321'
  );
  if (!result.success) {
    return res.status(429).json(result);
  }
  res.json(result);
};
voiceRouter.post('/simulate-call', handleSimulateCall);
voiceRouter.post('/api/v1/voice/triage/simulate-call', handleSimulateCall);

// POST /transfer
const handleTransfer = (req: Request, res: Response) => {
  const { line_id, transferred_to, operator_phone } = req.body || {};
  if (!line_id) {
    return res.status(400).json({ error: 'Missing line_id' });
  }
  const result = callTriageService.initiateWarmTransfer(line_id, transferred_to, operator_phone);
  if (!result.success) {
    return res.status(400).json(result);
  }
  res.json(result);
};
voiceRouter.post('/transfer', handleTransfer);
voiceRouter.post('/api/v1/voice/triage/transfer', handleTransfer);

// POST /complete
const handleComplete = (req: Request, res: Response) => {
  const { line_id, reason } = req.body || {};
  if (!line_id) {
    return res.status(400).json({ error: 'Missing line_id' });
  }
  const success = callTriageService.completeCall(line_id, reason);
  res.json({ success, line_id, status: 'completed' });
};
voiceRouter.post('/complete', handleComplete);
voiceRouter.post('/api/v1/voice/triage/complete', handleComplete);

// POST /telnyx/inbound
const handleTelnyxInbound = (req: Request, res: Response) => {
  const xml = TelnyxVoiceService.generateInboundTeXML();
  res.set('Content-Type', 'text/xml');
  res.send(xml);
};
voiceRouter.post('/telnyx/inbound', handleTelnyxInbound);
voiceRouter.post('/api/v1/voice/telnyx/inbound', handleTelnyxInbound);

// POST /telnyx/respond
const handleTelnyxRespond = (req: Request, res: Response) => {
  const speechResult = req.body?.SpeechResult || req.body?.speech_result || '';
  if (!speechResult) {
    const xml = TelnyxVoiceService.generateWarmTransferTeXML();
    res.set('Content-Type', 'text/xml');
    return res.send(xml);
  }

  const triage = callTriageService.classifyCall(speechResult);
  if (triage.priority === 'CRITICAL URGENT' || triage.priority === 'HIGH PRODUCTION') {
    // Zero-Repetition Warm Transfer to Front Desk
    const xml = TelnyxVoiceService.generateWarmTransferTeXML();
    res.set('Content-Type', 'text/xml');
    return res.send(xml);
  }

  const reply = `I understand you are inquiring about ${triage.intent_category.replace(/_/g, ' ').toLowerCase()}. Let me assist you with that.`;
  const xml = TelnyxVoiceService.generateResponseTeXML(reply);
  res.set('Content-Type', 'text/xml');
  res.send(xml);
};
voiceRouter.post('/telnyx/respond', handleTelnyxRespond);
voiceRouter.post('/api/v1/voice/telnyx/respond', handleTelnyxRespond);
