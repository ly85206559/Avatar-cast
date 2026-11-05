"""Local media validation and presenter-in-picture showcase rendering."""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from PIL import Image, UnidentifiedImageError


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".webm"}


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def prepare_asset(path: str) -> dict:
    """Inspect a local image or video before including it in a plan."""
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Showcase media must be a local file path.")
    source = Path(path).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in IMAGE_SUFFIXES | VIDEO_SUFFIXES:
        raise ValueError("Showcase media must be a local JPG, PNG, WebP, MP4, MOV or WebM file.")
    kind = "image" if source.suffix.lower() in IMAGE_SUFFIXES else "video"
    if kind == "image":
        try:
            with Image.open(source) as image:
                if image.format not in ("JPEG", "PNG", "WEBP"):
                    raise ValueError("Unsupported showcase image format.")
                image.verify()
        except (OSError, UnidentifiedImageError) as exc:
            raise ValueError("Cannot read the showcase image.") from exc
    else:
        from .native_assembly import _find_ffmpeg

        try:
            subprocess.run([_find_ffmpeg(None), "-nostdin", "-v", "error", "-i", str(source),
                            "-map", "0:v:0", "-frames:v", "1", "-f", "null", "-"],
                           check=True, capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError("Cannot decode a frame from the showcase video.") from exc
    return {"path": str(source), "sha256": _digest(source), "type": kind}


def validate_asset(asset: dict) -> None:
    if (not isinstance(asset, dict) or set(asset) != {"path", "sha256", "type"}
            or not isinstance(asset["path"], str) or not Path(asset["path"]).is_absolute()
            or not re.fullmatch(r"[0-9a-f]{64}", str(asset["sha256"]))
            or asset["type"] not in ("image", "video")):
        raise ValueError("Invalid showcase media in the plan.")
    path = Path(asset["path"])
    suffixes = IMAGE_SUFFIXES if asset["type"] == "image" else VIDEO_SUFFIXES
    if path.suffix.lower() not in suffixes:
        raise ValueError("Invalid showcase media type in the plan.")


def verify_asset(asset: dict) -> None:
    validate_asset(asset)
    path = Path(asset["path"])
    if not path.is_file() or _digest(path) != asset["sha256"]:
        raise ValueError("Showcase media changed or is missing; select it again.")


def scene(duration: float, cues: list[dict], matched: bool, beats: dict | None,
          allow_estimate: bool) -> dict:
    """Use the demonstration beat if available; otherwise estimate a middle scene."""
    if beats:
        from .content_templates import _beat_cues

        roles = _beat_cues(beats, cues, duration, matched, allow_estimate,
                           keys=("hook", "problem", "demo", "fit"))
        if roles and roles[2]["end"] - roles[2]["start"] >= 0.5:
            return {"at": roles[2]["start"], "until": roles[2]["end"],
                    "timing": "asr_matched" if matched else "estimated"}
    return {"at": duration * 0.25, "until": duration * 0.75, "timing": "estimated"}


def render(raw: Path, asset: dict, timing: dict, output: Path, ffmpeg: str,
           caption_filter: str, cwd: Path) -> None:
    """Cut to the supplied media with the original presenter in a small window."""
    start, end = timing["at"], timing["until"]
    input_options = ["-loop", "1", "-framerate", "30"] if asset["type"] == "image" else ["-stream_loop", "-1"]
    filters = (
        "[0:v]split=2[host][small];"
        "[small]scale=216:384,setsar=1,drawbox=x=0:y=0:w=iw:h=ih:color=white@0.8:t=4[pip];"
        "[1:v]fps=30,scale=720:1280:force_original_aspect_ratio=decrease,"
        "pad=720:1280:(ow-iw)/2:(oh-ih)/8:color=0x111c28,setsar=1,"
        f"setpts=PTS-STARTPTS+{start:.6f}/TB[media];"
        "[media][pip]overlay=480:730:shortest=1[scene];"
        f"[host][scene]overlay=0:0:enable='gte(t,{start:.6f})*lt(t,{end:.6f})':eof_action=pass,"
        f"{caption_filter}[out]"
    )
    command = [ffmpeg, "-nostdin", "-v", "error", "-i", str(raw), *input_options, "-i", asset["path"],
               "-filter_complex", filters, "-map", "[out]", "-map", "0:a:0",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
               "-c:a", "copy", "-movflags", "+faststart", str(output)]
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError("FFmpeg showcase failed: " + result.stderr[-3000:].strip())
