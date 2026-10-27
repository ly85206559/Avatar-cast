"""ffmpeg assembly: the one place that touches media files.

Rules, taken from the verified local assembly run (not from any other
project's pipeline):
- Every segment is cut to "speech end + 0.25s" -- never with ``-shortest``,
  which used to clip the tail.
- Output is normalised to 30 fps, 48 kHz, -16 LUFS loudnorm, so segments
  from different generators do not jump in volume or speed.
- Subtitles come from segment text + segment timings, written as SRT.
  SRT is generated, never burned into the picture by the generator.

All functions shell out to the system ``ffmpeg``/``ffprobe``. If ffmpeg
is missing, they raise RuntimeError with a plain message instead of
pretending to have rendered.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

TAIL_SEC = 0.25
TARGET_FPS = 30
TARGET_RATE = 48000
TARGET_LUFS = -16


def _need(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise RuntimeError(f"{tool} is not installed; install ffmpeg to render.")
    return path


def probe_duration_sec(path: str) -> float:
    _need("ffprobe")
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", path],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


def segment_keep_sec(audio_duration_sec: float) -> float:
    """How long a segment stays on screen: speech plus the 0.25s tail."""
    return round(audio_duration_sec + TAIL_SEC, 3)


def write_srt(segments: list[dict], path: str) -> str:
    """segments: [{"text": str, "start": float, "end": float}, ...].

    Times are in seconds from the start of the final video. Returns the
    path written.
    """
    def fmt(t: float) -> str:
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02d}:{(ms // 60000) % 60:02d}:{(ms // 1000) % 60:02d},{ms % 1000:03d}"

    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{fmt(seg['start'])} --> {fmt(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return path


def normalize_clip(input_path: str, output_path: str, keep_sec: float) -> str:
    """Trim to keep_sec, normalise loudness/fps/rate. Returns output_path."""
    _need("ffmpeg")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", input_path,
        "-t", str(keep_sec),
        "-vf", f"fps={TARGET_FPS}",
        "-af", f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11,aresample={TARGET_RATE}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        output_path,
    ], check=True)
    return output_path


def concat_clips(clip_paths: list[str], output_path: str) -> str:
    """Concatenate already-normalised clips (same codec/fps/rate)."""
    _need("ffmpeg")
    list_file = Path(output_path).with_suffix(".concat.txt")
    list_file.write_text(
        "".join(f"file '{Path(p).resolve()}'\n" for p in clip_paths),
        encoding="utf-8",
    )
    try:
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy", output_path,
        ], check=True)
    finally:
        list_file.unlink(missing_ok=True)
    return output_path
