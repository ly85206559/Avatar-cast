"""Offline demo: a runnable loop that spends nothing and proves nothing
about lip-sync.

This is deliberately NOT a digital-human demo. The video clips are
synthetic colour blocks with a sine tone, generated locally by ffmpeg.
They exercise the real contract validation, quote gate, component
filter, render assembly (30 fps / 48 kHz / -16 LUFS, +0.25s tail rule
via segment timing), and SRT writing — and nothing else.

Every qa.json segment is ``warn`` with lip-sync, face consistency, and
ASR marked ``not_evaluated``. A demo that reported ``pass`` here would
be lying: placeholder video has no talking head to score. To get a real
score, run the API lip-sync path (scripts/api_lipsync_run.py, gated,
costs money) or a local lip-sync model, then score that output with
qa_scorers.py on the same script.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .cache import segment_cache_key
from .components import filter_renderable
from .pipeline import plan, quote_summary
from .render import concat_clips, normalize_clip, probe_duration_sec, write_srt

DEMO_SEGMENT_SEC = 2.0
_COLORS = ["blue", "green", "purple", "orange", "teal"]
_FREQS = [440, 520, 660, 550, 490]
VALID_SHOTS = ("talking_head", "b_roll", "demo", "scene")


def _synthetic_clip(out_path: Path, index: int, duration: float) -> str:
    color = _COLORS[index % len(_COLORS)]
    freq = _FREQS[index % len(_FREQS)]
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"color=c={color}:s=640x360:d={duration}",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:d={duration}",
        "-shortest", str(out_path),
    ], check=True)
    return str(out_path)


def run_demo(out_dir: str | Path, script_path: str | Path,
             brief_path: str | Path) -> dict:
    """Run the offline demo into out_dir. Returns the demo report dict."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    script = json.loads(Path(script_path).read_text(encoding="utf-8"))
    brief = json.loads(Path(brief_path).read_text(encoding="utf-8"))
    if not isinstance(script, list) or not script:
        raise ValueError("demo script must be a non-empty list of segments")
    for seg in script:
        if seg.get("shot") not in VALID_SHOTS:
            raise ValueError(f"invalid shot: {seg}")
        if not seg.get("text"):
            raise ValueError(f"segment without text: {seg}")

    persona_id = brief.get("persona_id", "demo-persona")
    keys = [
        segment_cache_key(seg, persona_id, "demo", "demo", {}, "demo")
        for seg in script
    ]
    quotes = [
        {"estimated_cost": 0.0, "cache_hit": False,
         "duration_sec": DEMO_SEGMENT_SEC}
        for _ in script
    ]
    p = plan(script, quotes, budget=None, cache_keys=keys)
    _ok, dropped = filter_renderable([])

    clips: list[str] = []
    srt_segments: list[dict] = []
    qa_records: list[dict] = []
    cursor = 0.0
    for i, seg in enumerate(script):
        raw = out / f"seg-{seg['id']}-raw.mp4"
        _synthetic_clip(raw, i, DEMO_SEGMENT_SEC)
        norm = out / f"seg-{seg['id']}.mp4"
        normalize_clip(str(raw), str(norm), DEMO_SEGMENT_SEC)
        clips.append(str(norm))
        srt_segments.append({
            "text": seg["text"],
            "start": cursor,
            "end": cursor + DEMO_SEGMENT_SEC,
        })
        qa_records.append({
            "segment_id": seg["id"],
            "verdict": "warn",
            "cost": 0.0,
            "cache_hit": False,
            "duration_sec": DEMO_SEGMENT_SEC,
            "retries": 0,
            "retry_reasons": [],
            "note": ("offline demo: lipsync, face consistency and ASR "
                     "not evaluated on synthetic placeholder video"),
        })
        cursor += DEMO_SEGMENT_SEC

    final = out / "demo-final.mp4"
    concat_clips(clips, str(final))
    srt_path = out / "demo.srt"
    write_srt(srt_segments, str(srt_path))
    qa_path = out / "qa.json"
    qa_path.write_text(json.dumps(qa_records, ensure_ascii=False, indent=2),
                       encoding="utf-8")

    report = {
        "demo": True,
        "mode": "offline_synthetic_placeholder",
        "spent": 0.0,
        "segments": len(script),
        "duration_sec": round(probe_duration_sec(str(final)), 3),
        "quote_gate": quote_summary(p),
        "components_renderable": 0,
        "components_dropped": dropped,
        "lipsync": "not_evaluated",
        "face_consistency": "not_evaluated",
        "asr": "not_evaluated",
        "outputs": {
            "video": str(final),
            "srt": str(srt_path),
            "qa": str(qa_path),
        },
        "warning": ("Synthetic colour clips are not a talking head. "
                    "Do not present this demo as lip-sync evidence."),
    }
    (out / "demo-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="dhp demo")
    p.add_argument("--script", default="examples/demo-script.json")
    p.add_argument("--brief", default="examples/demo-brief.json")
    p.add_argument("--out", default="outputs/demo")
    args = p.parse_args(argv)
    report = run_demo(args.out, args.script, args.brief)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
