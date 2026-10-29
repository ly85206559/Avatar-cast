"""Offline orchestration exercise using synthetic media, not a digital human.

All scores and prices in this module are simulated. No provider or network is
called. The generated WAV files contain tones rather than spoken TTS.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

from .cache import segment_cache_key
from .pipeline import MAX_RETRIES, plan
from .qa import verdict
from .render import TAIL_SEC, burn_subtitles, concat_clips, normalize_clip, probe_duration_sec, write_srt


class DryRunError(RuntimeError):
    """A simulated segment exhausted its retries; see qa.json for details."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _ffmpeg(*args: str) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not installed; install ffmpeg to run the dry-run")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def _cache_hit(video: Path, metadata: Path) -> bool:
    try:
        record = json.loads(metadata.read_text(encoding="utf-8"))
        return (video.is_file() and _sha256(video) == record["sha256"]
                and record["scores_kind"] == "simulated"
                and verdict(record["scores"]) == "pass")
    except (OSError, ValueError, KeyError, TypeError):
        return False


def run_dry_run(script: list[dict], brief: dict, output_dir: str | Path,
                cache_dir: str | Path, *,
                failure_attempts: dict[str, int] | None = None) -> dict:
    """Create a 30–60s synthetic multi-segment video and a simulated QA report.

    ``failure_attempts`` injects a simulated failed QA result on the first N
    attempts for the named segment; it never affects a valid cached segment.
    Durations are apportioned by text length, including one tail per segment.
    """
    out = Path(output_dir).resolve()
    cache = Path(cache_dir).resolve()
    if out == cache or out in cache.parents or cache in out.parents:
        raise ValueError("output and cache directories must be separate")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise FileExistsError("output directory must be empty; choose a new directory")
    out.mkdir(parents=True, exist_ok=True)
    try:
        return _run_dry_run(script, brief, out, cache, failure_attempts)
    except Exception as exc:
        for name in ("final.mp4", "subtitles.srt"):
            (out / name).unlink(missing_ok=True)
        report_path = out / "qa.json"
        if not report_path.exists():
            report_path.write_text(json.dumps({
                "mode": "dry_run", "status": "fail", "quality_verdict": "unverified",
                "error": str(exc), "segments": [],
                "cost": {"currency": "SIMULATED", "estimated": 0, "simulated": 0,
                         "actual": 0, "cache_savings": 0},
                "cache": {"hits": 0, "misses": 0},
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        raise


def _run_dry_run(script: list[dict], brief: dict, output_dir: Path, cache_dir: Path,
                 failure_attempts: dict[str, int] | None) -> dict:
    target = float(brief["duration_target_sec"])
    if not math.isfinite(target) or not 30 <= target <= 60:
        raise ValueError("duration_target_sec must be between 30 and 60")
    if len(script) < 2:
        raise ValueError("dry-run requires at least two segments")
    ids = [s["id"] for s in script]
    if len(set(ids)) != len(ids):
        raise ValueError("segment ids must be unique")
    if any(not isinstance(s["text"], str) or not s["text"].strip() for s in script):
        raise ValueError("each segment must have non-empty text")
    if any(s["shot"] not in ("talking_head", "b_roll", "demo", "scene") for s in script):
        raise ValueError("invalid shot")
    weights = [len(s["text"].strip()) for s in script]
    # Concatenating independently encoded clips adds a small encoder delay.
    # Keep a margin at the 30/60 second boundaries, and verify the export.
    margin = len(script) * 0.1
    render_target = min(60 - margin, max(30 + margin, target))
    if render_target < 30 or render_target > 60:
        raise ValueError("too many segments for a 30–60 second export")
    speech_total = render_target - len(script) * TAIL_SEC
    if speech_total <= 0:
        raise ValueError("too many segments for the requested duration")
    durations = [speech_total * weight / sum(weights) for weight in weights]
    if min(durations) < 1 / 30:
        raise ValueError("segment duration must be at least one video frame")

    out = Path(output_dir)
    cache = Path(cache_dir)
    out.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    work = out / "segments"
    work.mkdir(exist_ok=True)
    failures = failure_attempts or {}
    audio_paths, audio_hashes, keys, hits = [], [], [], []
    for index, (seg, duration) in enumerate(zip(script, durations)):
        audio = work / f"{index:04d}.wav"
        # Stable tone selected by the full segment; it is deliberately not speech.
        seed = json.dumps(seg, sort_keys=True, ensure_ascii=False).encode("utf-8")
        frequency = 220 + int(hashlib.sha256(seed).hexdigest()[:4], 16) % 400
        _ffmpeg("-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=48000",
                "-t", f"{duration:.6f}", "-c:a", "pcm_s16le", str(audio))
        audio_hash = _sha256(audio)
        key = segment_cache_key(seg, brief.get("persona_id", "dry-run"), "synthetic",
                                "2", {"segment": seg, "duration": round(duration, 6),
                                      "preview_index": index, "preview_count": len(script)},
                                audio_hash, reference_sha256="synthetic-no-reference")
        audio_paths.append(audio)
        audio_hashes.append(audio_hash)
        keys.append(key)
        hits.append(_cache_hit(cache / f"{key}.mp4", cache / f"{key}.json"))

    # The rate is invented solely to exercise cost accounting; it is not a quote.
    rate = 0.1
    quotes = [{"duration_sec": duration + TAIL_SEC,
               "estimated_cost": (duration + TAIL_SEC) * rate, "cache_hit": hit}
              for duration, hit in zip(durations, hits)]
    task_plan = plan(script, quotes, cache_keys=keys)
    report = {
        "mode": "dry_run", "status": "running", "quality_verdict": "unverified",
        "notice": "Synthetic tones and labeled test cards with burned-in captions; scores, retry strategies and prices are simulated, not real TTS or lip sync.",
        "segments": [],
        "cost": {"currency": "SIMULATED", "rate_per_sec": rate,
                 "estimated": task_plan.total_cost, "simulated": 0.0,
                 "actual": 0.0, "cache_savings": 0.0},
        "cache": {"hits": 0, "misses": 0},
    }
    report_path = out / "qa.json"
    clips, subtitles = [], []
    offset = 0.0
    try:
        for i, (seg, duration, audio, audio_hash, key, hit, task) in enumerate(
                zip(script, durations, audio_paths, audio_hashes, keys, hits, task_plan.segments)):
            cached_video = cache / f"{key}.mp4"
            cached_meta = cache / f"{key}.json"
            clip = work / f"{i:04d}.mp4"
            entry = {"segment_id": seg["id"], "audio_sha256": audio_hash,
                     "cache_key": key, "cache_hit": hit, "attempts": 0,
                     "retries": 0, "retry_reasons": [], "verdict": "pending",
                     "scores_kind": "simulated"}
            report["segments"].append(entry)
            report["cache"]["hits" if hit else "misses"] += 1
            if _sha256(audio) != audio_hash:
                raise DryRunError(f"locked audio changed for {seg['id']}")
            if hit:
                shutil.copyfile(cached_video, clip)
                entry["scores"] = json.loads(cached_meta.read_text(encoding="utf-8"))["scores"]
                entry["verdict"] = "pass"
                report["cost"]["cache_savings"] += (duration + TAIL_SEC) * rate
            else:
                for attempt in range(MAX_RETRIES + 1):
                    entry["attempts"] += 1
                    report["cost"]["simulated"] += (duration + TAIL_SEC) * rate
                    source = work / f"{i:04d}.source.mp4"
                    color = ("0x203050", "0x20403b", "0x3b304e")[i % 3]
                    card = (
                        "drawtext=text='AvatarCast':fontcolor=white:fontsize=36:x=36:y=28,"
                        "drawtext=text='DRY RUN / SYNTHETIC MEDIA':fontcolor=0xffcc80:fontsize=18:x=36:y=80,"
                        f"drawtext=text='SEGMENT {i + 1} / {len(script)}':fontcolor=white:fontsize=30:x=36:y=142,"
                        "drawtext=text='Test tone - no speech or lip sync':fontcolor=white:fontsize=18:x=36:y=194"
                    )
                    _ffmpeg("-f", "lavfi", "-i", f"color=c={color}:s=640x360:r=30",
                            "-vf", card,
                            "-t", f"{duration + TAIL_SEC:.6f}", "-an", "-c:v", "libx264",
                            "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(source))
                    if _sha256(audio) != audio_hash:
                        raise DryRunError(f"locked audio changed for {seg['id']}")
                    normalize_clip(str(source), str(clip), duration + TAIL_SEC,
                                   locked_audio_path=str(audio))
                    source.unlink(missing_ok=True)
                    scores = {"wer_accuracy": 1.0, "lipsync_score": 1.0,
                              "face_cosine": 1.0, "voice_drift": 0.0,
                              "burned_subtitle": attempt < failures.get(seg["id"], 0)}
                    entry["scores"] = scores
                    entry["verdict"] = verdict(scores)
                    if entry["verdict"] == "pass":
                        shutil.copyfile(clip, cached_video)
                        cached_meta.write_text(json.dumps({"sha256": _sha256(cached_video),
                                                         "scores_kind": "simulated", "scores": scores}),
                                               encoding="utf-8")
                        break
                    entry["retry_reasons"].append("simulated QA failure")
                    if attempt == MAX_RETRIES:
                        raise DryRunError(f"segment {seg['id']} failed after {entry['attempts']} attempts")
                    entry["retries"] += 1
                    task.retries = attempt
                    entry.setdefault("retry_steps", []).append(task.next_retry_step())
            clip_duration = probe_duration_sec(str(clip))
            clips.append(str(clip))
            subtitles.append({"text": seg["text"], "start": offset,
                              "end": min(offset + duration, offset + clip_duration)})
            offset += clip_duration
        assembled = work / "assembled.mp4"
        concat_clips(clips, str(assembled))
        write_srt(subtitles, str(out / "subtitles.srt"))
        burn_subtitles(str(assembled), str(out / "subtitles.srt"), str(out / "final.mp4"))
        assembled.unlink()
        final_duration = probe_duration_sec(str(out / "final.mp4"))
        if not 30 <= final_duration <= 60:
            raise DryRunError(f"export duration {final_duration:.3f}s is outside 30–60 seconds")
        report["status"] = "pass"
        report["output"] = {"video": "final.mp4", "subtitles": "subtitles.srt",
                            "captions": "burned_in_and_srt",
                            "duration_sec": final_duration}
    except Exception as exc:
        report["status"] = "fail"
        report["error"] = str(exc)
        for entry in report["segments"]:
            if entry["verdict"] == "pending":
                entry["verdict"] = "unverified"
                entry["error"] = str(exc)
        for name in ("final.mp4", "subtitles.srt"):
            (out / name).unlink(missing_ok=True)
        raise
    finally:
        report["cost"]["simulated"] = round(report["cost"]["simulated"], 2)
        report["cost"]["cache_savings"] = round(report["cost"]["cache_savings"], 2)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
