import hashlib
import json
from pathlib import Path
import subprocess

import pytest
from PIL import Image

from dhp import auto_pack, content_templates, make, native, native_assembly, packaging_components


@pytest.mark.parametrize("template_id", content_templates.IDS)
def test_template_slots_become_reviewed_narration_without_gateway(tmp_path, monkeypatch, template_id):
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted gateway"))
    image = tmp_path / "photo.png"
    Image.new("RGB", (32, 48), "white").save(image)
    item = content_templates.get(template_id)
    roles = [s["key"] for s in item["structure"]]
    phrases = [f"第{n + 1}句话" for n in range(len(roles))]
    brief = {"template": template_id, "request": "制作一条短口播", "title": "测试标题",
             "beats": dict(zip(roles, phrases))}
    plan = make.create_brief_plan(str(image), brief, str(tmp_path / "project"))
    assert "".join(plan["segments"]) == "".join(p + "。" for p in phrases)
    assert plan["template"] == {"id": template_id, "version": 1}
    assert plan["presentation"]["style"] == item["style"]
    assert not (Path(plan["project"]) / "approval.json").exists()
    brief["beats"].pop(roles[0])
    with pytest.raises(ValueError, match="slots"):
        make.create_brief_plan(str(image), brief, str(tmp_path / "invalid"))
    brief["beats"][roles[0]] = phrases[0]
    brief["script"] = "未审核的另一份台词"
    with pytest.raises(ValueError, match="differs"):
        make.create_brief_plan(str(image), brief, str(tmp_path / "invalid"))


def test_template_auto_selection_explicit_style_and_plan_tampering(tmp_path, monkeypatch):
    image = tmp_path / "photo.png"
    Image.new("RGB", (32, 48), "white").save(image)
    brief = {"template": "auto", "request": "介绍这个产品的卖点", "script": "真实台词。", "style": "warm"}
    plan = make.create_brief_plan(str(image), brief, str(tmp_path / "project"))
    assert plan["template"]["id"] == "product-intro"
    assert plan["presentation"]["style"] == "warm"
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted gateway"))
    path = Path(plan["project"]) / "plan.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["template"]["id"] = "empathy"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed SHA-256"):
        make.run_project(plan["project"], confirm=True, plan_sha256=plan["plan_sha256"])
    with pytest.raises(ValueError, match="Unknown template"):
        content_templates.resolve("../../arbitrary")
    with pytest.raises(ValueError, match="version"):
        content_templates.validate({"id": "empathy", "version": True})
    assert content_templates.select("讲清楚这个知识") == "knowledge-share"
    assert content_templates.select("鼓励一下觉得累的人") == "empathy"
    assert content_templates.resolve("auto", "普通自我介绍") is None


@pytest.mark.parametrize("template_id", ("product-intro", "knowledge-share", "empathy"))
def test_template_project_run_reuses_completed_job_and_preserves_source(tmp_path, monkeypatch, template_id):
    ffmpeg = native_assembly._find_ffmpeg(None)
    if not all(make.doctor()["ffmpeg"].values()):
        pytest.skip("FFmpeg subtitles and libx264 required")
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted gateway"))
    image = tmp_path / "photo.png"
    Image.new("RGB", (32, 48), "white").save(image)
    plan = make.create_plan(str(image), "每天通勤。随身携带。按需选择。", str(tmp_path / "project"),
                            template=template_id, presentation={"style": "warm"})
    root = Path(plan["project"])
    job = root / "segment-001"
    job.mkdir()
    source = job / "original.mp4"
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=90x160:r=24:d=4",
                    "-f", "lavfi", "-i", "sine=duration=4", "-c:v", "libx264", "-c:a", "aac", str(source)],
                   check=True, capture_output=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    spec = {"mode": "native", "text": plan["segments"][0], "image_sha256": plan["image_sha256"],
            "agent_id": "offline-test", "duration_sec": 10}
    record = {"version": 1, "status": "complete", "spec": spec, "expected_sha256": digest}
    make._write_new_json(job / "job.json", record)
    # Offline receipt simulation: every job already exists, no service is called.
    make._write_new_json(root / "approval.json", {"plan_sha256": plan["plan_sha256"], "agent_id": "offline-test"})
    monkeypatch.setattr(native, "resume", lambda *_: record)
    class ASR:
        def __init__(self, _):
            pass
        def transcribe(self, _):
            return [{"word": w, "start": a, "end": b, "conf": 1}
                    for w, a, b in [("每天通勤", .1, .8), ("随身携带", 1.2, 2.2), ("按需选择", 2.5, 3.6)]]
    monkeypatch.setattr(auto_pack, "VoskASRProvider", ASR)
    result = make.run_project(str(root))
    assert result["template"] == plan["template"] and result["alignment_status"] == "matched"
    qa = json.loads((root / "result/qa.json").read_text(encoding="utf-8"))
    expected = {"product-intro": "HostReframe", "knowledge-share": "StepProgress", "empathy": "KeywordEmphasis"}
    assert expected[template_id] in qa["rendered_components"]
    assert qa["generation_requests"] == 0 and qa["quality_verdict"] == "unverified"
    assert make.run_project(str(root))["status"] == "ready_for_review"
    plan_bytes = (root / "plan.json").read_bytes()
    # A missing model keeps the selected template but discloses a simple fallback.
    monkeypatch.setattr(ASR, "transcribe", lambda *_: (_ for _ in ()).throw(RuntimeError("missing model")))
    edited = make.restyle_project(str(root), "auto")
    assert edited["template"] == plan["template"] and edited["warnings"]
    assert edited["presentation"]["style"] == "warm"
    assert edited["alignment_status"] == "fallback" and edited["generation_requests"] == 0
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert (root / "plan.json").read_bytes() == plan_bytes
    fallback = json.loads(Path(edited["qa"]).read_text(encoding="utf-8"))
    assert fallback["rendered_components"] == ["TextCard"]


def test_templates_keep_unreliable_timing_estimated():
    for template_id in content_templates.IDS:
        pack = content_templates.recipe(content_templates.resolve(template_id), "", [], 10, False)
        packaging_components.validate(pack, 10)
        assert pack["timing"] == "estimated" and len(pack["components"]) == 1


def test_matched_speech_without_usable_card_clauses_reports_limitation(monkeypatch):
    class ASR:
        def __init__(self, _):
            pass
        def transcribe(self, _):
            return [{"word": "好", "start": .1, "end": .5, "conf": 1}]
    monkeypatch.setattr(auto_pack, "VoskASRProvider", ASR)
    result = auto_pack.prepare("unused.mp4", "好。", 2, "explainer", "",
                               template=content_templates.resolve("knowledge-share"))
    assert result["alignment"]["status"] == "matched"
    assert len(result["pack"]["components"]) == 1 and result["warnings"]
