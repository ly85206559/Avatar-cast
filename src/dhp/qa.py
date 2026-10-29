"""QA thresholds. Defaults first, tune only from Benchmark data."""

from __future__ import annotations

import math
from numbers import Real

DEFAULT_THRESHOLDS = {
    "wer_accuracy_min": 0.85,
    "lipsync_score_min": 0.0,  # set per lipsync model after first Benchmark run
    "face_cosine_min": 0.85,
    "voice_drift_max": 0.30,
    "max_retries": 3,
}


def verdict(scores: dict, thresholds: dict | None = None) -> str:
    """Return unverified when a required measurement is unavailable."""
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    if scores.get("burned_subtitle") is True:
        return "fail"
    checks = (
        ("wer_accuracy", "wer_accuracy_min", lambda value, limit: value < limit),
        ("lipsync_score", "lipsync_score_min", lambda value, limit: value < limit),
        ("face_cosine", "face_cosine_min", lambda value, limit: value < limit),
        ("voice_drift", "voice_drift_max", lambda value, limit: value > limit),
    )
    missing = not isinstance(scores.get("burned_subtitle"), bool)
    for name, threshold, fails in checks:
        value = scores.get(name)
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            missing = True
        elif fails(value, t[threshold]):
            return "fail"
    return "unverified" if missing else "pass"
