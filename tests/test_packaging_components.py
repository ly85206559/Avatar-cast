import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from dhp import make, native_assembly, packaging_components as components, presentation


def _pack():
    return {"timing": "estimated", "components": [
        {"use": "TextCard", "title": "问题先说清楚"},
        {"use": "KeywordEmphasis", "text": "突出一个重点"},
        {"use": "MetricCard", "value": "3", "unit": "项", "label": "画面、声音、字幕", "source": "测试示意"},
        {"use": "EvidenceFocus", "claim": "把依据展示出来", "evidence": "这是一条用于包装测试的示意摘录。", "source": "测试示意"},
        {"use": "ComparePanel", "dimension": "同一维度", "left": {"title": "原片", "text": "已有画面和声音"},
         "right": {"title": "包装", "text": "加字幕与重点"}},
        {"use": "StepProgress", "steps": ["看画面", "听声音"], "step_times": [5, 5.5]},
        {"use": "HostReframe", "scale": 1.18},
        {"use": "RecapBoard", "title": "回到最初的问题", "items": ["先看原片", "再看包装"]},
    ]}


def _timed_pack():
    pack = _pack()
    for index, item in enumerate(pack["components"]):
        item.update(at=index, until=index + 0.9)
    return pack


@pytest.mark.parametrize("change", [
    lambda p: p.update(timing="word_aligned"),
    lambda p: p["components"][0].update(at=float("nan")),
    lambda p: p["components"][0].update(until=True),
    lambda p: p["components"][0].update(use=[]),
    lambda p: p["components"][2].pop("source"),
    lambda p: p["components"][3].update(evidence=""),
    lambda p: p["components"][4].update(right={}),
    lambda p: p["components"][5].update(step_times=[5.6, 5.1]),
    lambda p: p["components"][6].update(scale=2),
    lambda p: p["components"][7].update(items=["只有一条"]),
])
def test_rejects_unusable_component_contracts(change):
    pack = _timed_pack()
    change(pack)
    with pytest.raises(ValueError):
        components.validate(pack)


def test_data_escaping_and_bounds():
    pack = {"timing": "estimated", "components": [
        {"use": "TextCard", "at": 0, "until": 2, "title": r"{\pos(0,0)}"}]}
    text = components.ass_events(pack, 3, "FFFFFF")
    assert r"{\pos(0,0)}" not in text
    with pytest.raises(ValueError, match="beyond"):
        components.validate(pack, 1)
    normalized = components.validate(pack)
    normalized["components"][0]["title"] = "changed"
    assert pack["components"][0]["title"] != "changed"
    assert presentation.prepare("auto", request="鼓励最近进步慢的人")["style"] == "warm"


def _frame(ffmpeg, video, at, destination):
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-ss", str(at), "-i", str(video),
                    "-frames:v", "1", str(destination)], check=True)
    with Image.open(destination) as frame:
        return frame.convert("RGB")


def test_eight_components_render_pixels_locally_and_preserve_audio(tmp_path, monkeypatch, capsys):
    ffmpeg = native_assembly._find_ffmpeg(None)
    if not make.doctor()["ffmpeg"]["subtitles"]:
        pytest.skip("FFmpeg subtitles is required")
    image = tmp_path / "photo.png"
    Image.new("RGB", (32, 48), "white").save(image)
    project = Path(make.create_plan(str(image), "这是一段组件测试。", str(tmp_path / "project"))["project"])
    job = project / "segment-001"
    job.mkdir()
    source = job / "original.mp4"
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=180x320:r=30:d=8.4",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=8.4",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)], check=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    (job / "job.json").write_text(json.dumps({"version": 1, "status": "complete",
        "spec": {"mode": "native", "text": "这是一段组件测试。"}, "expected_sha256": digest}), encoding="utf-8")
    original_plan = (project / "plan.json").read_bytes()
    pack = _timed_pack()
    pack_file = tmp_path / "pack.json"
    pack_file.write_text(json.dumps(pack), encoding="utf-8")
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("local edit contacted gateway"))
    output = tmp_path / "edit"
    assert make.main(["restyle", "--project", str(project), "--style", "explainer",
                      "--pack-file", str(pack_file), "--output-dir", str(output)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["generation_requests"] == 0
    qa = json.loads((output / "qa.json").read_text(encoding="utf-8"))
    assert set(qa["rendered_components"]) == set(components.COMPONENTS)
    assert qa["component_timing"] == "estimated" and qa["tail_trim"] == "disabled"
    assert qa["output_duration_sec"] >= 8.3
    for index, item in enumerate(pack["components"]):
        before = _frame(ffmpeg, output / "original.mp4", index + 0.4, tmp_path / f"before-{index}.png")
        after = _frame(ffmpeg, output / "final.mp4", index + 0.4, tmp_path / f"after-{index}.png")
        area = (50, 300, 650, 700) if item["use"] == "HostReframe" else (
            (30, 120, 690, 260) if item["use"] == "TextCard" else (30, 800, 690, 1100))
        delta = ImageChops.difference(before, after).crop(area).convert("L")
        assert sum(delta.histogram()[41:]) > 400, item["use"]
    streams = []
    for name in ("original.mp4", "final.mp4"):
        streams.append(subprocess.run([ffmpeg, "-v", "error", "-i", str(output / name), "-map", "0:a:0",
                                       "-c:a", "copy", "-f", "adts", "-"], capture_output=True, check=True).stdout)
    assert streams[0] == streams[1]
    baseline = tmp_path / "baseline"
    native_assembly.assemble([str(job)], str(baseline), ffmpeg)
    baseline_audio = subprocess.run([ffmpeg, "-v", "error", "-i", str(baseline / "original.mp4"),
        "-map", "0:a:0", "-c:a", "copy", "-f", "adts", "-"], capture_output=True, check=True).stdout
    assert baseline_audio == streams[0]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert (project / "plan.json").read_bytes() == original_plan
    assert not (project / "approval.json").exists()
    invalid = copy.deepcopy(pack)
    invalid["components"][-1]["until"] = 100
    with pytest.raises(ValueError, match="beyond"):
        make.restyle_project(str(project), "promo", output_dir=str(tmp_path / "invalid"), pack=invalid)
    assert not (tmp_path / "invalid").exists()
