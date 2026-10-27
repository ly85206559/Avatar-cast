import shutil
import subprocess

import pytest

from dhp.render import segment_keep_sec, write_srt

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def test_segment_keep_adds_quarter_second_tail():
    assert segment_keep_sec(6.0) == 6.25


def test_write_srt_format(tmp_path):
    out = tmp_path / "out.srt"
    write_srt([
        {"text": "hello", "start": 0.0, "end": 6.25},
        {"text": "world", "start": 6.25, "end": 11.5},
    ], str(out))
    text = out.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:06,250" in text
    assert "00:00:06,250 --> 00:00:11,500" in text
    assert "hello" in text and "world" in text


def test_normalize_and_concat(tmp_path):
    from dhp.render import concat_clips, normalize_clip, probe_duration_sec
    # 1s colour video + sine audio, generated locally, no network.
    src = tmp_path / "src.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=c=blue:s=320x180:d=1",
        "-f", "lavfi", "-i", "sine=frequency=440:d=1",
        "-shortest", str(src),
    ], check=True)
    norm = tmp_path / "norm.mp4"
    normalize_clip(str(src), str(norm), 1.0)
    assert abs(probe_duration_sec(str(norm)) - 1.0) < 0.15
    final = tmp_path / "final.mp4"
    concat_clips([str(norm), str(norm)], str(final))
    assert abs(probe_duration_sec(str(final)) - 2.0) < 0.3
