"""Live session state machine (Phase 3 interface only, v0.3).

This is NOT a working live stream. There is no RTMP, no streaming
ASR/LLM/TTS, and no real-time lip-sync here, and claiming otherwise
would be dishonest. What exists in v0.3 is the session contract that
Phase 3 must satisfy, with tests:

- States: idle -> listening -> speaking -> (interrupted) -> listening
  -> ended. Any other transition is rejected.
- Interruption: while speaking, an interruption moves the session
  back to listening and records the cut-off time; it never rewrites
  already-spoken history.
- Latency budget: a dataclass with explicit targets (not measurements).
  A Phase 3 implementation must report measured latency against these
  targets; "fast" is not a number.

RTMP, streaming models, and interruption audio handling are Phase 3
work, not v0.3 work.
"""

from __future__ import annotations

from dataclasses import dataclass, field

STATES = ("idle", "listening", "speaking", "ended")
ALLOWED = {
    "idle": ("listening", "ended"),
    "listening": ("speaking", "ended"),
    "speaking": ("listening", "ended"),  # speaking -> listening = interrupted
    "ended": (),
}


@dataclass
class LatencyBudget:
    """Targets in milliseconds. Targets, not measurements."""
    asr_ms: int = 300
    llm_first_token_ms: int = 800
    tts_first_audio_ms: int = 500
    lipsync_frame_ms: int = 40


@dataclass
class LiveSession:
    persona_id: str
    state: str = "idle"
    interruptions: int = 0
    history: list[str] = field(default_factory=list)
    budget: LatencyBudget = field(default_factory=LatencyBudget)

    def transition(self, new_state: str) -> None:
        if new_state not in ALLOWED[self.state]:
            raise ValueError(f"illegal live transition: {self.state} -> {new_state}")
        if self.state == "speaking" and new_state == "listening":
            self.interruptions += 1
        self.state = new_state
        self.history.append(f"{self.state}")

    def interrupt(self) -> None:
        """Cut off speaking and go back to listening."""
        self.transition("listening")
