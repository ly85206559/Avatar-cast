import hashlib
import io
import json
from pathlib import Path
import subprocess

import pytest
from PIL import Image

from dhp import auto_pack, content_templates, make, native, native_assembly, showcase


BEATS = {"hook": "想试试口播？", "problem": "做视频要处理字幕。",
         "demo": "这个工具可以添加字幕。", "fit": "先用已有原片试试。"}


def test_product_demo_plan_binds_asset_and_rejects_changes_before_gateway(tmp_path, monkeypatch):
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted gateway"))
    presenter, asset = tmp_path / "presenter.png", tmp_path / "product.png"
    Image.new("RGB", (32, 48), "white").save(presenter)
    Image.new("RGB", (48, 32), "red").save(asset)
    brief = {"template": "product-demo", "request": "展示产品截图", "title": "产品介绍", "beats": BEATS,
             "asset": str(asset)}
    plan = make.create_brief_plan(str(presenter), brief, str(tmp_path / "project"))
    assert plan["beats"] == BEATS and plan["asset"]["type"] == "image"
    assert content_templates.select("用演示种草模板展示产品") == "product-demo"
    assert plan["asset"]["sha256"] == hashlib.sha256(asset.read_bytes()).hexdigest()
    Image.new("RGB", (48, 32), "blue").save(asset)
    with pytest.raises(ValueError, match="media changed"):
        make.run_project(plan["project"], confirm=True, plan_sha256=plan["plan_sha256"])
    assert not (Path(plan["project"]) / "approval.json").exists()


def test_product_demo_scene_uses_demo_beat_and_discloses_fallback(monkeypatch):
    cues = [{"text": text, "start": start, "end": end} for text, start, end in [
        (BEATS["hook"], .1, 1), (BEATS["problem"], 1.2, 2.8),
        (BEATS["demo"], 3.1, 6.2), (BEATS["fit"], 6.5, 9.2),
    ]]
    assert showcase.scene(10, cues, True, BEATS, True) == {"at": 3.1, "until": 6.2, "timing": "asr_matched"}
    assert showcase.scene(10, cues, True, None, True) == {"at": 2.5, "until": 7.5, "timing": "estimated"}
    class Missing:
        def __init__(self, _):
            raise RuntimeError("no model")
    monkeypatch.setattr(auto_pack, "VoskASRProvider", Missing)
    result = auto_pack.prepare("unused", "".join(BEATS.values()), 10, "promo", "标题",
                               template=content_templates.resolve("product-demo"), beats=BEATS)
    assert any("未提供展示素材" in warning for warning in result["warnings"])


def test_audio_only_file_cannot_be_a_showcase_video(tmp_path):
    if not all(make.doctor()["ffmpeg"].values()):
        pytest.skip("FFmpeg subtitles and libx264 required")
    ffmpeg = native_assembly._find_ffmpeg(None)
    asset = tmp_path / "audio-only.mp4"
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "sine=duration=1",
                    "-c:a", "aac", str(asset)], check=True, capture_output=True)
    with pytest.raises(ValueError, match="decode a frame"):
        showcase.prepare_asset(str(asset))


def test_completed_project_runs_and_replaces_media_without_changing_plan(tmp_path, monkeypatch):
    if not all(make.doctor()["ffmpeg"].values()):
        pytest.skip("FFmpeg subtitles and libx264 required")
    ffmpeg = native_assembly._find_ffmpeg(None)
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted gateway"))
    presenter, asset, replacement = (tmp_path / name for name in ("presenter.png", "asset.png", "replacement.png"))
    for path, color in ((presenter, "white"), (asset, "red"), (replacement, "blue")):
        Image.new("RGB", (32, 48), color).save(path)
    plan = make.create_brief_plan(str(presenter), {"template": "product-demo", "request": "展示产品",
                                                  "title": "产品", "beats": BEATS, "asset": str(asset)},
                                  str(tmp_path / "project"))
    root, job = Path(plan["project"]), Path(plan["project"]) / "segment-001"
    job.mkdir()
    source = job / "original.mp4"
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=green:s=90x160:r=30:d=4",
                    "-f", "lavfi", "-i", "sine=duration=4", "-c:v", "libx264", "-c:a", "aac", str(source)],
                   check=True, capture_output=True)
    record = {"version": 1, "status": "complete", "expected_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "spec": {"mode": "native", "text": plan["segments"][0], "image_sha256": plan["image_sha256"],
                       "agent_id": "offline-fixture", "duration_sec": 10}}
    make._write_new_json(job / "job.json", record)
    # A synthetic completed receipt; no live approval or submission is implied.
    make._write_new_json(root / "approval.json", {"plan_sha256": plan["plan_sha256"], "agent_id": "offline-fixture"})
    monkeypatch.setattr(native, "resume", lambda *_: record)
    class Missing:
        def __init__(self, _):
            raise RuntimeError("no model")
    monkeypatch.setattr(auto_pack, "VoskASRProvider", Missing)
    result = make.run_project(str(root))
    report = json.loads(Path(result["qa"]).read_text(encoding="utf-8"))
    assert report["showcase"]["asset"] == plan["asset"] and report["generation_requests"] == 0
    assert make.run_project(str(root))["status"] == "ready_for_review"
    plan_bytes = (root / "plan.json").read_bytes()
    edited = make.restyle_project(str(root), "auto", asset=str(replacement))
    report = json.loads(Path(edited["qa"]).read_text(encoding="utf-8"))
    assert report["showcase"]["asset"]["sha256"] == hashlib.sha256(replacement.read_bytes()).hexdigest()
    assert (root / "plan.json").read_bytes() == plan_bytes and edited["generation_requests"] == 0


@pytest.mark.parametrize("media_type", ["image", "video"])
def test_showcase_cuts_to_media_and_back_with_presenter_and_original_audio(tmp_path, monkeypatch, media_type):
    if not all(make.doctor()["ffmpeg"].values()):
        pytest.skip("FFmpeg subtitles and libx264 required")
    ffmpeg = native_assembly._find_ffmpeg(None)
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted gateway"))
    class Missing:
        def __init__(self, _):
            raise RuntimeError("no model")
    monkeypatch.setattr(auto_pack, "VoskASRProvider", Missing)
    job = tmp_path / "job"
    job.mkdir()
    source = job / "original.mp4"
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=green:s=180x320:r=30:d=4",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-c:v", "libx264", "-c:a", "aac",
                    str(source)], check=True, capture_output=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    (job / "job.json").write_text(json.dumps({"version": 1, "status": "complete", "expected_sha256": digest,
        "spec": {"mode": "native", "text": "这是已有口播。"}}, ensure_ascii=False), encoding="utf-8")
    if media_type == "image":
        asset = tmp_path / "product.png"
        Image.new("RGB", (640, 960), (255, 0, 0)).save(asset)
    else:
        asset = tmp_path / "product.mp4"
        subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=blue:s=160x240:r=30:d=1",
                        "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
                        "-vf", "drawbox=x=0:y=0:w=iw:h=ih:color=red:t=fill:enable='gte(t,0.5)'",
                        "-c:v", "libx264", "-c:a", "aac",
                        str(asset)], check=True, capture_output=True)
    output = tmp_path / "result"
    assert make.main(["restyle", "--job-dir", str(job), "--template", "product-demo", "--asset", str(asset),
                      "--output-dir", str(output)]) == 0
    report = json.loads((output / "qa.json").read_text(encoding="utf-8"))
    assert report["generation_requests"] == 0 and report["showcase"]["asset_audio"] == "muted"
    assert report["showcase"]["scene"]["timing"] == "estimated"
    assert any("估算" in w for w in report["warnings"])
    def frame(seconds):
        result = subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-ss", str(seconds), "-i",
                                 str(output / "final.mp4"), "-frames:v", "1", "-f", "image2pipe",
                                 "-vcodec", "png", "-"], check=True, capture_output=True)
        return Image.open(io.BytesIO(result.stdout)).convert("RGB")
    before, during, after = frame(.5), frame(2), frame(3.5)
    for pic in (before, after):
        r, g, b = pic.getpixel((100, 300))
        assert g > r + 50 and g > b + 50
    r, g, b = during.getpixel((100, 300))
    assert (r > g + 100 and r > b + 100) if media_type == "image" else (b > r + 100 and b > g + 100)
    r, g, b = during.getpixel((580, 900))
    assert g > r + 50 and g > b + 50
    if media_type == "video":
        early, late = frame(1.2).getpixel((100, 300)), frame(1.7).getpixel((100, 300))
        assert early[2] > early[0] + 100 and late[0] > late[2] + 100
    def audio_hash(path):
        return subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a:0",
                               "-c", "copy", "-f", "hash", "-hash", "SHA256", "-"],
                              check=True, capture_output=True).stdout
    assert audio_hash(output / "original.mp4") == audio_hash(output / "final.mp4")
