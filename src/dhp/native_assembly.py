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

from . import presentation as packaging
from . import packaging_components


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


def _caption_groups(text: str) -> list[list[str]]:
    """Prefer complete clauses; never cut Latin words or decimal numbers."""
    groups = []
    for clause in re.split(r"(?<=[，。！？；：、!?;:])\s*|(?<=[,.])(?=\s|$)\s*", text):
        lines, line = [], ""
        for token in re.findall(r"[A-Za-z0-9]+(?:[.'’:/_%+-][A-Za-z0-9]+)*|.", clause):
            if line and len(line + token) > 16 and token not in "，。！？；：、,.!?;:":
                if line.strip():
                    lines.append(line.rstrip())
                line = token.lstrip()
            else:
                line += token
        if line.strip():
            lines.append(line.rstrip())
        groups.extend(lines[i:i + 2] for i in range(0, len(lines), 2))
    return groups


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


def _tail_duration(video: Path, duration: float, ffmpeg: str) -> float:
    """Trim only long terminal near-silence; preserve ambiguous or quiet clips."""
    result = _run([ffmpeg, "-nostdin", "-hide_banner", "-i", str(video), "-vn",
                   "-af", "silencedetect=noise=-50dB:d=2", "-f", "null", "-"])
    starts = re.findall(r"silence_start:\s*(-?\d+(?:\.\d+)?)", result.stderr)
    ends = re.findall(r"silence_end:\s*(-?\d+(?:\.\d+)?)", result.stderr)
    if not starts or not ends:
        return duration
    start, end = float(starts[-1]), float(ends[-1])
    if start < max(1.0, duration * 0.25) or end < duration - 0.15 or end - start < 2:
        return duration
    return min(duration, start + 0.8)


def assemble(job_dirs: list[str], output_dir: str, ffmpeg: str | None = None,
             presentation: dict | None = None, *, auto_request: str | None = None,
             asr_model: str | None = None, template: dict | None = None) -> dict:
    """Produce an experimental subtitled cut from completed native jobs.

    The input hashes are checked before rendering. Default captions divide each
    container duration by text length; automatic packaging can instead use
    conservatively matched local ASR sentence boundaries, with explicit fallback.
    No speech, identity, lip-sync or human acceptance is inferred.
    """
    if not job_dirs:
        raise ValueError("At least one completed native job is required.")
    if template is not None:
        from . import content_templates

        content_templates.validate(template)
        if auto_request is None or presentation is None:
            raise ValueError("A template requires automatic packaging and a presentation.")
    if auto_request is not None and (not isinstance(auto_request, str) or not auto_request.strip()):
        raise ValueError("A non-empty packaging request is required.")
    if auto_request is not None and presentation is None:
        presentation = packaging.prepare(request=auto_request)
    if presentation is not None:
        presentation = packaging.prepare(**presentation)
    pack = presentation.get("pack") if presentation else None
    if pack is not None and auto_request is not None:
        raise ValueError("Choose an automatic request or an explicit component timeline.")
    trim_tail = bool(presentation) and pack is None and auto_request is None
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
        measured = _duration(item["video"], executable)
        item["source_duration_sec"] = measured
        item["duration_sec"] = _tail_duration(item["video"], measured, executable) if trim_tail else measured

    if pack is not None:
        packaging_components.validate(pack, sum(item["duration_sec"] for item in inputs))

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
            video_trim = f"trim=duration={item['duration_sec']:.5f}," if trim_tail else ""
            audio_trim = f"apad,atrim=duration={item['duration_sec']:.5f}," if trim_tail else ""
            filters.append(f"[{index}:v:0]{video_trim}setpts=PTS-STARTPTS,{scale}[v{index}]")
            filters.append(f"[{index}:a:0]{audio_trim}asetpts=PTS-STARTPTS,aresample=48000,"
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
        automatic = None
        if auto_request is not None:
            from . import auto_pack

            automatic = auto_pack.prepare(str(raw), "".join(item["text"] for item in inputs),
                                          raw_duration, presentation["style"], presentation["title"], asr_model,
                                          template=template)
            pack = automatic["pack"]
            presentation = {**presentation, "pack": pack}
        timing_scale = min(1.0, raw_duration / sum(item["duration_sec"] for item in inputs))
        for item in inputs:
            text = " ".join(item["text"].split())
            groups = _caption_groups(text)
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
        if automatic and automatic["alignment"]["status"] == "matched":
            aligned_cues = automatic["alignment"]["cues"]
            captions.write_text("\n\n".join(
                f"{index}\n{_timestamp(cue['start'])} --> {_timestamp(cue['end'])}\n"
                + "\n".join(textwrap.wrap(cue["text"], width=16, break_long_words=True, break_on_hyphens=False))
                for index, cue in enumerate(aligned_cues, 1)) + "\n", encoding="utf-8")
        # Use an independent, full-duration ASS layer so the required label
        # remains at the top while the speech captions stay at the bottom.
        label = work / "ai-label.ass"
        end_centiseconds = math.ceil((raw_duration + 1) * 100)
        end = (f"{end_centiseconds // 360000}:{(end_centiseconds // 6000) % 60:02}:"
               f"{(end_centiseconds // 100) % 60:02}.{end_centiseconds % 100:02}")
        label.write_text(
            "[Script Info]\nScriptType: v4.00+\nPlayResX: 720\nPlayResY: 1280\n"
            "[V4+ Styles]\n"
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
            "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
            "Alignment,MarginL,MarginR,MarginV,Encoding\n"
            "Style: Label,Microsoft YaHei,30,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
            "-1,0,0,0,100,100,0,0,1,2,0,8,20,20,24,1\n"
            "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
            f"Dialogue: 0,0:00:00.00,{end},Label,,0,0,0,,AI 数字人演绎\n",
            encoding="utf-8",
        )
        caption_filter = "subtitles=subtitles.srt:force_style='FontName=Microsoft YaHei,FontSize=9,Bold=1,Outline=1,MarginV=18',subtitles=ai-label.ass"
        if presentation:
            packaging.write_overlay(label, raw_duration, presentation)
            caption_filter = packaging.subtitle_filter(presentation)
        final = work / "final.mp4"
        reframe = packaging_components.reframe_filter(pack) if pack else ""
        _run([executable, "-nostdin", "-v", "error", "-i", str(raw),
              "-vf", reframe + caption_filter,
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
            "presentation": presentation,
            "tail_trim": "conservative_near_silence_detection" if trim_tail else "disabled",
            "generation_requests": 0,
            "component_timing": pack["timing"] if pack else "not_used",
            "rendered_components": [item["use"] for item in pack["components"]] if pack else [],
            "unique_source_count": unique_sources, "reused_source_video": unique_sources < len(inputs),
            "subtitle_timing": "estimated_from_segment_container_duration",
            "subtitle_review": "required", "speech_accuracy": "not_evaluated",
            "lip_sync": "not_evaluated", "identity_consistency": "not_evaluated",
            "human_review": "not_reviewed", "publication_approval": "not_granted",
            "ai_label": "burned_in_video", "ai_label_text": "AI 数字人演绎",
            "description_label": "not_checked",
            "native_audio": ("tail_trimmed_from_unchanged_source_reencoded_to_aac_48khz" if
                             any(item["duration_sec"] < item["source_duration_sec"] for item in inputs)
                             else "preserved_content_reencoded_to_aac_48khz"),
            "video_geometry": "720x1280_aspect_preserving_pad_30fps",
            "segments": [{"job_dir": item["job_dir"], "sha256": item["sha256"],
                          "duration_sec": item["duration_sec"], "source_duration_sec": item["source_duration_sec"],
                          "text": item["text"]}
                         for item in inputs],
            "notice": "Subtitle cues are estimated from each segment duration, not word alignment; "
                      "review speech, timing, visual captions, lip sync, and add AI labeling to the description before release. "
                      + ("Source video is reused; segment count does not prove independent generations."
                         if unique_sources < len(inputs) else ""),
        }
        if automatic:
            if template is not None:
                report["template"] = template
            report.update(auto_request=auto_request, alignment=automatic["alignment"], warnings=automatic["warnings"],
                          subtitle_timing=("vosk_matched_sentence_bounds" if automatic["alignment"]["status"] == "matched"
                                           else "estimated_from_segment_container_duration"))
            report["notice"] = ("Local ASR timestamps are estimates and require playback review. "
                                "Unmatched speech falls back to estimated captions. No generation was requested.")
            for name, value in (("pack.json", pack), ("alignment.json", automatic["alignment"])):
                (work / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Publish QA in an explicitly incomplete state first. Only mark it
        # assembled after the final file is fully copied into its new folder.
        staged_report = {**report, "status": "assembling"}
        (work / "qa.json").write_text(json.dumps(staged_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (work / "qa-final.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        qa_identity = _copy_exclusive(work / "qa.json", output / "qa.json")
        for name in ("original.mp4", "subtitles.srt"):
            _copy_exclusive(work / name, output / name)
        if automatic:
            for name in ("pack.json", "alignment.json"):
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
