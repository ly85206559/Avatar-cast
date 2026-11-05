"""Reproduce the three-point preview from the completed relaxation pilot, locally."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from dhp import content_templates, make, native_assembly


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-dir", required=True, help="completed relaxation pilot")
    parser.add_argument("--image", required=True, help="the pilot's original presenter image")
    parser.add_argument("--output-dir", required=True, help="new private project and MP4 directory")
    parser.add_argument("--preview-dir", required=True, help="new silent GIF and poster directory")
    parser.add_argument("--asr-model")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = Path(args.job_dir).resolve()
    output, preview = Path(args.output_dir).resolve(), Path(args.preview_dir).resolve()
    if output.exists() or preview.exists():
        raise ValueError("Choose new output and preview directories.")
    brief = json.loads((root / "templates/three-point/example.json").read_text(encoding="utf-8"))
    job = json.loads((source / "job.json").read_text(encoding="utf-8"))
    image_hash = hashlib.sha256(Path(args.image).read_bytes()).hexdigest()
    expected = content_templates.narration(brief, content_templates.resolve("three-point"))
    if job.get("spec", {}).get("text") != expected or job["spec"].get("image_sha256") != image_hash:
        raise ValueError("Use the documented relaxation pilot and its original presenter image.")
    project = output / "project"
    make.create_brief_plan(args.image, brief, str(project))
    segment = project / "segment-001"
    segment.mkdir()
    for name in ("job.json", "original.mp4"):
        shutil.copyfile(source / name, segment / name)
    result = make.restyle_project(str(project), "auto", output_dir=str(output / "cut"), asr_model=args.asr_model)
    qa = json.loads(Path(result["qa"]).read_text(encoding="utf-8"))
    preview.mkdir(parents=True)
    ffmpeg = native_assembly._find_ffmpeg(None)
    video = Path(result["video"])
    def run(*args):
        subprocess.run([ffmpeg, "-nostdin", "-v", "error", *map(str, args)], check=True, capture_output=True)
    run("-ss", "4", "-i", video, "-frames:v", "1", "-q:v", "3", preview / "three-point.jpg")
    run("-i", video, "-an", "-filter_complex",
        "fps=6,scale=216:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer",
        "-loop", "0", preview / "three-point.gif")
    proof = {"source_sha256": qa["segments"][0]["sha256"], "video_sha256": qa["video_sha256"],
             "template": qa["template"], "alignment": qa["alignment"]["status"],
             "component_timing": qa["component_timing"], "components": qa["rendered_components"],
             "generation_requests": 0, "warnings": qa["warnings"],
             "notice": "Existing relaxation narration; GIF is silent. MP4 remains local and needs playback review."}
    (output / "proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"video": str(video), "preview": str(preview / "three-point.gif"),
                      "proof": str(output / "proof.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
