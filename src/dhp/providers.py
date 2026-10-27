"""Provider interfaces. Every adapter must report model, version, params, time, cost.

No adapter is implemented here on purpose: pick one per interface, implement it
in providers/<name>.py, and register it in config. The pipeline only talks to
these interfaces, never to a vendor SDK directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Quote:
    estimated_cost: float
    currency: str = "USD"
    cache_hit: bool = False
    notes: str = ""


@dataclass
class Clip:
    path: str
    model: str
    model_version: str
    params: dict = field(default_factory=dict)
    duration_sec: float = 0.0
    cost: float = 0.0


@dataclass
class Audio:
    path: str
    duration_sec: float
    sha256: str
    voice_id: str


class VideoProvider(Protocol):
    def estimate(self, task: dict) -> Quote: ...
    def generate(self, task: dict) -> Clip: ...


class TTSProvider(Protocol):
    def synthesize(self, segment: dict) -> Audio: ...


class LipSyncProvider(Protocol):
    def drive(self, image_path: str, audio: Audio) -> Clip: ...


class ASRProvider(Protocol):
    def transcribe(self, audio_path: str) -> list[dict]: ...


class QAScorer(Protocol):
    def score(self, clip: Clip, segment: dict, audio: Audio) -> dict: ...
