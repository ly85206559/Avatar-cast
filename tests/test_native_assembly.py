import array
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from dhp import native_assembly
from dhp.native_assembly import _duration, _find_ffmpeg, assemble


def _job(parent: Path, name: str, payload: bytes, text: str = "sample text", status: str = "complete") -> Path:
    directory = parent / name
    directory.mkdir()
    (directory / "original.mp4").write_bytes(payload)
    (directory / "job.json").write_text(json.dumps({
        "version": 1, "status": status, "spec": {"mode": "native", "text": text},
        "expected_sha256": hashlib.sha256(payload).hexdigest(),
    }), encoding="utf-8")
    return directory


@pytest.fixture(scope="module")
def ffmpeg():
    try:
        executable = _find_ffmpeg(None)
    except RuntimeError:
        pytest.skip("FFmpeg is required for the local assembly integration test")
    filters = subprocess.run([executable, "-hide_banner", "-filters"], capture_output=True, text=True, check=True)
    if " subtitles " not in filters.stdout:
        pytest.skip("FFmpeg libass subtitles filter is required")
    return executable


def _make_video(ffmpeg: str, path: Path, color: str, size: str, frequency: int) -> None:
    subprocess.run([
        ffmpeg, "-nostdin", "-v", "error",
        "-f", "lavfi", "-i", f"color=c={color}:s={size}:r=24:d=0.7",
        "-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=16000:duration=0.7",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path),
    ], check=True)


def _frame(ffmpeg: str, video: Path, at: float, output: Path) -> Image.Image:
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-ss", str(at), "-i", str(video),
                    "-frames:v", "1", str(output)], check=True)
    return Image.open(output).convert("RGB")


def _audio_strengths(ffmpeg: str, video: Path, at: float) -> tuple[float, float]:
    audio = subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-ss", str(at), "-i", str(video),
                            "-t", "0.25", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                           capture_output=True, check=True).stdout
    samples = array.array("h", audio)
    if not samples:
        raise AssertionError("The expected native audio is missing")

    def strength(freq):
        return abs(sum(sample * complex(math.cos(2 * math.pi * freq * i / 8000),
                                        math.sin(2 * math.pi * freq * i / 8000))
                       for i, sample in enumerate(samples)))

    return strength(440), strength(880)


def test_assembly_preserves_both_audio_segments_pads_and_renders_estimated_captions(tmp_path, ffmpeg):
    sources = []
    for name, color, size, freq, text in [
        ("first", "red", "90x160", 440, "第一段测试这是比较长的字幕需要按两行分成多个字幕段以保证画面可读同时标明所有时间均为估算"),
        ("second", "lime", "160x90", 880, "第二段测试"),
    ]:
        video = tmp_path / f"{name}.mp4"
        _make_video(ffmpeg, video, color, size, freq)
        sources.append(_job(tmp_path, name, video.read_bytes(), text=text))

    output = tmp_path / "assembled"
    # Reusing a clip must be reported as such; three segments do not mean
    # three independent generations.
    report = assemble([str(sources[0]), str(sources[1]), str(sources[0])], str(output), ffmpeg)
    qa = json.loads((output / "qa.json").read_text(encoding="utf-8"))
    assert report == qa
    assert qa["status"] == "assembled" and qa["quality_verdict"] == "unverified"
    assert qa["subtitle_timing"] == "estimated_from_segment_container_duration"
    assert qa["human_review"] == "not_reviewed" and qa["publication_approval"] == "not_granted"
    assert qa["ai_label"] == "burned_in_video" and qa["ai_label_text"] == "AI 数字人演绎"
    assert qa["description_label"] == "not_checked"
    assert qa["segment_count"] == 3 and qa["unique_source_count"] == 2
    assert qa["reused_source_video"] is True
    srt = (output / "subtitles.srt").read_text(encoding="utf-8")
    assert "第一段测试" in srt and "第二段测试" in srt and srt.count(" --> ") >= 5
    assert all(len(cue.splitlines()[2:]) <= 2 for cue in srt.strip().split("\n\n"))
    last = re.findall(r"--> (\d+):(\d+):(\d+),(\d+)", srt)[-1]
    last_end = int(last[0]) * 3600 + int(last[1]) * 60 + int(last[2]) + int(last[3]) / 1000
    assert last_end <= qa["output_duration_sec"] + 0.001
    assert abs(_duration(output / "final.mp4", ffmpeg) - sum(s["duration_sec"] for s in qa["segments"])) < 0.2

    first_at = 0.2
    second_at = qa["segments"][0]["duration_sec"] + 0.2
    first = _frame(ffmpeg, output / "original.mp4", first_at, tmp_path / "first.png")
    second = _frame(ffmpeg, output / "original.mp4", second_at, tmp_path / "second.png")
    assert first.size == second.size == (720, 1280)
    assert first.getpixel((360, 100))[0] > 150  # portrait fills the frame
    assert max(second.getpixel((360, 100))) < 25  # landscape is padded, not stretched
    center = second.getpixel((360, 640))
    assert center[1] > 150 and center[0] < 30
    first_audio = _audio_strengths(ffmpeg, output / "final.mp4", first_at)
    second_audio = _audio_strengths(ffmpeg, output / "final.mp4", second_at)
    assert first_audio[0] > first_audio[1] * 3
    assert second_audio[1] > second_audio[0] * 3

    captioned = _frame(ffmpeg, output / "final.mp4", first_at, tmp_path / "captioned.png")
    delta = ImageChops.difference(first, captioned).crop((0, 920, 720, 1280)).convert("L")
    assert sum(delta.histogram()[41:]) > 100  # subtitles are visible in decoded pixels

    # The independent disclosure stays visible at the top from start to end;
    # compare with the unlabelled raw cut, not with a hardcoded font bitmap.
    for index, at in enumerate((0.2, qa["output_duration_sec"] / 2, qa["output_duration_sec"] - 0.25)):
        raw_frame = _frame(ffmpeg, output / "original.mp4", at, tmp_path / f"raw-label-{index}.png")
        final_frame = _frame(ffmpeg, output / "final.mp4", at, tmp_path / f"final-label-{index}.png")
        top_delta = ImageChops.difference(raw_frame, final_frame).crop((0, 0, 720, 100)).convert("L")
        assert sum(top_delta.histogram()[41:]) > 100


def test_rejects_missing_or_changed_inputs_before_creating_output(tmp_path):
    first = _job(tmp_path, "first", b"valid hash placeholder")
    second = _job(tmp_path, "second", b"original")
    (second / "original.mp4").write_bytes(b"changed")
    output = tmp_path / "assembled"
    with pytest.raises(ValueError, match="checksum changed"):
        assemble([str(first), str(second)], str(output))
    assert not output.exists()


def test_rejects_incomplete_jobs_and_existing_output(tmp_path):
    first = _job(tmp_path, "first", b"first", status="accepted")
    second = _job(tmp_path, "second", b"second")
    output = tmp_path / "assembled"
    with pytest.raises(ValueError, match="not complete"):
        assemble([str(first), str(second)], str(output))
    assert not output.exists()
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("do not replace", encoding="utf-8")
    with pytest.raises(ValueError, match="does not already exist"):
        assemble([str(first), str(second)], str(output))
    assert sentinel.read_text(encoding="utf-8") == "do not replace"


@pytest.mark.parametrize("failure", ["partial_final", "qa_finalize"])
def test_failed_publication_never_leaves_a_false_complete_video(tmp_path, ffmpeg, monkeypatch, failure):
    source = tmp_path / "source.mp4"
    _make_video(ffmpeg, source, "red", "90x160", 440)
    job = _job(tmp_path, "source-job", source.read_bytes())
    output = tmp_path / "assembled"
    if failure == "partial_final":
        real_copy = native_assembly.shutil.copyfileobj

        def fail_final_copy(src, dst, *args, **kwargs):
            if Path(dst.name).name == "final.mp4":
                dst.write(b"partial")
                raise OSError("simulated full disk")
            return real_copy(src, dst, *args, **kwargs)

        monkeypatch.setattr(native_assembly.shutil, "copyfileobj", fail_final_copy)
    else:
        real_replace = Path.replace

        def fail_qa_replace(self, target):
            if self.name == "qa-final.json":
                raise OSError("simulated QA promotion failure")
            return real_replace(self, target)

        monkeypatch.setattr(Path, "replace", fail_qa_replace)

    with pytest.raises(OSError, match="simulated"):
        assemble([str(job), str(job)], str(output), ffmpeg)
    assert not (output / "final.mp4").exists()
    assert (output / "original.mp4").exists()
    assert (output / "subtitles.srt").exists()
    qa = json.loads((output / "qa.json").read_text(encoding="utf-8"))
    assert qa["status"] == "assembling" and qa["quality_verdict"] == "unverified"
