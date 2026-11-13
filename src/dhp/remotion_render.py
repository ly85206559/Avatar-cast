"""Stage private local media and render the optional product-demo composition."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def timeline(duration: float, alignment: dict, cues: list[dict], scene: dict | None,
             assets: list[dict], title: str) -> dict:
    """Keep recognizer timestamps intact and highlight verified text matches only."""
    matched = alignment.get("status") == "matched"
    captions = [{"text": cue["text"], "startMs": round(cue["start"] * 1000),
                 "endMs": round(cue["end"] * 1000), "timestampMs": None, "confidence": None}
                for cue in cues]
    words = alignment.get("words", [])
    reliable_words = alignment.get("matched_words", words if matched else [])
    emphasis = []
    for cue in cues:
        candidates = [word for word in reliable_words if cue["start"] <= word["start"] < cue["end"]
                      and 2 <= len(word["word"].strip()) <= 8]
        if candidates:
            emphasis.append(max(candidates, key=lambda word: len(word["word"].strip())))
    scenes = []
    if scene and assets:
        step = (scene["until"] - scene["at"]) / len(assets)
        if step < 0.5:
            raise ValueError("Too many assets for the showcase interval; use fewer assets or a longer clip.")
        for index, asset in enumerate(assets):
            scenes.append({**asset, "at": scene["at"] + index * step,
                           "until": scene["at"] + (index + 1) * step})
    return {"duration": duration, "title": title, "captions": captions, "words": words, "emphasis": emphasis,
            "scenes": scenes, "timing": "asr_matched" if matched else "estimated",
            "scene_timing": scene.get("timing") if scene else "not_used"}


def check_setup() -> tuple[str, Path]:
    template = Path(__file__).parent / "remotion_template"
    node = shutil.which("node")
    if not node or not (template / "node_modules" / "@remotion" / "renderer").is_dir():
        raise RuntimeError(f"Install Node.js and run npm ci --prefix \"{template}\"; see docs/REMOTION.md.")
    return node, template


def render(raw: Path, asset: dict | list[dict] | None, scene: dict | None, alignment: dict,
           cues: list[dict], title: str, duration: float, output: Path, ffmpeg: str,
           work: Path) -> dict:
    from .native_assembly import _duration
    from .showcase import verify_asset

    node, template = check_setup()
    public = work / "remotion-media"
    public.mkdir()
    shutil.copyfile(raw, public / "host.mp4")
    items = asset if isinstance(asset, list) else ([asset] if asset else [])
    staged = []
    for index, item in enumerate(items):
        source = Path(item["path"])
        name = f"asset-{index}{source.suffix.lower()}"
        shutil.copyfile(source, public / name)
        verify_asset({**item, "path": str(public / name)})
        staged.append({"src": name, "type": item["type"],
                       "sourceFrames": max(1, round(_duration(public / name, ffmpeg) * 30))
                       if item["type"] == "video" else 1})
    edit = timeline(duration, alignment, cues, scene, staged, title)
    config = work / "remotion.json"
    config.write_text(json.dumps(edit, ensure_ascii=False, indent=2), encoding="utf-8")
    silent = work / "remotion-silent.mp4"
    result = subprocess.run([node, str(template / "render.mjs"), str(config), str(public), str(silent)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError("Remotion render failed: " + (result.stderr + result.stdout)[-2500:])
    # Mux the complete normalized narration unchanged. Asset audio is never used.
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-i", str(silent), "-i", str(raw),
                    "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-movflags", "+faststart", str(output)],
                   check=True, capture_output=True)
    return edit
