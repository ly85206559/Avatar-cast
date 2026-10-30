import base64
import hashlib
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from dhp.grok_gateway import GatewayClient, GatewayError, SubmissionUnknown


@pytest.fixture
def gateway():
    state = {"calls": [], "mode": "normal", "video": b"a real test video payload"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["calls"].append((self.path, payload, self.headers.get("Authorization")))
            if state["mode"] == "close" and self.path == "/api/sendPrompt":
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            if state["mode"] == "partial" and self.path == "/api/sendPrompt":
                self.send_response(200)
                self.send_header("Content-Length", "100")
                self.end_headers()
                self.wfile.write(b'{"accepted":')
                self.wfile.flush()
                self.close_connection = True
                return
            if state["mode"] == "redirect":
                self.send_response(307)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/stolen")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if self.path == "/api/listAgents":
                result = [{"id": "bot", "isRunningTurn": False}]
            elif self.path == "/api/uploadAttachment":
                result = {"path": "/workspace/input.png"}
            elif self.path == "/api/sendPrompt":
                result = {"accepted": True}
            elif self.path == "/api/getAgentTranscriptTail":
                result = {"entries": [{"seq": 3}], "nextBeforeSeq": 2}
            elif self.path == "/api/readAttachmentChunk":
                if state["mode"] == "null":
                    result = None
                else:
                    data = state["video"]
                    chunk = data[payload["offset"]:payload["offset"] + payload["length"]]
                    if state["mode"] == "short" and payload["length"]:
                        chunk = chunk[:-1]
                    result = {"totalSize": len(data), "bytesBase64": base64.b64encode(chunk).decode(),
                              "mime": "video/mp4", "resolvedName": "sample.mp4"}
            else:
                self.send_error(404)
                return
            encoded = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = GatewayClient(f"http://127.0.0.1:{server.server_port}", "test-secret")
    try:
        yield client, state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_gateway_replays_actual_upload_submit_and_transcript_shapes(gateway, tmp_path):
    client, state = gateway
    image = tmp_path / "portrait.png"
    image.write_bytes(b"portrait bytes")
    assert client.list_agents()[0]["id"] == "bot"
    remote = client.upload_attachment("bot", image, expected_sha256=hashlib.sha256(image.read_bytes()).hexdigest())
    result = client.send_prompt("bot", "你好", "saved-nonce", [remote], [image.name])
    assert result == {"accepted": True}
    assert client.transcript_tail("bot", 5)["entries"] == [{"seq": 3}]
    assert [entry[0] for entry in state["calls"]] == [
        "/api/listAgents", "/api/uploadAttachment", "/api/sendPrompt", "/api/getAgentTranscriptTail"]
    upload = state["calls"][1][1]
    assert base64.b64decode(upload["bytesBase64"]) == b"portrait bytes"
    assert state["calls"][2][1] == {"agentId": "bot", "prompt": "你好", "clientNonce": "saved-nonce",
                                   "attachmentPaths": [remote], "attachmentNames": ["portrait.png"]}
    assert state["calls"][3][1] == {"id": "bot", "limit": 5}


def test_download_checks_chunks_and_digest_without_overwriting(gateway, tmp_path):
    client, state = gateway
    output = tmp_path / "original.mp4"
    expected = hashlib.sha256(state["video"]).hexdigest()
    result = client.download_attachment("bot", "/workspace/original.mp4", output,
                                        expected_sha256=expected, chunk_size=5)
    assert output.read_bytes() == state["video"]
    assert result["size"] == len(state["video"])
    assert result["sha256"] == expected
    with pytest.raises(GatewayError, match="overwrite"):
        client.download_attachment("bot", "/workspace/original.mp4", output)
    assert output.read_bytes() == state["video"]


def test_changed_attachment_is_not_uploaded(gateway, tmp_path):
    client, state = gateway
    image = tmp_path / "portrait.png"
    image.write_bytes(b"old image")
    expected = hashlib.sha256(image.read_bytes()).hexdigest()
    image.write_bytes(b"new image")
    with pytest.raises(GatewayError, match="checksum changed"):
        client.upload_attachment("bot", image, expected_sha256=expected)
    assert state["calls"] == []


@pytest.mark.parametrize("mode", ["null", "short"])
def test_download_rejects_invalid_data_without_leaving_an_output(gateway, tmp_path, mode):
    client, state = gateway
    state["mode"] = mode
    output = tmp_path / "original.mp4"
    with pytest.raises(GatewayError):
        client.download_attachment("bot", "/workspace/original.mp4", output, chunk_size=5)
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []


def test_download_rejects_a_digest_mismatch(gateway, tmp_path):
    client, _ = gateway
    with pytest.raises(GatewayError, match="checksum"):
        client.download_attachment("bot", "/workspace/original.mp4", tmp_path / "original.mp4",
                                   expected_sha256="0" * 64)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("remote", ["file:///home/box/attachment.mp4", "relative.mp4",
                                    "/workspace/../other.mp4", "//other/remote.mp4"])
def test_download_rejects_ambiguous_paths_before_request(gateway, tmp_path, remote):
    client, state = gateway
    with pytest.raises(GatewayError, match="absolute gateway"):
        client.download_attachment("bot", remote, tmp_path / "video.mp4")
    assert state["calls"] == []
    assert list(tmp_path.iterdir()) == []


def test_download_rejects_invalid_digest_before_request(gateway, tmp_path):
    client, state = gateway
    with pytest.raises(GatewayError, match="SHA-256"):
        client.download_attachment("bot", "/workspace/a.mp4", tmp_path / "video.mp4",
                                   expected_sha256="invalid")
    assert state["calls"] == []


@pytest.mark.parametrize("mode", ["close", "partial"])
def test_uncertain_submit_is_never_automatically_retried(gateway, mode):
    client, state = gateway
    state["mode"] = mode
    with pytest.raises(SubmissionUnknown, match="outcome is unknown"):
        client.send_prompt("bot", "generate one video", "saved-nonce")
    assert sum(call[0] == "/api/sendPrompt" for call in state["calls"]) == 1


def test_redirect_is_not_followed_and_credentials_do_not_appear_in_error(gateway):
    client, state = gateway
    state["mode"] = "redirect"
    with pytest.raises(GatewayError) as exc:
        client.list_agents()
    assert "test-secret" not in str(exc.value)
    assert [call[0] for call in state["calls"]] == ["/api/listAgents"]


def test_config_requires_https_except_for_loopback_and_hides_secrets(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"gateway": {"baseUrl": "http://example.com", "token": "test-secret"}}))
    with pytest.raises(GatewayError) as exc:
        GatewayClient.from_config(path)
    assert "test-secret" not in str(exc.value)
