import shutil
import subprocess
import math
import array

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


def test_locked_audio_replaces_video_audio(tmp_path):
    from dhp.render import normalize_clip, probe_duration_sec

    src = tmp_path / "with_other_audio.mp4"
    locked = tmp_path / "locked.wav"
    out = tmp_path / "out.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=c=blue:s=160x90:d=1",
        "-f", "lavfi", "-i", "sine=frequency=440:d=1.25",
        "-t", "1.25", str(src),
    ], check=True)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
        "sine=frequency=880:d=1", str(locked),
    ], check=True)
    normalize_clip(str(src), str(out), 1.25, locked_audio_path=str(locked))
    assert abs(probe_duration_sec(str(out)) - 1.25) < 0.15
    video_duration = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=duration", "-of", "default=nw=1:nk=1", str(out),
    ], capture_output=True, text=True, check=True).stdout
    assert float(video_duration) >= 1.24
    decoded = subprocess.run([
        "ffmpeg", "-v", "error", "-i", str(out), "-t", "0.8", "-ac", "1",
        "-ar", "8000", "-f", "s16le", "-",
    ], capture_output=True, check=True).stdout
    samples = array.array("h", decoded)

    def strength(frequency):
        return abs(sum(sample * math.sin(2 * math.pi * frequency * i / 8000)
                       for i, sample in enumerate(samples)))

    assert strength(880) > 10 * strength(440)
