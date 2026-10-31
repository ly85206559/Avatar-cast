"""Acceptance coverage for a real local render using explicitly synthetic media."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

from dhp.dry_run import DryRunError, run_dry_run
from dhp.render import probe_duration_sec


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg and ffprobe are needed for the dry-run acceptance test",
)


def _inputs():
    script = [
        {"id": "s1", "shot": "talking_head", "text": "First test\n\nsegment"},
        {"id": "s2", "shot": "talking_head", "text": "Second test segment"},
        {"id": "s3", "shot": "talking_head", "text": "Third test segment"},
    ]
    brief = {"persona_id": "acceptance", "duration_target_sec": 33,
             "ratio": "16:9", "topic": "synthetic acceptance"}
    return script, brief


def _report(path):
    return json.loads((path / "qa.json").read_text(encoding="utf-8"))


def test_multi_segment_render_retry_cache_and_cli(tmp_path):
    script, brief = _inputs()
    cache = tmp_path / "cache"
    first = tmp_path / "first"
    result = run_dry_run(script, brief, first, cache, failure_attempts={"s2": 1})
    qa = _report(first)
    assert result == qa
    assert qa["mode"] == "dry_run" and qa["status"] == "pass"
    assert qa["quality_verdict"] == "unverified"
    assert [segment["segment_id"] for segment in qa["segments"]] == ["s1", "s2", "s3"]
    assert qa["segments"][1]["retries"] == 1
    assert qa["segments"][1]["attempts"] == 2
    assert qa["segments"][1]["retry_reasons"]
    assert all(segment["verdict"] == "pass" for segment in qa["segments"])
    assert qa["cache"] == {"hits": 0, "misses": 3}
    assert qa["cost"]["currency"] == "SIMULATED"
    assert qa["cost"]["actual"] == 0
    assert qa["cost"]["simulated"] > qa["cost"]["estimated"] > 0
    assert all(segment["scores_kind"] == "simulated" for segment in qa["segments"])

    video = first / "final.mp4"
    assert 30 <= probe_duration_sec(str(video)) <= 60
    streams = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
        "-of", "json", str(video),
    ], text=True))["streams"]
    assert {stream["codec_type"] for stream in streams} >= {"video", "audio"}
    srt = (first / "subtitles.srt").read_text(encoding="utf-8")
    assert srt.count(" --> ") == 3
    assert all(" ".join(segment["text"].split()) in " ".join(srt.split()) for segment in script)
    assert len(re.split(r"\r?\n\s*\r?\n", srt.strip())) == 3
    timestamps = re.findall(r"(\d\d):(\d\d):(\d\d),(\d\d\d) --> "
                            r"(\d\d):(\d\d):(\d\d),(\d\d\d)", srt)
    def seconds(parts):
        h, m, s, ms = map(int, parts)
        return h * 3600 + m * 60 + s + ms / 1000
    ranges = [(seconds(t[:4]), seconds(t[4:])) for t in timestamps]
    assert ranges[0][0] == 0
    assert all(start < end <= probe_duration_sec(str(video)) for start, end in ranges)
    assert all(ranges[i][1] <= ranges[i + 1][0] for i in range(2))
    offset = 0.0
    for i, (start, _) in enumerate(ranges):
        assert abs(start - offset) < 0.01
        offset += probe_duration_sec(str(first / "segments" / f"{i:04d}.mp4"))

    script_file, brief_file = tmp_path / "script.json", tmp_path / "brief.json"
    script_file.write_text(json.dumps(script), encoding="utf-8")
    brief_file.write_text(json.dumps(brief), encoding="utf-8")
    second = tmp_path / "second"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    subprocess.run([
        sys.executable, "-m", "dhp.cli", str(script_file), "--brief", str(brief_file),
        "--dry-run", "--output-dir", str(second), "--cache-dir", str(cache),
    ], env=env, check=True, capture_output=True, text=True)
    cached = _report(second)
    assert cached["status"] == "pass"
    assert cached["quality_verdict"] == "unverified"
    assert cached["cache"] == {"hits": 3, "misses": 0}
    assert cached["cost"]["actual"] == 0
    assert cached["cost"]["estimated"] == 0
    assert cached["cost"]["simulated"] == 0
    assert cached["cost"]["cache_savings"] == qa["cost"]["estimated"]
    assert all(segment["cache_hit"] for segment in cached["segments"])
    assert [s["cache_key"] for s in cached["segments"]] == [s["cache_key"] for s in qa["segments"]]
    assert [s["audio_sha256"] for s in cached["segments"]] == [s["audio_sha256"] for s in qa["segments"]]
    assert 30 <= probe_duration_sec(str(second / "final.mp4")) <= 60

    # Same-length edit preserves duration allocation, so only this segment changes.
    edited = [dict(segment) for segment in script]
    edited[2]["text"] = "Third test section"
    assert len(edited[2]["text"]) == len(script[2]["text"])
    third = tmp_path / "third"
    run_dry_run(edited, brief, third, cache)
    changed = _report(third)
    assert changed["cache"] == {"hits": 2, "misses": 1}
    assert [s["cache_hit"] for s in changed["segments"]] == [True, True, False]
    assert changed["segments"][2]["cache_key"] != qa["segments"][2]["cache_key"]

    # Corrupting a cached artifact must trigger regeneration, not reuse.
    (cache / (changed["segments"][2]["cache_key"] + ".mp4")).write_bytes(b"corrupt")
    fourth = tmp_path / "fourth"
    run_dry_run(edited, brief, fourth, cache)
    recovered = _report(fourth)
    assert recovered["cache"] == {"hits": 2, "misses": 1}
    assert 30 <= probe_duration_sec(str(fourth / "final.mp4")) <= 60


def test_first_segment_failure_stops_without_final_export(tmp_path):
    script, brief = _inputs()
    successful = tmp_path / "successful"
    run_dry_run(script, brief, successful, tmp_path / "successful-cache")
    video_before = (successful / "final.mp4").read_bytes()
    qa_before = (successful / "qa.json").read_bytes()
    with pytest.raises(FileExistsError):
        run_dry_run(script, brief, successful, tmp_path / "cache", failure_attempts={"s1": 4})
    assert (successful / "final.mp4").read_bytes() == video_before
    assert (successful / "qa.json").read_bytes() == qa_before

    output = tmp_path / "failed"
    with pytest.raises(DryRunError):
        run_dry_run(script, brief, output, tmp_path / "cache", failure_attempts={"s1": 4})
    qa = _report(output)
    assert qa["mode"] == "dry_run" and qa["status"] == "fail"
    assert qa["segments"][0]["verdict"] == "fail"
    assert qa["segments"][0]["retries"] == 3
    assert not any(s["segment_id"] in {"s2", "s3"} and s["attempts"] for s in qa["segments"])
    assert qa["cost"]["actual"] == 0
    assert not (output / "final.mp4").exists()
    assert not (output / "subtitles.srt").exists()


@pytest.mark.parametrize("target", [30, 60])
def test_export_duration_in_range_at_requested_boundaries(tmp_path, target):
    script, brief = _inputs()
    brief["duration_target_sec"] = target
    output = tmp_path / str(target)
    run_dry_run(script, brief, output, tmp_path / "cache")
    duration = probe_duration_sec(str(output / "final.mp4"))
    assert 30 <= duration <= 60
    assert _report(output)["output"]["duration_sec"] == duration


def test_export_has_visible_cards_and_chinese_captions(tmp_path):
    script = [
        {"id": "s1", "shot": "talking_head", "text": "第一段字幕，检查中文显示。"},
        {"id": "s2", "shot": "talking_head", "text": "第二段字幕，检查片段切换。"},
        {"id": "s3", "shot": "talking_head", "text": "第三段字幕，检查最终导出。"},
    ]
    output = tmp_path / "visible"
    run_dry_run(script, {"duration_target_sec": 30}, output, tmp_path / "cache")
    frames = []
    for position in (2, 12, 22):
        frame = subprocess.check_output([
            "ffmpeg", "-v", "error", "-ss", str(position), "-i", str(output / "final.mp4"),
            "-frames:v", "1", "-vf", "scale=320:180", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ])
        assert len(frame) == 320 * 180 * 3
        # Check decoded pixels, not just that an MP4 or sidecar subtitle exists.
        for start, end in ((0, 120), (120, 180)):
            band = frame[start * 320 * 3:end * 320 * 3]
            bright = sum(min(band[i:i + 3]) > 180 for i in range(0, len(band), 3))
            assert bright > 80, f"missing visible card or burned-in caption in rows {start}:{end}; bright pixels={bright}"
        frames.append(frame)
    assert len(set(frames)) == 3, "all segments still look like the same blank frame"
