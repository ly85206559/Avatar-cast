"""Render three local packaging comparisons from the existing 10-second pilot.

The examples illustrate packaging, not new sales/emotional dialogue. No provider
client or generation operation is used. Run from an installed AvatarCast checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from dhp import native_assembly, presentation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-dir", required=True, help="completed original 10-second pilot job")
    parser.add_argument("--output-dir", required=True, help="new comparison directory")
    args = parser.parse_args()
    job = json.loads((Path(args.job_dir) / "job.json").read_text(encoding="utf-8"))
    expected_text = "你好，这是 AvatarCast 的数字人口播测试。我们先验证画面、声音和字幕是否同步。"
    if job.get("spec", {}).get("text") != expected_text:
        raise ValueError("These comparison examples require the documented pilot dialogue. "
                         "For other dialogue, prepare a matching pack and use make restyle.")
    root = Path(args.output_dir).resolve()
    if root.exists():
        raise ValueError("Choose a new comparison directory.")
    root.mkdir(parents=True)
    ffmpeg = native_assembly._find_ffmpeg(None)
    before = native_assembly.assemble([args.job_dir], str(root / "baseline"), ffmpeg)

    def audio_hash(path):
        audio = subprocess.run([ffmpeg, "-v", "error", "-i", str(path), "-map", "0:a:0",
                                "-c:a", "copy", "-f", "adts", "-"], capture_output=True, check=True)
        return hashlib.sha256(audio.stdout).hexdigest()

    original_audio = audio_hash(root / "baseline" / "original.mp4")
    cases = []
    for style, label in (("promo", "推广介绍"), ("explainer", "知识讲解"), ("warm", "温暖陪伴")):
        pack_path = Path(__file__).resolve().parents[1] / "examples" / "packaging" / f"{style}.json"
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        output = root / style
        report = native_assembly.assemble([args.job_dir], str(output), ffmpeg,
                                         presentation.prepare(style, pack=pack))
        shutil.copyfile(pack_path, output / "pack.json")
        # Comparison uses the same normalized before picture and only one audio
        # track. Components never change the original dialogue or performance.
        header = output / "comparison.ass"
        header.write_text(
            "[Script Info]\nScriptType: v4.00+\nPlayResX: 1440\nPlayResY: 1360\n"
            "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,Bold,Alignment\n"
            "Style: Header,Microsoft YaHei,34,&H00FFFFFF,&H00000000,-1,5\n"
            "[Events]\nFormat: Layer,Start,End,Style,Text\n"
            "Dialogue: 0,0:00:00.00,0:01:00.00,Header,{\\pos(360,40)}原片\n"
            f"Dialogue: 0,0:00:00.00,0:01:00.00,Header,{{\\pos(1080,40)}}{label} · 本地包装\n",
            encoding="utf-8",
        )
        native_assembly._run([
            ffmpeg, "-nostdin", "-v", "error", "-i", str(root / "baseline" / "original.mp4"),
            "-i", str(output / "final.mp4"), "-filter_complex",
            "[0:v][1:v]hstack=inputs=2,pad=1440:1360:0:80:color=0x12161c,subtitles=comparison.ass[v]",
            "-map", "[v]", "-map", "0:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(output / "comparison.mp4")
        ], cwd=output)
        native_assembly._duration(output / "comparison.mp4", ffmpeg)
        if audio_hash(output / "final.mp4") != original_audio:
            raise ValueError("The packaged audio differs from the comparison baseline.")
        cases.append({"style": style, "label": label, "duration_sec": report["output_duration_sec"],
                      "components": report["rendered_components"], "component_timing": report["component_timing"],
                      "audio_matches_baseline": True})
    (root / "comparison-proof.json").write_text(json.dumps({
        "generation_requests": 0, "source_job": str(Path(args.job_dir).resolve()),
        "source_sha256": before["segments"][0]["sha256"], "cases": cases,
        "baseline_audio_sha256": original_audio,
        "component_coverage": sorted({name for case in cases for name in case["components"]}),
        "notice": "Packaging comparison on unchanged pilot dialogue. Component timing is estimated; "
                  "these are not newly generated sales or emotional performances."
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cards = "".join(
        f'<article><h2>{case["label"]}</h2><video controls preload="metadata" '
        f'src="{case["style"]}/comparison.mp4"></video><p>左：原片　右：本地包装 · 相同原声</p>'
        f'<a href="{case["style"]}/final.mp4">查看竖屏成片</a></article>' for case in cases)
    (root / "index.html").write_text(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><title>AvatarCast 包装前后对照</title>'
        '<style>body{margin:0;background:#11161d;color:#ecf2fa;font:16px system-ui;padding:32px}'
        'main{max-width:1120px;margin:auto}section{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}'
        'article{background:#1d2632;padding:18px;border-radius:16px}video{width:100%;border-radius:8px}'
        'p{line-height:1.7;color:#b5c2d3}h2{font-size:20px}a{color:#9cceff}'
        '@media(max-width:820px){section{grid-template-columns:1fr}}</style><main>'
        '<h1>同一原片，三种呈现方式</h1><p>推广介绍、知识讲解、温暖陪伴的包装对照。'
        '保留已有测试原声，本轮未提交生成任务。时间点为估算，情感版展示包装气质。</p><section>'
        + cards + '</section></main></html>', encoding="utf-8")
    print(json.dumps({"preview": str(root / "index.html"), "generation_requests": 0,
                      "cases": cases}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
