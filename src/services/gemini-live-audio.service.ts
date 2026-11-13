/**
 * Gemini Live 24kHz Bidirectional Audio Streaming Service
 * Blueprint V1.0.0 Section 1 (Mode A) Specification (Sub-300ms Round-Trip SLA)
 */

import { WebSocket } from 'ws';
import { callTriageService } from './call-triage.service';

export class GeminiLiveAudioService {
  /**
   * Handles incoming WebSocket client connection for 24kHz raw PCM bidirectional streaming
   */
  static handleWebSocketConnection(ws: WebSocket, lineId: string = 'line-1'): void {
    const ch = callTriageService.getLine(lineId);
    if (!ch) {
      ws.close(1008, 'Channel not found');
      return;
    }

    const turnController = callTriageService.getTurnController(lineId);

    ws.on('message', (data: Buffer | string) => {
      try {
        // If message is binary PCM audio frame (24kHz 16-bit mono)
        if (Buffer.isBuffer(data)) {
          // Calculate RMS volume level
          let sumSquares = 0;
          const numSamples = Math.floor(data.length / 2);
          for (let i = 0; i < data.length - 1; i += 2) {
            const sample = data.readInt16LE(i) / 32768.0;
            sumSquares += sample * sample;
          }
          const rmsVolume = numSamples > 0 ? Math.sqrt(sumSquares / numSamples) : 0;

          if (turnController) {
            const vad = turnController.processAudioFrame(rmsVolume);
            // If vocal barge-in triggered while AI speaking, emit immediate interruption signal
            if (vad.bargeIn) {
              ws.send(JSON.stringify({ event: 'barge_in', lineId, vad }));
            } else if (vad.turnComplete) {
              ws.send(JSON.stringify({ event: 'turn_complete', lineId, vad }));
            }
          }
        } else {
          // JSON control frame
          const parsed = JSON.parse(data.toString());
          if (parsed.event === 'start_ai_speech') {
            turnController?.setAiSpeaking(true);
          } else if (parsed.event === 'stop_ai_speech') {
            turnController?.setAiSpeaking(false);
          }
        }
      } catch (err) {
        // Safe error suppression
      }
    });

    ws.on('close', () => {
      turnController?.reset();
    });
  }
}
