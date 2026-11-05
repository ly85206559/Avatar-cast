"""Build template and component previews locally from completed, owned pilot jobs.

No gateway client is used. Public GIFs are silent packaging demonstrations;
full MP4s, speech and private job metadata stay in the selected output directory.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from dhp import make, native_assembly, presentation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-dir", required=True, help="completed original AvatarCast pilot")
    parser.add_argument("--template-job-dir", required=True, help="completed clip reused for template packaging")
    parser.add_argument("--output-dir", required=True, help="new private MP4 / proof directory")
    parser.add_argument("--public-dir", required=True, help="new directory for authorized preview images and GIFs")
    parser.add_argument("--asr-model")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    output = Path(args.output_dir).resolve()
    public = Path(args.public_dir).resolve()
    if output.exists() or public.exists():
        raise ValueError("Choose new output and preview directories; nothing will be overwritten.")
    job = json.loads((Path(args.job_dir) / "job.json").read_text(encoding="utf-8"))
    if job.get("spec", {}).get("text") != "你好，这是 AvatarCast 的数字人口播测试。我们先验证画面、声音和字幕是否同步。":
        raise ValueError("The component examples quote the documented pilot dialogue; use that completed job.")
    output.mkdir(parents=True)
    public.mkdir(parents=True)
    ffmpeg = native_assembly._find_ffmpeg(None)
    records = []

    def run(*command):
        subprocess.run([ffmpeg, "-nostdin", "-v", "error", *map(str, command)], check=True, capture_output=True)

    def previews(video, name, seconds, poster_time):
        run("-ss", poster_time, "-i", video, "-frames:v", "1", "-q:v", "3", public / (name + ".jpg"))
        run("-ss", "0.8" if seconds == 4 else "0", "-t", seconds, "-i", video, "-an", "-filter_complex",
            "fps=6,scale=216:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer",
            "-loop", "0", public / (name + ".gif"))

    for template_id in ("product-intro", "knowledge-share", "empathy"):
        directory = output / template_id
        if make.main(["restyle", "--job-dir", args.template_job_dir, "--template", template_id,
                      "--title", "同一原片的包装预览", "--output-dir", str(directory),
                      *(["--asr-model", args.asr_model] if args.asr_model else [])]) != 0:
            raise RuntimeError("Template preview failed: " + template_id)
        report = json.loads((directory / "qa.json").read_text(encoding="utf-8"))
        previews(directory / "final.mp4", template_id, min(10, report["output_duration_sec"]), 7)
        records.append({"kind": "template_packaging_only", "id": template_id, "template": report["template"],
                        "source_sha256": report["segments"][0]["sha256"],
                        "alignment": report["alignment"]["status"], "components": report["rendered_components"],
                        "generation_requests": report["generation_requests"]})

    for path in sorted((repo / "examples/components").glob("*.json")):
        name = path.stem
        pack = json.loads(path.read_text(encoding="utf-8"))
        report = native_assembly.assemble([args.job_dir], str(output / name), ffmpeg,
                                         presentation.prepare("explainer", pack=pack))
        video = output / name / "final.mp4"
        previews(video, name, 4, 3.4)
        # Decode the full exported video, not just the poster frame.
        run("-i", video, "-f", "null", "-")
        records.append({"kind": "component", "id": name, "timing": "estimated",
                        "source_sha256": report["segments"][0]["sha256"],
                        "components": report["rendered_components"], "generation_requests": 0})

    for entry in records:
        video = output / entry["id"] / "final.mp4"
        run("-i", video, "-f", "null", "-")
        entry["video_sha256"] = hashlib.sha256(video.read_bytes()).hexdigest()
    proof = {"generation_requests": 0, "paid_service_calls": 0, "records": records,
             "notice": "Existing test dialogue, not new product/emotional narration. GIFs have no audio. "
                       "No human lip-sync acceptance is inferred. MP4s remain private."}
    (output / "proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    cards = "".join(f'<article><h2>{r["id"]}</h2><video controls preload="metadata" width="240" '
                    f'src="{r["id"]}/final.mp4"></video></article>' for r in records)
    (output / "index.html").write_text('<!doctype html><meta charset="utf-8"><title>本地包装预览</title>'
        '<style>body{background:#151b23;color:#fff;font:16px system-ui;padding:24px}'
        'main{display:flex;flex-wrap:wrap;gap:24px}</style><h1>已有原片 · 本地包装验证</h1>'
        '<p>全部复用测试台词。组件时间为估算；没有发起新生成。</p><main>' + cards + '</main>', encoding="utf-8")
    print(json.dumps({"proof": str(output / "proof.json"), "preview": str(output / "index.html")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
