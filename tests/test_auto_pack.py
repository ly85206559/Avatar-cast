import hashlib
import json
import shutil
import subprocess

import pytest
from PIL import Image, ImageChops

from dhp import auto_pack, make, native_assembly, packaging_components


def _words():
    return [{"word": "先看画面", "start": 0.4, "end": 1.6, "conf": 0.98},
            {"word": "再听声音", "start": 2.1, "end": 3.4, "conf": 0.99}]


@pytest.mark.parametrize("alter,reason", [
    (lambda words: words[0].update(word="先看照片"), "script_transcript_mismatch"),
    (lambda words: words[0].update(conf=0.5), "low_word_confidence"),
    (lambda words: words[0].pop("conf"), "invalid_or_missing_word_timing"),
    (lambda words: words[0].update(start=float("nan")), "invalid_or_missing_word_timing"),
    (lambda words: words[1].update(start=0.3), "invalid_or_missing_word_timing"),
    (lambda words: words.append({"word": "额外对白", "start": 3.5, "end": 3.8, "conf": 1}), "script_transcript_mismatch"),
])
def test_unreliable_matching_falls_back_without_fabricated_cues(alter, reason):
    words = _words()
    alter(words)
    result = auto_pack.match_cues("先看画面，再听声音。", words, 4)
    assert result == {"status": "fallback", "reason": reason, "cues": []}


def test_matching_and_recipes_use_observed_sentence_boundaries():
    alignment = auto_pack.match_cues("先看画面，再听声音。", _words(), 4)
    assert alignment["status"] == "matched"
    assert [(c["start"], c["end"]) for c in alignment["cues"]] == [(0.4, 1.6), (2.1, 3.4)]
    # A separate opening title does not replace or shift the actual subtitle cues.
    for style in ("promo", "explainer", "warm"):
        pack = auto_pack.recipe(style, "", alignment["cues"], 4, True)
        packaging_components.validate(pack, 4)
        assert pack["timing"] == "asr_matched"
        assert all(i["at"] == 2.1 for i in pack["components"][1:])
    # Repeated words map to their actual later occurrence, not the first substring.
    repeated = [{"word": "先看画面", "start": a, "end": a + 0.8, "conf": 1} for a in (0.1, 1.2)]
    cues = auto_pack.match_cues("先看画面，先看画面。", repeated, 3)["cues"]
    assert cues[1]["start"] == 1.2


def test_missing_model_produces_simple_pack_and_review_warning(monkeypatch):
    class Missing:
        def __init__(self, _):
            raise RuntimeError("model missing")
    monkeypatch.setattr(auto_pack, "VoskASRProvider", Missing)
    result = auto_pack.prepare("unused.mp4", "台词。", 4, "warm", "")
    assert result["alignment"]["status"] == "fallback"
    assert result["warnings"]
    assert [i["use"] for i in result["pack"]["components"]] == ["TextCard"]
    assert result["pack"]["timing"] == "estimated"


def test_one_request_cli_renders_local_asr_captions_and_records_fallback(tmp_path, monkeypatch, capsys):
    ffmpeg = native_assembly._find_ffmpeg(None)
    if not make.doctor()["ffmpeg"]["subtitles"]:
        pytest.skip("FFmpeg subtitles is required")
    job = tmp_path / "completed"
    job.mkdir()
    source = job / "original.mp4"
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=180x320:r=30:d=4",
                    "-f", "lavfi", "-i", "sine=duration=4", "-c:v", "libx264", "-c:a", "aac", str(source)], check=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    (job / "job.json").write_text(json.dumps({"version": 1, "status": "complete",
        "spec": {"mode": "native", "text": "先看画面，再听声音。"}, "expected_sha256": digest}), encoding="utf-8")
    class LocalASR:
        def __init__(self, _):
            pass
        def transcribe(self, _):
            return _words()
    monkeypatch.setattr(auto_pack, "VoskASRProvider", LocalASR)
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted generation gateway"))
    for request, style in (("把这条做成知识分享", "explainer"), ("做成带货介绍", "promo"), ("做成情感陪伴", "warm")):
        output = tmp_path / style
        assert make.main(["restyle", "--job-dir", str(job), "--request", request,
                          "--output-dir", str(output)]) == 0
        result = json.loads(capsys.readouterr().out)
        assert result["generation_requests"] == 0 and result["alignment_status"] == "matched"
        assert result["presentation"]["style"] == style
        captions = (output / "subtitles.srt").read_text(encoding="utf-8")
        assert "00:00:00,400 --> 00:00:01,600" in captions
        assert "00:00:02,100 --> 00:00:03,400" in captions
        qa = json.loads((output / "qa.json").read_text(encoding="utf-8"))
        assert qa["subtitle_timing"] == "vosk_matched_sentence_bounds"
        assert qa["quality_verdict"] == "unverified" and qa["tail_trim"] == "disabled"
        assert (output / "alignment.json").exists() and (output / "pack.json").exists()
        frames = []
        for name in ("original", "final"):
            path = tmp_path / f'{style}-{name}.png'
            subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-ss", "2.6", "-i", str(output / f'{name}.mp4'),
                            "-frames:v", "1", str(path)], check=True)
            with Image.open(path) as image:
                frames.append(image.convert("RGB"))
        delta = ImageChops.difference(*frames).crop((30, 800, 690, 1100)).convert("L")
        assert sum(delta.histogram()[41:]) > 400
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    image = tmp_path / "photo.png"
    Image.new("RGB", (32, 48), "white").save(image)
    plan = make.create_plan(str(image), "先看画面，再听声音。", str(tmp_path / "project"))
    project = tmp_path / "project"
    shutil.copytree(job, project / "segment-001")
    plan_bytes = (project / "plan.json").read_bytes()
    assert make.main(["restyle", "--project", plan["project"], "--request", "知识分享",
                      "--output-dir", str(tmp_path / "project-edit")]) == 0
    assert json.loads(capsys.readouterr().out)["alignment_status"] == "matched"
    assert (project / "plan.json").read_bytes() == plan_bytes
    assert not (project / "approval.json").exists()
    monkeypatch.setattr(LocalASR, "transcribe", lambda *_: [{**w, "conf": 0.1} for w in _words()])
    fallback = tmp_path / "fallback"
    assert make.main(["restyle", "--job-dir", str(job), "--request", "知识分享", "--output-dir", str(fallback)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["alignment_status"] == "fallback" and result["warnings"]
    qa = json.loads((fallback / "qa.json").read_text(encoding="utf-8"))
    assert qa["subtitle_timing"] == "estimated_from_segment_container_duration"
    assert qa["rendered_components"] == ["TextCard"]
