import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from dhp import make, native_assembly, presentation


def test_assistant_brief_creates_defaults_without_contacting_gateway(tmp_path, monkeypatch):
    image = tmp_path / "photo.png"
    Image.new("RGB", (32, 48), "white").save(image)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("plan contacted provider"))
    brief = {"request": "帮我做一条咖啡店推广", "script": "忙碌一天，来喝杯咖啡。让每次停留，都成为放松的小片刻。", "title": "给生活一点香气"}
    result = make.create_brief_plan(str(image), brief)
    assert Path(result["project"]).parent == tmp_path / "outputs"
    assert result["segments"] == [brief["script"]]
    assert result["request"] != result["segments"][0]
    assert result["presentation"] == {"style": "promo", "title": brief["title"]}
    assert not (Path(result["project"]) / "approval.json").exists()
    with pytest.raises(ValueError, match="assistant-drafted script"):
        make.create_brief_plan(str(image), {"request": "介绍咖啡店"})


def test_overlay_treats_user_title_as_data(tmp_path):
    output = tmp_path / "overlay.ass"
    presentation.write_overlay(output, 3, presentation.prepare("clean", r"{\pos(0,0)}测试"))
    contents = output.read_text(encoding="utf-8")
    assert r"{\pos(0,0)}" not in contents
    assert "AI 数字人演绎" in contents
    with pytest.raises(ValueError):
        presentation.prepare(["bad"])


def _video(ffmpeg, output, sound):
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=gray:s=90x160:r=30:d=4",
                    "-f", "lavfi", "-i", sound, "-af", "apad=whole_dur=4", "-t", "4",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(output)], check=True)


def _frame(ffmpeg, path, output):
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-ss", "0.3", "-i", str(path),
                    "-frames:v", "1", str(output)], check=True)
    return Image.open(output).convert("RGB")


def test_restyle_renders_three_distinct_styles_and_trims_only_terminal_silence(tmp_path, monkeypatch):
    try:
        ffmpeg = native_assembly._find_ffmpeg(None)
    except RuntimeError:
        pytest.skip("FFmpeg is required")
    if not make.doctor()["ffmpeg"]["subtitles"]:
        pytest.skip("FFmpeg subtitles is required")
    source = tmp_path / "source.mp4"
    _video(ffmpeg, source, "sine=frequency=440:sample_rate=16000:duration=1.2")
    image = tmp_path / "photo.png"
    Image.new("RGB", (32, 48), "white").save(image)
    plan = make.create_plan(str(image), "这是一段测试口播。", str(tmp_path / "project"))
    root = Path(plan["project"])
    original_plan = (root / "plan.json").read_bytes()
    job = root / "segment-001"
    job.mkdir()
    original = source.read_bytes()
    (job / "original.mp4").write_bytes(original)
    (job / "job.json").write_text(json.dumps({"version": 1, "status": "complete",
        "spec": {"mode": "native", "text": "这是一段测试口播。"},
        "expected_sha256": hashlib.sha256(original).hexdigest()}), encoding="utf-8")
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("restyle contacted provider"))
    image.unlink()  # Local edits need only completed original clips.
    frames = []
    for style in presentation.STYLES:
        result = make.restyle_project(str(root), style, "照片变成口播")
        assert result["generation_requests"] == 0
        qa = json.loads(Path(result["qa"]).read_text(encoding="utf-8"))
        assert 1.8 < qa["output_duration_sec"] < 2.2
        assert qa["segments"][0]["source_duration_sec"] >= 4
        assert qa["quality_verdict"] == "unverified"
        frame = _frame(ffmpeg, result["video"], tmp_path / f"{style}.png")
        raw_frame = _frame(ffmpeg, Path(result["video"]).with_name("original.mp4"), tmp_path / f"{style}-raw.png")
        title_area = (0, 900, 720, 1060) if style == "promo" else (0, 80, 720, 240)
        delta = ImageChops.difference(frame, raw_frame).crop(title_area).convert("L")
        assert sum(delta.histogram()[41:]) > 400  # Packaging is visible in decoded pixels.
        frames.append(frame)
    assert all(ImageChops.difference(frames[0], f).getbbox() for f in frames[1:])
    assert (job / "original.mp4").read_bytes() == original
    assert (root / "plan.json").read_bytes() == original_plan
    assert not (root / "approval.json").exists()
    silent = tmp_path / "silent.mp4"
    _video(ffmpeg, silent, "anullsrc=r=16000:cl=mono")
    assert native_assembly._tail_duration(silent, 4, ffmpeg) == 4


def test_restyle_does_not_generate_a_missing_segment(tmp_path, monkeypatch):
    image = tmp_path / "photo.png"
    Image.new("RGB", (32, 48), "white").save(image)
    plan = make.create_plan(str(image), "一段测试。", str(tmp_path / "project"))
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("restyle contacted provider"))
    with pytest.raises(ValueError, match="job.json"):
        make.restyle_project(plan["project"], "promo")
