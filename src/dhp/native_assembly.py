"""Assemble completed native clips locally; all subtitle timings are estimates."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_ffmpeg(explicit: str | None) -> str:
    executable = explicit or shutil.which("ffmpeg")
    if executable is None:
        try:
            from imageio_ffmpeg import get_ffmpeg_exe

            executable = get_ffmpeg_exe()
        except (ImportError, OSError, RuntimeError):
            pass
    if not executable or not shutil.which(executable):
        raise RuntimeError("FFmpeg is required; install it or imageio-ffmpeg.")
    return str(executable)


def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError("FFmpeg failed: " + result.stderr[-3000:].strip())
    return result


def _duration(path: Path, ffmpeg: str) -> float:
    # Decode both streams before creating any output. FFmpeg reports the input
    # container duration here; its printed precision makes captions estimates.
    result = _run([ffmpeg, "-nostdin", "-xerror", "-hide_banner", "-nostats", "-i", str(path),
                   "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"])
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        raise ValueError(f"Cannot measure duration of {path}; FFmpeg did not report one.")
    duration = int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"Invalid measured duration for {path}.")
    return duration


def _timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    return (f"{milliseconds // 3600000:02}:{(milliseconds // 60000) % 60:02}:"
            f"{(milliseconds // 1000) % 60:02},{milliseconds % 1000:03}")


def _remove_owned(path: Path, identity: os.stat_result) -> None:
    """Remove only the exact file this assembly call created."""
    try:
        current = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return
    if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
        path.unlink()


def _copy_exclusive(source: Path, destination: Path) -> os.stat_result:
    identity = None
    try:
        with source.open("rb") as src, destination.open("xb") as dst:
            identity = os.fstat(dst.fileno())
            shutil.copyfileobj(src, dst)
    except BaseException:
        if identity is not None:
            _remove_owned(destination, identity)
        raise
    return identity


def assemble(job_dirs: list[str], output_dir: str, ffmpeg: str | None = None) -> dict:
    """Produce an experimental subtitled cut from at least two completed jobs.

    The input hashes are checked before rendering. Subtitle cues divide each
    measured container duration by text length, not actual speech boundaries.
    No speech, identity, lip-sync or human acceptance is inferred.
    """
    if len(job_dirs) < 2:
        raise ValueError("At least two completed native jobs are required.")
    output = Path(output_dir).expanduser().absolute()
    if os.path.lexists(output):
        raise ValueError("Choose an output directory that does not already exist.")

    inputs = []
    for job_dir in job_dirs:
        directory = Path(job_dir).expanduser().resolve()
        try:
            job = json.loads((directory / "job.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"A readable job.json is required in {directory}.") from exc
        if not isinstance(job, dict) or job.get("version") != 1 or job.get("status") != "complete":
            raise ValueError(f"The native job in {directory} is not complete.")
        spec = job.get("spec")
        if not isinstance(spec, dict) or spec.get("mode") != "native":
            raise ValueError(f"The job in {directory} is not a native job.")
        text = spec.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"The native job in {directory} has no script text.")
        expected = job.get("expected_sha256")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
            raise ValueError(f"The native job in {directory} has no valid video checksum.")
        video = directory / "original.mp4"
        if not video.is_file() or _sha256(video) != expected.lower():
            raise ValueError(f"The original video in {directory} is missing or its checksum changed.")
        inputs.append({"job_dir": str(directory), "video": video, "sha256": expected.lower(), "text": text})

    executable = _find_ffmpeg(ffmpeg)
    for item in inputs:
        item["duration_sec"] = _duration(item["video"], executable)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    with tempfile.TemporaryDirectory(prefix=".assemble-", dir=output) as work_dir:
        work = Path(work_dir)
        # Calculate scaled dimensions from display aspect ratio, then pad. This
        # avoids stretching even when the input has non-square pixels.
        scale = ("scale=w='if(gte(a*sar,9/16),720,max(2,trunc(1280*a*sar/2)*2))':"
                 "h='if(gte(a*sar,9/16),max(2,trunc(720/(a*sar)/2)*2),1280)',"
                 "setsar=1,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=black,fps=30")
        filters = []
        concat_inputs = []
        command = [executable, "-nostdin", "-v", "error"]
        for index, item in enumerate(inputs):
            command += ["-i", str(item["video"])]
            filters.append(f"[{index}:v:0]setpts=PTS-STARTPTS,{scale}[v{index}]")
            filters.append(f"[{index}:a:0]asetpts=PTS-STARTPTS,aresample=48000,"
                           f"aformat=sample_fmts=fltp:channel_layouts=stereo[a{index}]")
            concat_inputs.append(f"[v{index}][a{index}]")
        filters.append("".join(concat_inputs) + f"concat=n={len(inputs)}:v=1:a=1[outv][outa]")
        raw = work / "original.mp4"
        _run(command + ["-filter_complex", ";".join(filters), "-map", "[outv]", "-map", "[outa]",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-ar", "48000", "-movflags", "+faststart", str(raw)])

        captions = work / "subtitles.srt"
        cues = []
        offset = 0.0
        cue_index = 0
        raw_duration = _duration(raw, executable)
        timing_scale = min(1.0, raw_duration / sum(item["duration_sec"] for item in inputs))
        for item in inputs:
            text = " ".join(item["text"].split())
            groups = []
            for sentence in re.split(r"(?<=[。！？!?])", text):
                lines = textwrap.wrap(sentence, width=16, break_long_words=True, break_on_hyphens=False)
                # Avoid leaving a tiny fragment on a line by itself.
                if len(lines) > 1 and len(lines[-1]) < 5 and len(lines[-2]) > 8:
                    shift = 5 - len(lines[-1])
                    lines[-1] = lines[-2][-shift:] + lines[-1]
                    lines[-2] = lines[-2][:-shift]
                groups.extend(lines[i:i + 2] for i in range(0, len(lines), 2))
            weights = [sum(len(line) for line in group) for group in groups]
            segment_start = offset
            elapsed_weight = 0
            for group, weight in zip(groups, weights):
                cue_index += 1
                elapsed_weight += weight
                end = segment_start + item["duration_sec"] * timing_scale * elapsed_weight / sum(weights)
                cues.append(f"{cue_index}\n{_timestamp(offset)} --> {_timestamp(end)}\n" + "\n".join(group))
                offset = end
        captions.write_text("\n\n".join(cues) + "\n", encoding="utf-8")
        final = work / "final.mp4"
        _run([executable, "-nostdin", "-v", "error", "-i", str(raw),
              "-vf", "subtitles=subtitles.srt:force_style='FontName=Microsoft YaHei,FontSize=9,Bold=1,Outline=1,MarginV=18'",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
              "-c:a", "copy", "-movflags", "+faststart", str(final)], cwd=work)
        # Final full decode verifies the produced streams, not speech accuracy.
        final_duration = _duration(final, executable)
        if any(_sha256(item["video"]) != item["sha256"] for item in inputs):
            raise ValueError("A source video changed during assembly; no completed output was saved.")
        unique_sources = len({item["sha256"] for item in inputs})
        report = {
            "status": "assembled", "quality_verdict": "unverified", "experimental": True,
            "output_dir": str(output), "raw_video": "original.mp4", "video": "final.mp4",
            "subtitles": "subtitles.srt", "segment_count": len(inputs),
            "raw_video_sha256": _sha256(raw), "video_sha256": _sha256(final),
            "output_duration_sec": final_duration,
            "unique_source_count": unique_sources, "reused_source_video": unique_sources < len(inputs),
            "subtitle_timing": "estimated_from_segment_container_duration",
            "subtitle_review": "required", "speech_accuracy": "not_evaluated",
            "lip_sync": "not_evaluated", "identity_consistency": "not_evaluated",
            "human_review": "not_reviewed", "publication_approval": "not_granted", "ai_label": "not_checked",
            "native_audio": "preserved_content_reencoded_to_aac_48khz",
            "video_geometry": "720x1280_aspect_preserving_pad_30fps",
            "segments": [{"job_dir": item["job_dir"], "sha256": item["sha256"],
                          "duration_sec": item["duration_sec"], "text": item["text"]}
                         for item in inputs],
            "notice": "Subtitle cues are estimated from each segment duration, not word alignment; "
                      "review speech, timing, visual captions, lip sync, and AI labeling before release. "
                      + ("Source video is reused; segment count does not prove independent generations."
                         if unique_sources < len(inputs) else ""),
        }
        # Publish QA in an explicitly incomplete state first. Only mark it
        # assembled after the final file is fully copied into its new folder.
        staged_report = {**report, "status": "assembling"}
        (work / "qa.json").write_text(json.dumps(staged_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (work / "qa-final.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        qa_identity = _copy_exclusive(work / "qa.json", output / "qa.json")
        for name in ("original.mp4", "subtitles.srt"):
            _copy_exclusive(work / name, output / name)
        final_identity = _copy_exclusive(work / "final.mp4", output / "final.mp4")
        try:
            current_qa = (output / "qa.json").stat(follow_symlinks=False)
            if (current_qa.st_dev, current_qa.st_ino) != (qa_identity.st_dev, qa_identity.st_ino):
                raise RuntimeError("Assembly QA was replaced before it could be finalized.")
            (work / "qa-final.json").replace(output / "qa.json")
        except BaseException:
            _remove_owned(output / "final.mp4", final_identity)
            raise
    return report
