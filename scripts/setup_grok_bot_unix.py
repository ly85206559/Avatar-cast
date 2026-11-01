#!/usr/bin/env python3
"""Import a running Grok Bot gateway on macOS/Linux using a local CLI login.

This uses the same unofficial backend as the Windows importer. It does not
start the remote computer, send a prompt, or print credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class SetupError(Exception):
    """A safe, user-facing setup failure without credentials."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _read_config(path: Path) -> tuple[bytes, dict]:
    """Read only a current user's private, regular config without following symlinks."""
    try:
        parent = path.parent.stat()
        if parent.st_uid != os.geteuid() or parent.st_mode & 0o022:
            raise SetupError("The config directory must be owned by this user and not group/world writable.")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as source:
            info = os.fstat(source.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or info.st_mode & 0o077 or info.st_mode & 0o600 != 0o600):
                raise SetupError("The config must be a regular file owned by this user with mode 600.")
            raw = source.read()
        config = json.loads(raw.decode("utf-8"))
    except SetupError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise SetupError("Cannot read a private ~/.gbm/config.json; sign in with the Grok Bot CLI first.") from exc
    if not isinstance(config, dict):
        raise SetupError("The existing config is not a JSON object; it was not changed.")
    return raw, config


def _request(method: str, token: str, body: dict) -> dict:
    request = urllib.request.Request(
        "https://api2.cursor.sh/aiserver.v1.GrokBotService/" + method,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token,
                 "Connect-Protocol-Version": "1", "x-cursor-client-type": "sand",
                 "x-cursor-client-version": "0.1.0", "x-sand-box-namespace": "prod"},
        method="POST",
    )
    try:
        with urllib.request.build_opener(_NoRedirect).open(request, timeout=20) as response:
            result = json.load(response)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise SetupError("Unable to check the Grok Bot computer or gateway; verify the account connection.") from exc
    if not isinstance(result, dict):
        raise SetupError("The provider returned an invalid response; no configuration was changed.")
    return result


def _gateway(route: dict) -> dict:
    url = route.get("gatewayUrl")
    token = route.get("gatewayToken")
    try:
        parsed = urllib.parse.urlsplit(url) if isinstance(url, str) else None
        if (not parsed or parsed.scheme != "https" or not parsed.hostname
                or not parsed.hostname.endswith(".cursorvm.com") or parsed.username or parsed.password
                or parsed.query or parsed.fragment or not isinstance(token, str) or not token
                or "\n" in token or "\r" in token):
            raise ValueError
        parsed.port  # Validate any explicit port.
    except ValueError as exc:
        raise SetupError("The provider returned an unsupported gateway; no configuration was changed.") from exc
    headers = {}
    if route.get("networkToken"):
        headers["x-anyrun-network-token"] = route["networkToken"]
    elif route.get("gatewayPortToken"):
        headers["x-anyrun-port-token"] = route["gatewayPortToken"]
    if any(not isinstance(v, str) or "\n" in v or "\r" in v for v in headers.values()):
        raise SetupError("The provider returned invalid gateway headers; no configuration was changed.")
    return {"baseUrl": url, "token": token, "headers": headers}


def import_gateway(path: Path, wait_seconds: int = 0) -> None:
    if not 0 <= wait_seconds <= 120:
        raise SetupError("wait-seconds must be between 0 and 120.")
    original, config = _read_config(path)
    token = config.get("accessToken")
    if not isinstance(token, str) or not re.fullmatch(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token):
        raise SetupError("No valid CLI login found; sign in with the same Grok Bot account first.")
    deadline = time.monotonic() + wait_seconds
    state = _request("GetSandBoxRunState", token, {})
    while state.get("state") not in ("SAND_BOX_RUN_STATE_RUNNING", 3):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SetupError("The Grok Bot computer is not running; wake it in the desktop app and run setup again.")
        time.sleep(min(2, remaining))
        state = _request("GetSandBoxRunState", token, {})
    route = _request("EnsureSandBox", token, {"wake": False})
    if route.get("runState") not in ("SAND_BOX_RUN_STATE_RUNNING", 3):
        raise SetupError("The Grok Bot computer is no longer running; no configuration was changed.")
    config["gateway"] = _gateway(route)

    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".avatarcast-gateway-", dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as dest:
            os.fchmod(dest.fileno(), 0o600)
            json.dump(config, dest, ensure_ascii=False, indent=2)
            dest.write("\n")
        current, _ = _read_config(path)
        if current != original:
            raise SetupError("The config changed during setup; it was not overwritten.")
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path.home() / ".gbm" / "config.json")
    parser.add_argument("--wait-seconds", type=int, default=30,
                        help="wait 0–120 seconds for an already-starting computer; never wakes it")
    args = parser.parse_args()
    if sys.platform != "darwin" and not sys.platform.startswith("linux"):
        print("This setup is for macOS and Linux; Windows users should use setup_grok_bot_windows.ps1.", file=sys.stderr)
        return 1
    try:
        import_gateway(args.config.expanduser(), args.wait_seconds)
    except (SetupError, OSError) as exc:
        print(f"Grok Bot setup failed: {exc if isinstance(exc, SetupError) else 'local file operation failed.'}", file=sys.stderr)
        return 1
    print("Grok Bot gateway imported. Credentials were not displayed; run 'dhp make doctor --online'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
