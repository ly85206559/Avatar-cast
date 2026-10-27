import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_demo_script_matches_shots():
    script = json.loads((ROOT / "examples/demo-script.json").read_text())
    assert script, "demo script must not be empty"
    for seg in script:
        assert seg["shot"] in ("talking_head", "b_roll", "demo", "scene")
        assert seg["text"].strip()


def test_demo_brief_persona_present():
    brief = json.loads((ROOT / "examples/demo-brief.json").read_text())
    assert brief["persona_id"]
    assert brief["ratio"] in ("16:9", "9:16", "1:1")


def test_qa_verdict_rejects_burned_subtitle():
    from dhp.qa import verdict

    assert verdict({"burned_subtitle": True, "wer_accuracy": 0.99}) == "fail"
    assert verdict({"burned_subtitle": False, "wer_accuracy": 0.92,
                    "face_cosine": 0.95, "voice_drift": 0.1}) == "pass"
