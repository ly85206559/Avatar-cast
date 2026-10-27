"""QA thresholds. Defaults first, tune only from Benchmark data."""

from __future__ import annotations

DEFAULT_THRESHOLDS = {
    "wer_accuracy_min": 0.85,
    "lipsync_score_min": 0.0,  # set per lipsync model after first Benchmark run
    "face_cosine_min": 0.85,
    "voice_drift_max": 0.30,
    "max_retries": 3,
}


def verdict(scores: dict, thresholds: dict | None = None) -> str:
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    if scores.get("burned_subtitle"):
        return "fail"
    if scores.get("wer_accuracy", 1.0) < t["wer_accuracy_min"]:
        return "fail"
    if scores.get("face_cosine", 1.0) < t["face_cosine_min"]:
        return "fail"
    if scores.get("voice_drift", 0.0) > t["voice_drift_max"]:
        return "fail"
    return "pass"
