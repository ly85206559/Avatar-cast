import hashlib
import json
from pathlib import Path
import subprocess

import pytest
from PIL import Image

from dhp import auto_pack, content_templates, make, native, native_assembly, packaging_components


BEATS = {
    "hook": "下班后，",
    "point_1": "先把工作消息放一放，",
    "point_2": "再散步十分钟，",
    "point_3": "最后听首喜欢的歌，",
    "closing": "给自己一点放松的时间。",
}


def test_three_point_plan_keeps_roles_and_rejects_changed_script(tmp_path, monkeypatch):
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted gateway"))
    image = tmp_path / "image.png"
    Image.new("RGB", (32, 48), "white").save(image)
    plan = make.create_brief_plan(str(image), {"template": "three-point", "request": "三个放松方法",
                                                "title": "下班放松", "beats": BEATS}, str(tmp_path / "project"))
    assert content_templates.select("分享三个下班放松的方法") == "three-point"
    assert content_templates.select("推荐三个产品") == "product-intro"
    assert plan["beats"] == BEATS
    assert "".join(plan["segments"]) == "".join(BEATS.values())
    data = json.loads((Path(plan["project"]) / "plan.json").read_text(encoding="utf-8"))
    data["beats"]["point_2"] = "另一个方法，"
    (Path(plan["project"]) / "plan.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="do not match"):
        make._load_plan(Path(plan["project"]))
    bad = {**BEATS, "point_1": "很长的内容" * 6}
    with pytest.raises(ValueError, match="18 characters"):
        content_templates.narration({"beats": bad}, content_templates.resolve("three-point"))


def test_three_point_uses_role_boundaries_and_labels_estimates():
    selection = content_templates.resolve("three-point")
    cues = [{"text": text, "start": start, "end": end} for text, start, end in [
        (BEATS["hook"], .1, .8), (BEATS["point_1"], 1.1, 2.8),
        (BEATS["point_2"], 3.2, 4.8), (BEATS["point_3"], 5.2, 7.0),
        (BEATS["closing"], 7.5, 9.4),
    ]]
    pack = content_templates.recipe(selection, "下班放松", cues, 10, True, beats=BEATS)
    packaging_components.validate(pack, 10)
    points = [c for c in pack["components"] if c["use"] == "KeywordEmphasis"][:3]
    assert [c["at"] for c in points] == [1.1, 3.2, 5.2]
    assert [c["text"] for c in points] == ["01  先把工作消息放一放", "02  再散步十分钟", "03  最后听首喜欢的歌"]
    assert pack["timing"] == "asr_matched"
    estimated = content_templates.recipe(selection, "下班放松", [], 10, False, beats=BEATS)
    packaging_components.validate(estimated, 10)
    assert estimated["timing"] == "estimated"
    assert len([c for c in estimated["components"] if c["use"] == "KeywordEmphasis"]) == 4
    multiple = content_templates.recipe(selection, "下班放松", [], 20, False, beats=BEATS,
                                        allow_estimate=False)
    assert [c["use"] for c in multiple["components"]] == ["TextCard"]
    mismatched = content_templates.recipe(selection, "下班放松", cues[:-1], 10, True, beats=BEATS)
    assert [c["use"] for c in mismatched["components"]] == ["TextCard"]
    missing = content_templates.recipe(selection, "下班放松", cues, 10, True)
    assert [c["use"] for c in missing["components"]] == ["TextCard"]


def test_another_topic_gets_its_own_three_points(tmp_path, monkeypatch):
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted gateway"))
    image = tmp_path / "image.png"
    Image.new("RGB", (32, 48), "white").save(image)
    example = Path(__file__).resolve().parents[1] / "templates/three-point/example-desk.json"
    brief = json.loads(example.read_text(encoding="utf-8"))
    brief["template"] = "auto"
    plan = make.create_brief_plan(str(image), brief, str(tmp_path / "project"))
    assert plan["template"]["id"] == "three-point"
    pack = content_templates.recipe(plan["template"], plan["presentation"]["title"], [], 10, False,
                                    beats=plan["beats"])
    points = [c["text"] for c in pack["components"] if c["use"] == "KeywordEmphasis"]
    assert points[:3] == ["01  先收起不常用的东西", "02  再把常用物品放近些", "03  最后留出一块空位"]
    assert not any("下班" in p for p in points)


def test_three_point_completed_job_renders_and_restyles_without_gateway(tmp_path, monkeypatch):
    if not all(make.doctor()["ffmpeg"].values()):
        pytest.skip("FFmpeg subtitles and libx264 required")
    ffmpeg = native_assembly._find_ffmpeg(None)
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted gateway"))
    image = tmp_path / "image.png"
    Image.new("RGB", (32, 48), "white").save(image)
    plan = make.create_brief_plan(str(image), {"template": "three-point", "request": "三个放松方法",
                                                "title": "下班放松", "beats": BEATS}, str(tmp_path / "project"))
    root = Path(plan["project"])
    job = root / "segment-001"
    job.mkdir()
    source = job / "original.mp4"
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=90x160:r=24:d=10",
                    "-f", "lavfi", "-i", "sine=duration=10", "-c:v", "libx264", "-c:a", "aac", str(source)],
                   check=True, capture_output=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    record = {"version": 1, "status": "complete", "expected_sha256": digest,
              "spec": {"mode": "native", "text": plan["segments"][0], "image_sha256": plan["image_sha256"],
                       "agent_id": "offline-test", "duration_sec": 10}}
    make._write_new_json(job / "job.json", record)
    # Test fixture only: a completed receipt and synthetic media, never a new provider submission.
    make._write_new_json(root / "approval.json", {"plan_sha256": plan["plan_sha256"], "agent_id": "offline-test"})
    monkeypatch.setattr(native, "resume", lambda *_: record)
    class ASR:
        def __init__(self, _):
            pass
        def transcribe(self, _):
            return [{"word": text.rstrip("，。"), "start": start, "end": end, "conf": 1}
                    for text, start, end in [(BEATS["hook"], .1, .8), (BEATS["point_1"], 1.1, 2.8),
                                             (BEATS["point_2"], 3.2, 4.8), (BEATS["point_3"], 5.2, 7.0),
                                             (BEATS["closing"], 7.5, 9.4)]]
    monkeypatch.setattr(auto_pack, "VoskASRProvider", ASR)
    result = make.run_project(str(root))
    qa = json.loads(Path(result["qa"]).read_text(encoding="utf-8"))
    assert result["alignment_status"] == "matched"
    assert {"TextCard", "HostReframe", "KeywordEmphasis"} <= set(qa["rendered_components"])
    assert qa["rendered_components"].count("KeywordEmphasis") == 4
    assert qa["generation_requests"] == 0
    plan_bytes = (root / "plan.json").read_bytes()
    monkeypatch.setattr(ASR, "transcribe", lambda *_: (_ for _ in ()).throw(RuntimeError("missing model")))
    edited = make.restyle_project(str(root), "auto")
    fallback = json.loads(Path(edited["qa"]).read_text(encoding="utf-8"))
    assert edited["alignment_status"] == "fallback" and any("估算" in w for w in edited["warnings"])
    assert fallback["rendered_components"].count("KeywordEmphasis") == 4 and fallback["component_timing"] == "estimated"
    assert (root / "plan.json").read_bytes() == plan_bytes
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
