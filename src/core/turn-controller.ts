/**
 * Conversational Turn Controller & Vocal Barge-In Engine
 * Blueprint V1.0.0 Section 2 Specification
 */

export interface AudioFrameResult {
  state: 'QUIET' | 'STARTING' | 'SPEAKING' | 'STOPPING';
  rawVolume: number;
  smoothedVolume: number;
  bargeIn: boolean;
  turnComplete: boolean;
  isSpeaking: boolean;
  aiIsSpeaking: boolean;
  nowMs: number;
}

export class TurnController {
  private prevVolume: number = 0.0;
  private smoothedVolume: number = 0.0;
  public state: 'QUIET' | 'STARTING' | 'SPEAKING' | 'STOPPING' = 'QUIET';
  private speechStartMs: number | null = null;
  private speechStopMs: number | null = null;
  public isSpeaking: boolean = false;
  public aiIsSpeaking: boolean = false;

  readonly ALPHA = 0.65;
  readonly VOLUME_THRESHOLD = 0.05;
  readonly BARGE_IN_SUSTAINED_MS = 180;
  readonly TURN_DONE_SILENCE_MS = 450;

  constructor() {
    this.reset();
  }

  reset(): void {
    this.prevVolume = 0.0;
    this.smoothedVolume = 0.0;
    this.state = 'QUIET';
    this.speechStartMs = null;
    this.speechStopMs = null;
    this.isSpeaking = false;
  }

  setAiSpeaking(aiSpeaking: boolean): void {
    this.aiIsSpeaking = aiSpeaking;
  }

  processAudioFrame(rawVolume: number, nowMs: number = Date.now()): AudioFrameResult {
    // 1. Exponential Volume Smoothing (EMA alpha=0.65)
    this.smoothedVolume = this.ALPHA * rawVolume + (1.0 - this.ALPHA) * this.prevVolume;
    this.prevVolume = this.smoothedVolume;

    let bargeIn = false;
    let turnComplete = false;

    if (this.smoothedVolume >= this.VOLUME_THRESHOLD) {
      this.speechStopMs = null;
      if (this.state === 'QUIET' || this.state === 'STOPPING') {
        this.state = 'STARTING';
        this.speechStartMs = nowMs;
      } else if (this.state === 'STARTING') {
        if (this.speechStartMs !== null && nowMs - this.speechStartMs >= this.BARGE_IN_SUSTAINED_MS) {
          this.state = 'SPEAKING';
          this.isSpeaking = true;
          bargeIn = true; // Sustained speech >= 180ms triggers barge-in
        }
      }
    } else {
      if (this.state === 'SPEAKING' || this.state === 'STARTING') {
        this.state = 'STOPPING';
        this.speechStopMs = nowMs;
        this.speechStartMs = null;
      } else if (this.state === 'STOPPING') {
        if (this.speechStopMs !== null && nowMs - this.speechStopMs >= this.TURN_DONE_SILENCE_MS) {
          this.state = 'QUIET';
          this.isSpeaking = false;
          turnComplete = true;
          this.speechStopMs = null;
        }
      }
    }

    return {
      state: this.state,
      rawVolume: Number(rawVolume.toFixed(4)),
      smoothedVolume: Number(this.smoothedVolume.toFixed(4)),
      bargeIn,
      turnComplete,
      isSpeaking: this.isSpeaking,
      aiIsSpeaking: this.aiIsSpeaking,
      nowMs,
    };
  }
}
