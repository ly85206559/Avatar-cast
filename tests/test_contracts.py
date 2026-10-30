import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_demo_script_matches_shots():
    script = json.loads((ROOT / "examples/demo-script.json").read_text(encoding="utf-8"))
    assert script, "demo script must not be empty"
    for seg in script:
        assert seg["shot"] in ("talking_head", "b_roll", "demo", "scene")
        assert seg["text"].strip()


def test_demo_brief_persona_present():
    brief = json.loads((ROOT / "examples/demo-brief.json").read_text(encoding="utf-8"))
    assert brief["persona_id"]
    assert brief["ratio"] in ("16:9", "9:16", "1:1")


def test_qa_verdict_rejects_burned_subtitle():
    from dhp.qa import verdict

    assert verdict({"burned_subtitle": True, "wer_accuracy": 0.99}) == "fail"
    assert verdict({"burned_subtitle": False, "wer_accuracy": 0.92,
                    "lipsync_score": 0.5, "face_cosine": 0.95,
                    "voice_drift": 0.1}) == "pass"


def test_qa_requires_all_measurements_and_checks_lipsync():
    from dhp.qa import verdict

    scores = {"burned_subtitle": False, "wer_accuracy": 0.92,
              "lipsync_score": 0.5, "face_cosine": 0.95, "voice_drift": 0.1}
    assert verdict({k: v for k, v in scores.items() if k != "lipsync_score"}) == "unverified"
    assert verdict({**scores, "lipsync_score": -0.1}) == "fail"
    assert verdict({**scores, "lipsync_score": float("nan")}) == "unverified"
    assert verdict({"burned_subtitle": True}) == "fail"
    schema = json.loads((ROOT / "schemas/qa.json").read_text(encoding="utf-8"))
    assert verdict({}) in schema["properties"]["verdict"]["enum"]


def test_cache_key_changes_with_reference_image():
    from dhp.cache import segment_cache_key

    args = ({"text": "hello"}, "presenter", "model", "1", {}, "audio")
    assert segment_cache_key(*args, reference_sha256="image1") == segment_cache_key(
        *args, reference_sha256="image1")
    assert segment_cache_key(*args, reference_sha256="image1") != segment_cache_key(
        *args, reference_sha256="image2")
