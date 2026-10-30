"""Small client for the Grok Bot gateway used by the native-video workflow.

The gateway is an unofficial, version-dependent interface. A successful
``sendPrompt`` response only means the prompt was accepted; it does not mean
that a video has been generated. In particular, a failed or timed-out submit
must be reconciled against the saved nonce and transcript, never retried here.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import http.client
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class GatewayError(RuntimeError):
    """The gateway request or its response could not be used safely."""


class SubmissionUnknown(GatewayError):
    """A submitted prompt may have been accepted; reconcile before retrying."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GatewayClient:
    """Use a locally configured gateway without printing its credentials."""

    def __init__(self, base_url: str, token: str, headers: dict | None = None,
                 timeout: float = 30.0):
        if not isinstance(base_url, str) or not isinstance(token, str) or not token:
            raise GatewayError("Gateway address and token are required.")
        parsed = urllib.parse.urlsplit(base_url)
        if (not parsed.hostname or parsed.username or parsed.password or
                parsed.query or parsed.fragment or parsed.scheme not in ("https", "http")):
            raise GatewayError("Invalid gateway address.")
        if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise GatewayError("An HTTP gateway must be on the local machine.")
        if headers is not None and not isinstance(headers, dict):
            raise GatewayError("Gateway headers must be an object.")
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._headers = dict(headers or {})
        if any(str(key).lower() in ("authorization", "host", "content-length")
               for key in self._headers):
            raise GatewayError("Gateway extra headers may not override authentication or host.")
        self.timeout = timeout
        self._opener = urllib.request.build_opener(_NoRedirect())

    @classmethod
    def from_config(cls, path: str | Path | None = None) -> "GatewayClient":
        config_path = Path(path) if path is not None else Path.home() / ".gbm" / "config.json"
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            gateway = config["gateway"]
            return cls(gateway["baseUrl"], gateway["token"], gateway.get("headers"))
        except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
            raise GatewayError("Could not read a valid Grok Bot gateway configuration.") from exc

    def _post(self, operation: str, body: dict):
        request = urllib.request.Request(
            f"{self.base_url}/api/{operation}",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", **self._headers,
                     "Authorization": f"Bearer {self._token}"},
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise GatewayError(f"Gateway {operation} returned HTTP {exc.code}.") from None
        except (OSError, http.client.HTTPException, UnicodeError, ValueError):
            raise GatewayError(f"Gateway {operation} failed or returned invalid JSON.") from None

    def list_agents(self) -> list:
        result = self._post("listAgents", {})
        agents = result.get("agents") if isinstance(result, dict) else result
        if not isinstance(agents, list):
            raise GatewayError("Gateway did not return an agent list.")
        return agents

    def upload_attachment(self, agent_id: str, local_path: str | Path, *,
                          expected_sha256: str | None = None) -> str:
        path = Path(local_path)
        if expected_sha256 is not None and (not isinstance(expected_sha256, str) or
                                            not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256)):
            raise GatewayError("Expected attachment checksum must be a SHA-256 hex digest.")
        try:
            contents = path.read_bytes()
        except OSError as exc:
            raise GatewayError("Could not read the local attachment.") from exc
        if expected_sha256 is not None and hashlib.sha256(contents).hexdigest() != expected_sha256.lower():
            raise GatewayError("Local attachment checksum changed; upload was not sent.")
        result = self._post("uploadAttachment", {
            "agentId": agent_id, "filename": path.name,
            "bytesBase64": base64.b64encode(contents).decode("ascii"),
        })
        if not isinstance(result, dict) or not isinstance(result.get("path"), str) or not result["path"]:
            raise GatewayError("Gateway did not return an attachment path.")
        return result["path"]

    def send_prompt(self, agent_id: str, prompt: str, nonce: str,
                    attachment_paths: list[str] | None = None,
                    attachment_names: list[str] | None = None) -> dict:
        paths = list(attachment_paths or [])
        names = list(attachment_names or [])
        if not agent_id or not prompt or not nonce or len(paths) != len(names):
            raise GatewayError("Agent, prompt, saved nonce and matching attachment names are required.")
        body = {"agentId": agent_id, "prompt": prompt, "clientNonce": nonce,
                "attachmentPaths": paths, "attachmentNames": names}
        try:
            result = self._post("sendPrompt", body)
        except GatewayError as exc:
            raise SubmissionUnknown("Prompt submission outcome is unknown; check its nonce and transcript before retrying.") from exc
        if not isinstance(result, dict) or result.get("accepted") is not True:
            raise SubmissionUnknown("Prompt acceptance is unknown; check its nonce and transcript before retrying.")
        return result

    def transcript_tail(self, agent_id: str, limit: int = 50) -> dict:
        result = self._post("getAgentTranscriptTail", {"id": agent_id, "limit": limit})
        if not isinstance(result, dict) or not isinstance(result.get("entries"), list):
            raise GatewayError("Gateway did not return a transcript.")
        return result

    def download_attachment(self, agent_id: str, remote_path: str,
                            output_path: str | Path, *, expected_sha256: str | None = None,
                            chunk_size: int = 512 * 1024) -> dict:
        """Download a known gateway path, verifying every chunk and the final digest.

        ``sha256`` is computed locally. If the provider supplied a digest, pass
        it as ``expected_sha256`` for an independent integrity comparison.
        """
        output = Path(output_path)
        if (not isinstance(remote_path, str) or not remote_path.startswith("/") or
                remote_path.startswith("//") or "\x00" in remote_path or
                any(part in (".", "..") for part in remote_path.split("/")) or chunk_size <= 0):
            raise GatewayError("A known absolute gateway attachment path and a positive chunk size are required.")
        if expected_sha256 is not None and (not isinstance(expected_sha256, str) or
                                            not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256)):
            raise GatewayError("Expected attachment checksum must be a SHA-256 hex digest.")
        if output.exists():
            raise GatewayError("Refusing to overwrite an existing output.")
        result = self._post("readAttachmentChunk", {
            "agentId": agent_id, "path": remote_path, "offset": 0, "length": 0,
        })
        total = result.get("totalSize") if isinstance(result, dict) else None
        if isinstance(total, bool) or not isinstance(total, int) or total <= 0:
            raise GatewayError("Gateway did not return a valid attachment size.")

        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent,
                                             prefix=f".{output.name}.", suffix=".part",
                                             delete=False) as target:
                temporary = Path(target.name)
                digest = hashlib.sha256()
                offset = 0
                while offset < total:
                    length = min(chunk_size, total - offset)
                    part = self._post("readAttachmentChunk", {
                        "agentId": agent_id, "path": remote_path,
                        "offset": offset, "length": length,
                    })
                    if not isinstance(part, dict) or part.get("totalSize") != total:
                        raise GatewayError("Attachment size changed while downloading.")
                    try:
                        chunk = base64.b64decode(part["bytesBase64"], validate=True)
                    except (KeyError, TypeError, ValueError, binascii.Error):
                        raise GatewayError("Gateway returned an invalid attachment chunk.") from None
                    if len(chunk) != length:
                        raise GatewayError("Gateway returned an incomplete attachment chunk.")
                    target.write(chunk)
                    digest.update(chunk)
                    offset += length
            sha256 = digest.hexdigest()
            if expected_sha256 is not None and sha256.lower() != expected_sha256.lower():
                raise GatewayError("Attachment checksum does not match the expected digest.")
            # Create the final name without overwriting a file another process
            # may have created while the download was in progress.
            os.link(temporary, output)
            return {"path": str(output), "size": total, "sha256": sha256}
        except OSError as exc:
            raise GatewayError("Could not save the downloaded attachment.") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
