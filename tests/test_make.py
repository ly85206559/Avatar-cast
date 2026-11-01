import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from dhp import make, native
from dhp.grok_gateway import SubmissionUnknown


@pytest.fixture
def image(tmp_path):
    path = tmp_path / "presenter.png"
    Image.new("RGB", (32, 32), "white").save(path)
    return path


def test_plan_preserves_script_and_does_not_connect(image, tmp_path, monkeypatch):
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("plan contacted gateway"))
    text = "第一段口播内容，介绍我们的项目。" * 4
    result = make.create_plan(str(image), text, str(tmp_path / "project"))
    assert "".join(result["segments"]) == text
    assert len(result["segments"]) > 1
    assert result["billing"]["estimated_cost"] is None
    assert not (tmp_path / "project" / "approval.json").exists()


def test_show_returns_the_hash_of_the_plan_the_user_sees(image, tmp_path, monkeypatch, capsys):
    result = make.create_plan(str(image), "一段测试。", str(tmp_path / "project"))
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("show contacted gateway"))
    assert make.main(["show", "--project", result["project"]]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["segments"] == ["一段测试。"]
    assert shown["plan_sha256"] == result["plan_sha256"]


def test_plan_does_not_split_long_english_word(image, tmp_path):
    text = "AvatarCast " + ("A" * 40) + " finished."
    result = make.create_plan(str(image), text, str(tmp_path / "project"))
    assert ("A" * 40) in result["segments"][0]
    assert " ".join(result["segments"]) == text


def test_plan_rejects_unsupported_image_before_creating_project(tmp_path):
    image = tmp_path / "presenter.bmp"
    Image.new("RGB", (32, 32), "white").save(image)
    project = tmp_path / "project"
    with pytest.raises(ValueError, match="JPEG, PNG, or WebP"):
        make.create_plan(str(image), "一段测试", str(project))
    assert not project.exists()


def test_run_requires_approval_before_contact(image, tmp_path, monkeypatch):
    result = make.create_plan(str(image), "一段测试", str(tmp_path / "project"))
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted gateway"))
    with pytest.raises(ValueError, match="confirm-allowance"):
        make.run_project(result["project"])
    assert not (Path(result["project"]) / "approval.json").exists()


def test_changed_image_stops_before_contact(image, tmp_path, monkeypatch):
    result = make.create_plan(str(image), "一段测试", str(tmp_path / "project"))
    Image.new("RGB", (32, 32), "blue").save(image)
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted gateway"))
    with pytest.raises(ValueError, match="image changed"):
        make.run_project(result["project"], confirm=True)


def test_missing_chinese_font_stops_before_contact(image, tmp_path, monkeypatch):
    result = make.create_plan(str(image), "一段测试", str(tmp_path / "project"))
    monkeypatch.setattr(make, "doctor", lambda: {"ffmpeg": {"available": True, "subtitles": True, "libx264": True},
                                                "chinese_font": "missing"})
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted gateway"))
    with pytest.raises(ValueError, match="Chinese font"):
        make.run_project(result["project"], confirm=True, plan_sha256=result["plan_sha256"])


def test_changed_plan_before_approval_stops_before_contact(image, tmp_path, monkeypatch):
    result = make.create_plan(str(image), "一段测试", str(tmp_path / "project"))
    plan_path = Path(result["project"]) / "plan.json"
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    data["segments"][0] = "改变后的台词"
    plan_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted gateway"))
    with pytest.raises(ValueError, match="reviewed SHA-256"):
        make.run_project(result["project"], confirm=True, plan_sha256=result["plan_sha256"])


def test_existing_segment_without_receipt_does_not_get_resubmitted(image, tmp_path, monkeypatch):
    result = make.create_plan(str(image), "一段测试", str(tmp_path / "project"))
    root = Path(result["project"])
    make._write_new_json(root / "approval.json", {"plan_sha256": native._sha256(root / "plan.json"), "agent_id": "bot"})
    (root / "segment-001").mkdir()
    monkeypatch.setattr(make, "doctor", lambda: {"ffmpeg": {"available": True, "subtitles": True, "libx264": True}})
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted gateway"))
    with pytest.raises(ValueError, match="job.json"):
        make.run_project(str(root))


def test_plan_changes_after_approval_are_rejected(image, tmp_path, monkeypatch):
    result = make.create_plan(str(image), "一段测试", str(tmp_path / "project"))
    root = Path(result["project"])
    approval = {"plan_sha256": native._sha256(root / "plan.json"), "agent_id": "bot"}
    make._write_new_json(root / "approval.json", approval)
    data = json.loads((root / "plan.json").read_text(encoding="utf-8"))
    data["segments"][0] = "改过的台词"
    (root / "plan.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(make, "doctor", lambda: {"ffmpeg": {"available": True, "subtitles": True, "libx264": True}})
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: pytest.fail("contacted gateway"))
    with pytest.raises(ValueError, match="approved plan changed"):
        make.run_project(str(root))


def test_multiple_bots_require_selection():
    class Gateway:
        def list_agents(self):
            return [{"id": "one"}, {"id": "two"}]

    with pytest.raises(ValueError, match="Select one bot"):
        make._select_bot(Gateway(), None)
    assert make._select_bot(Gateway(), "two") == "two"


def test_attention_stops_before_starting_later_segments(image, tmp_path, monkeypatch, capsys):
    class Gateway:
        def list_agents(self):
            return [{"id": "bot", "isRunningTurn": False}]

    plan = make.create_plan(str(image), "甲" * 24 + "。" + "乙" * 24 + "。", str(tmp_path / "project"))
    project = plan["project"]
    monkeypatch.setattr(make, "doctor", lambda: {"ffmpeg": {"available": True, "subtitles": True, "libx264": True}})
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: Gateway())
    started = []
    monkeypatch.setattr(native, "start", lambda spec, _: started.append(spec) or {"status": "needs_attention"})
    monkeypatch.setattr(native, "_wait", lambda *_: {"status": "needs_attention", "last_reply": "Account needs attention."})
    assert make.main(["run", "--project", project, "--confirm-allowance", "--plan-sha256", plan["plan_sha256"]]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "needs_attention" and result["last_reply"] == "Account needs attention."
    assert len(started) == 1


def test_project_lock_blocks_concurrent_runs(tmp_path):
    with make._project_lock(tmp_path):
        with pytest.raises(ValueError, match="already running"):
            with make._project_lock(tmp_path):
                pass
    with make._project_lock(tmp_path):
        pass


def test_doctor_only_reports_safe_bot_fields(monkeypatch):
    class Gateway:
        def list_agents(self):
            return [{"id": "bot", "name": "Presenter", "token": "never-display"}]

    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: Gateway())
    report = make.doctor(online=True)
    assert report["grok_bot"]["connection"] == "ok"
    assert report["grok_bot"]["bots"] == [{"id": "bot", "name": "Presenter"}]
    assert "never-display" not in json.dumps(report)


def test_online_doctor_returns_failure_when_gateway_unavailable(monkeypatch, capsys):
    monkeypatch.setattr(make, "doctor", lambda *args: {
        "ffmpeg": {"available": True, "subtitles": True, "libx264": True},
        "chinese_font": "available", "grok_bot": {"connection": "unavailable"},
    })
    assert make.main(["doctor", "--online"]) == 1
    assert json.loads(capsys.readouterr().out)["grok_bot"]["connection"] == "unavailable"


@pytest.mark.parametrize("platform,command", [
    ("win32", "pwsh -NoProfile -File scripts/setup_grok_bot_windows.ps1"),
    ("darwin", "python scripts/setup_grok_bot_unix.py"),
    ("linux", "python scripts/setup_grok_bot_unix.py"),
])
def test_sleeping_gateway_gives_recovery_steps_without_submitting(monkeypatch, capsys, platform, command):
    from dhp.grok_gateway import GatewayError

    monkeypatch.setattr(make.sys, "platform", platform)
    def unavailable(*args, **kwargs):
        raise GatewayError("Gateway listAgents returned HTTP 417.", status_code=417)
    monkeypatch.setattr(make, "run_project", unavailable)
    assert make.main(["resume", "--project", "existing-project"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "connection_unavailable"
    assert result["recovery"]["setup_command"] == command
    assert result["recovery"]["reason"] == "possibly_sleeping_or_stale_gateway"
    assert result["recovery"]["resume_existing_only"] is True
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize("segment_count", [1, 3])
def test_resume_without_resubmitting_and_assemble(image, tmp_path, monkeypatch, segment_count):
    ffmpeg = native._find_ffmpeg()
    if not ffmpeg or not all(make.doctor()["ffmpeg"].values()):
        pytest.skip("FFmpeg with subtitles and libx264 is required")
    source = tmp_path / "synthetic.mp4"
    subprocess.run([
        ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=blue:s=90x160:r=24:d=0.7",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000:duration=0.7",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(source),
    ], check=True, capture_output=True)

    class Gateway:
        def __init__(self):
            self.sent = []
            self.ready = False

        def list_agents(self):
            return [{"id": "bot", "isRunningTurn": False}]

        def upload_attachment(self, agent_id, local_path, expected_sha256=None):
            assert hashlib.sha256(Path(local_path).read_bytes()).hexdigest() == expected_sha256
            return "/workspace/input.png"

        def send_prompt(self, agent_id, prompt, nonce, attachment_paths, attachment_names):
            self.sent.append(nonce)
            if len(self.sent) == 1:
                raise SubmissionUnknown("connection interrupted")
            return {"accepted": True}

        def transcript_tail(self, agent_id, limit=200):
            entries = []
            for nonce in self.sent:
                request = "req-" + nonce
                entries.append({"kind": "message", "clientNonce": nonce, "requestId": request})
                if self.ready:
                    digest = hashlib.sha256(source.read_bytes()).hexdigest()
                    marker = f"AVATARCAST_RESULT {nonce} /workspace/avatarcast-{nonce}.mp4 {digest}"
                    entries.append({"kind": "send-message", "requestId": request,
                                    "message": {"type": "text", "content": marker}})
            return {"entries": entries}

        def download_attachment(self, agent_id, remote_path, output_path, expected_sha256=None):
            shutil.copyfile(source, output_path)
            assert hashlib.sha256(Path(output_path).read_bytes()).hexdigest() == expected_sha256
            return {"sha256": expected_sha256}

    gateway = Gateway()
    monkeypatch.setattr(make.GatewayClient, "from_config", lambda *_: gateway)
    text = "".join(character * 24 + "。" for character in "甲乙丙"[:segment_count])
    if segment_count == 1:
        plan = make.create_brief_plan(str(image), {"request": "知识讲解", "script": text,
                                      "title": "测试讲解"}, str(tmp_path / "project"))
    else:
        plan = make.create_plan(str(image), text, str(tmp_path / "project"))
    project = plan["project"]
    first = make.run_project(project, confirm=True, plan_sha256=plan["plan_sha256"], wait_seconds=0)
    assert first["status"] == "waiting" and first["segment_status"] == "submission_unknown"
    assert len(gateway.sent) == 1
    assert make.run_project(project, wait_seconds=0)["status"] == "waiting"
    assert len(gateway.sent) == 1
    gateway.ready = True
    result = make.run_project(project, wait_seconds=0)
    assert result["status"] == "ready_for_review" and result["segment_count"] == segment_count
    assert len(gateway.sent) == segment_count
    qa = json.loads(Path(result["qa"]).read_text(encoding="utf-8"))
    assert qa["segment_count"] == segment_count and qa["unique_source_count"] == 1
    assert qa["quality_verdict"] == "unverified" and qa["subtitle_review"] == "required"
    assert qa["presentation"] == plan["presentation"]
    assert make.run_project(project, wait_seconds=0)["status"] == "ready_for_review"
    assert len(gateway.sent) == segment_count
