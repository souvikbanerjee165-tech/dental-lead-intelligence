"""
Conversational Turn Controller & Vocal Barge-In Engine.
Implements Section 2 of Voice Telephony & Multi-Line Switchboard Engine Blueprint V1.0.0:
1. Exponential Volume Smoothing (EMA alpha = 0.65)
2. Vocal State Machine: QUIET -> STARTING -> SPEAKING -> STOPPING -> QUIET
3. 180ms Cutoff for Vocal Barge-In interruption (<200ms target)
4. 450ms Silence Hysteresis for Turn Completion
"""

import time
from typing import Dict, Any, Optional


class TurnController:
    """Real-time Voice Activity Detector (VAD) & Barge-In State Controller."""

    ALPHA: float = 0.65
    VOLUME_THRESHOLD: float = 0.05
    BARGE_IN_SUSTAINED_MS: int = 180
    TURN_DONE_SILENCE_MS: int = 450

    def __init__(self):
        self.prev_volume: float = 0.0
        self.smoothed_volume: float = 0.0
        self.state: str = "QUIET"  # QUIET, STARTING, SPEAKING, STOPPING
        self.speech_start_ms: Optional[int] = None
        self.speech_stop_ms: Optional[int] = None
        self.is_speaking: bool = False
        self.ai_is_speaking: bool = False

    def reset(self):
        """Resets the VAD tracking state."""
        self.prev_volume = 0.0
        self.smoothed_volume = 0.0
        self.state = "QUIET"
        self.speech_start_ms = None
        self.speech_stop_ms = None
        self.is_speaking = False

    def set_ai_speaking(self, ai_speaking: bool):
        """Sets whether the AI receptionist is currently speaking audio output."""
        self.ai_is_speaking = ai_speaking

    def process_audio_frame(self, raw_volume: float, now_ms: Optional[int] = None) -> Dict[str, Any]:
        """
        Processes an incoming audio frame volume level with EMA smoothing and hysteresis.
        Returns state transition details including barge-in triggers and turn completions.
        """
        if now_ms is None:
            now_ms = int(time.time() * 1000)

        # 1. Exponential Volume Smoothing (EMA alpha = 0.65)
        self.smoothed_volume = self.ALPHA * raw_volume + (1.0 - self.ALPHA) * self.prev_volume
        self.prev_volume = self.smoothed_volume

        barge_in = False
        turn_complete = False

        if self.smoothed_volume >= self.VOLUME_THRESHOLD:
            # Volume above speech threshold
            self.speech_stop_ms = None
            if self.state in ("QUIET", "STOPPING"):
                self.state = "STARTING"
                self.speech_start_ms = now_ms

            elif self.state == "STARTING":
                if self.speech_start_ms and (now_ms - self.speech_start_ms >= self.BARGE_IN_SUSTAINED_MS):
                    self.state = "SPEAKING"
                    self.is_speaking = True
                    # If caller speaks while AI is speaking, trigger immediate barge-in cutoff!
                    if self.ai_is_speaking:
                        barge_in = True
                    else:
                        barge_in = True  # Generic speaking event for state tracking

        else:
            # Volume below threshold (silence or background noise)
            if self.state in ("SPEAKING", "STARTING"):
                self.state = "STOPPING"
                self.speech_stop_ms = now_ms
                self.speech_start_ms = None

            elif self.state == "STOPPING":
                if self.speech_stop_ms and (now_ms - self.speech_stop_ms >= self.TURN_DONE_SILENCE_MS):
                    self.state = "QUIET"
                    self.is_speaking = False
                    turn_complete = True
                    self.speech_stop_ms = None

        return {
            "state": self.state,
            "raw_volume": round(raw_volume, 4),
            "smoothed_volume": round(self.smoothed_volume, 4),
            "barge_in": barge_in,
            "turn_complete": turn_complete,
            "is_speaking": self.is_speaking,
            "ai_is_speaking": self.ai_is_speaking,
            "now_ms": now_ms
        }
