import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from dhp import native
from dhp.grok_gateway import SubmissionUnknown


class FakeGateway:
    def __init__(self, *, unknown=False):
        self.unknown = unknown
        self.sent = []
        self.entries = []
        self.downloads = 0

    def list_agents(self):
        return [{"id": "bot", "isRunningTurn": False}]

    def upload_attachment(self, agent_id, local_path, *, expected_sha256=None):
        assert hashlib.sha256(Path(local_path).read_bytes()).hexdigest() == expected_sha256
        return "/workspace/input.png"

    def send_prompt(self, agent_id, prompt, nonce, attachment_paths, attachment_names):
        self.sent.append((agent_id, prompt, nonce, attachment_paths, attachment_names))
        if self.unknown:
            raise SubmissionUnknown("outcome unknown")
        return {"accepted": True}

    def transcript_tail(self, agent_id, limit=50):
        return {"entries": self.entries}

    def download_attachment(self, agent_id, remote_path, output_path, expected_sha256=None):
        self.downloads += 1
        payload = b"provider-video"
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
        Path(output_path).write_bytes(payload)
        return {"path": str(output_path), "size": len(payload), "sha256": expected_sha256}


@pytest.fixture
def spec(tmp_path):
    image = tmp_path / "presenter.png"
    Image.new("RGB", (20, 20), "white").save(image)
    return native.plan(str(image), "你好，这是测试。", "bot", str(tmp_path / "out"), 10)


def result_entries(job):
    digest = hashlib.sha256(b"provider-video").hexdigest()
    marker = f"AVATARCAST_RESULT {job['nonce']} {job['remote_path']} {digest}"
    return [
        {"kind": "message", "clientNonce": job["nonce"], "requestId": "request-1"},
        {"kind": "send-message", "requestId": "request-1",
         "message": {"type": "text", "content": marker}},
    ]


def test_plan_does_not_connect_or_create_output(tmp_path, monkeypatch, capsys):
    image = tmp_path / "presenter.png"
    Image.new("RGB", (20, 20), "white").save(image)
    monkeypatch.setattr(native.GatewayClient, "from_config",
                        lambda *_: pytest.fail("plan must not contact a gateway"))
    out = tmp_path / "new-job"
    rc = native.main(["start", "--image", str(image), "--text", "测试",
                      "--agent-id", "bot", "--output-dir", str(out),
                      "--billing", "allowance"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["status"] == "plan_only"
    assert not out.exists()


def test_unknown_submission_is_reconciled_without_resubmission(spec, monkeypatch):
    monkeypatch.setattr(native, "_find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(native, "_check_media", lambda *_: {
        "decode": "pass", "audio": "non_silent", "audio_rms": 0.1})
    gateway = FakeGateway(unknown=True)
    job = native.start(spec, gateway)
    assert job["status"] == "submission_unknown"
    assert len(gateway.sent) == 1
    assert json.loads((Path(spec["output_dir"]) / "job.json").read_text(encoding="utf-8"))["nonce"] == job["nonce"]

    assert native.resume(spec["output_dir"], gateway)["status"] == "submission_unknown"
    assert len(gateway.sent) == 1
    gateway.entries = result_entries(job)
    finished = native.resume(spec["output_dir"], gateway)
    assert finished["status"] == "complete"
    assert len(gateway.sent) == 1
    assert gateway.downloads == 1
    qa = json.loads((Path(spec["output_dir"]) / "qa.json").read_text(encoding="utf-8"))
    assert qa["quality_verdict"] == "unverified"
    assert qa["cost"]["actual"] is None
    assert native.resume(spec["output_dir"], gateway)["status"] == "complete"
    assert gateway.downloads == 1


def test_result_must_match_nonce_request_and_expected_path(spec, monkeypatch):
    monkeypatch.setattr(native, "_find_ffmpeg", lambda: "ffmpeg")
    gateway = FakeGateway()
    job = native.start(spec, gateway)
    entries = result_entries(job)
    entries[1]["requestId"] = "another-request"
    gateway.entries = entries
    assert native.resume(spec["output_dir"], gateway)["status"] == "accepted"
    assert gateway.downloads == 0
    entries[1]["requestId"] = "request-1"
    entries[1]["message"]["content"] = entries[1]["message"]["content"].replace(
        job["remote_path"], "/workspace/unrelated.mp4")
    assert native.resume(spec["output_dir"], gateway)["status"] == "needs_attention"
    assert gateway.downloads == 0


def test_existing_wrong_original_is_never_overwritten(spec, monkeypatch):
    monkeypatch.setattr(native, "_find_ffmpeg", lambda: "ffmpeg")
    gateway = FakeGateway()
    job = native.start(spec, gateway)
    gateway.entries = result_entries(job)
    raw = Path(spec["output_dir"]) / "original.mp4"
    raw.write_bytes(b"unexpected")
    with pytest.raises(ValueError, match="does not match"):
        native.resume(spec["output_dir"], gateway)
    assert raw.read_bytes() == b"unexpected"
    assert gateway.downloads == 0


def test_busy_bot_stops_before_upload_or_submission(spec, monkeypatch):
    monkeypatch.setattr(native, "_find_ffmpeg", lambda: "ffmpeg")
    gateway = FakeGateway()
    gateway.list_agents = lambda: [{"id": "bot", "isRunningTurn": True}]
    with pytest.raises(ValueError, match="busy"):
        native.start(spec, gateway)
    assert not Path(spec["output_dir"]).exists()
    assert not gateway.sent


def test_corrupt_or_silent_media_never_gets_complete_status(spec, monkeypatch):
    monkeypatch.setattr(native, "_find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(native, "_check_media", lambda *_: {
        "decode": "pass", "audio": "silent", "audio_rms": 0.0})
    gateway = FakeGateway()
    job = native.start(spec, gateway)
    gateway.entries = result_entries(job)
    assert native.resume(spec["output_dir"], gateway)["status"] == "media_unverified"
    qa = json.loads((Path(spec["output_dir"]) / "qa.json").read_text(encoding="utf-8"))
    assert qa["checks"]["audio"] == "silent"
    assert qa["quality_verdict"] == "unverified"


def test_human_review_is_separate_from_unmeasured_scores(spec, monkeypatch):
    monkeypatch.setattr(native, "_find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(native, "_check_media", lambda *_: {
        "decode": "pass", "audio": "non_silent"})
    gateway = FakeGateway()
    job = native.start(spec, gateway)
    gateway.entries = result_entries(job)
    native.resume(spec["output_dir"], gateway)
    qa = native.review(spec["output_dir"], "accept", "Reviewed the video")
    assert qa["human_review"]["status"] == "accepted"
    assert qa["quality_verdict"] == "unverified"
    assert qa["lip_sync"] == "not_evaluated"
    assert json.loads((Path(spec["output_dir"]) / "qa.json").read_text(encoding="utf-8")) == qa


def test_finished_bot_response_without_video_requests_attention(spec, monkeypatch):
    monkeypatch.setattr(native, "_find_ffmpeg", lambda: "ffmpeg")
    gateway = FakeGateway()
    job = native.start(spec, gateway)
    gateway.entries = [
        {"kind": "message", "clientNonce": job["nonce"], "requestId": "request-1"},
        {"kind": "send-message", "requestId": "request-1",
         "message": {"type": "text", "content": "Please confirm the provider charge."}},
    ]
    recovered = native.resume(spec["output_dir"], gateway)
    assert recovered["status"] == "needs_attention"
    assert recovered["last_reply"] == "Please confirm the provider charge."
    assert len(gateway.sent) == 1


def test_bots_only_exposes_safe_fields(monkeypatch, capsys):
    gateway = FakeGateway()
    gateway.list_agents = lambda: [{"id": "bot", "name": "Presenter", "token": "secret"}]
    monkeypatch.setattr(native.GatewayClient, "from_config", lambda *_: gateway)
    assert native.main(["bots"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"id": "bot", "name": "Presenter"}]


def test_resume_uses_previously_matched_request_when_nonce_ages_out(spec, monkeypatch):
    monkeypatch.setattr(native, "_find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(native, "_check_media", lambda *_: {"decode": "pass", "audio": "non_silent"})
    gateway = FakeGateway()
    job = native.start(spec, gateway)
    entries = result_entries(job)
    gateway.entries = entries[:1]
    native.resume(spec["output_dir"], gateway)
    gateway.entries = entries[1:]
    assert native.resume(spec["output_dir"], gateway)["status"] == "complete"


def test_resume_rejects_tampered_result_path(spec, monkeypatch):
    monkeypatch.setattr(native, "_find_ffmpeg", lambda: "ffmpeg")
    gateway = FakeGateway()
    job = native.start(spec, gateway)
    job["remote_path"] = "/workspace/unrelated.mp4"
    native._write_json(Path(spec["output_dir"]) / "job.json", job)
    with pytest.raises(ValueError, match="invalid result path"):
        native.resume(spec["output_dir"], gateway)
    assert gateway.downloads == 0


def test_completed_job_requires_qa_report(spec, monkeypatch):
    monkeypatch.setattr(native, "_find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(native, "_check_media", lambda *_: {"decode": "pass", "audio": "non_silent"})
    gateway = FakeGateway()
    job = native.start(spec, gateway)
    gateway.entries = result_entries(job)
    native.resume(spec["output_dir"], gateway)
    (Path(spec["output_dir"]) / "qa.json").unlink()
    with pytest.raises(ValueError, match="missing a valid QA"):
        native.resume(spec["output_dir"], gateway)
