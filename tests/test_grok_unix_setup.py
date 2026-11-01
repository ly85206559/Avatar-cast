"""Exercise Unix setup with synthetic credentials and no network access."""

import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("grok_unix_setup", ROOT / "scripts/setup_grok_bot_unix.py")
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


@unittest.skipUnless(os.name == "posix", "Unix file permissions are required")
class UnixSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "config.json"
        self.original = {"version": 1, "accessToken": "eyJtest.eyJtest.signature", "keep": {"name": "existing"}}
        self.config.write_text(json.dumps(self.original), encoding="utf-8")
        self.config.chmod(0o600)
        self.calls = []

    def request(self, method, token, body):
        self.calls.append((method, body))
        self.assertEqual(token, self.original["accessToken"])
        if method == "GetSandBoxRunState":
            return {"state": "SAND_BOX_RUN_STATE_RUNNING"}
        return {"runState": 3, "gatewayUrl": "https://example.cursorvm.com",
                "gatewayToken": "synthetic-gateway", "networkToken": "synthetic-network"}

    def test_import_preserves_login_and_only_describes_running_computer(self):
        with mock.patch.object(setup, "_request", side_effect=self.request):
            setup.import_gateway(self.config)
        saved = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(saved["keep"], self.original["keep"])
        self.assertEqual(saved["accessToken"], self.original["accessToken"])
        self.assertEqual(saved["gateway"]["token"], "synthetic-gateway")
        self.assertEqual(saved["gateway"]["headers"]["x-anyrun-network-token"], "synthetic-network")
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.calls, [("GetSandBoxRunState", {}), ("EnsureSandBox", {"wake": False})])

    def test_sleeping_computer_never_calls_ensure_or_changes_config(self):
        original = self.config.read_bytes()
        with mock.patch.object(setup, "_request", return_value={"state": "SLEEPING"}) as request:
            with self.assertRaisesRegex(setup.SetupError, "not running"):
                setup.import_gateway(self.config)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(self.config.read_bytes(), original)

    def test_waits_for_starting_computer_without_waking_or_creating_it(self):
        def request(method, token, body):
            if method == "GetSandBoxRunState" and not self.calls:
                self.calls.append((method, body))
                return {"state": "STARTING"}
            return self.request(method, token, body)
        with (mock.patch.object(setup, "_request", side_effect=request),
              mock.patch.object(setup.time, "sleep") as sleep):
            setup.import_gateway(self.config, wait_seconds=4)
        sleep.assert_called_once()
        self.assertEqual(self.calls, [("GetSandBoxRunState", {}), ("GetSandBoxRunState", {}),
                                     ("EnsureSandBox", {"wake": False})])

    def test_readiness_timeout_preserves_config_and_does_not_ensure(self):
        original = self.config.read_bytes()
        with (mock.patch.object(setup, "_request", return_value={"state": "SLEEPING"}) as request,
              mock.patch.object(setup.time, "sleep"),
              mock.patch.object(setup.time, "monotonic", side_effect=[0, 1, 3])):
            with self.assertRaisesRegex(setup.SetupError, "not running"):
                setup.import_gateway(self.config, wait_seconds=2)
        self.assertEqual(request.call_count, 2)
        self.assertTrue(all(c.args[0] == "GetSandBoxRunState" for c in request.call_args_list))
        self.assertEqual(self.config.read_bytes(), original)

    def test_untrusted_gateway_does_not_save_or_expose_token(self):
        original = self.config.read_bytes()
        routes = [{"state": 3}, {"runState": 3, "gatewayUrl": "https://evil.example",
                                  "gatewayToken": "synthetic-secret"}]
        with mock.patch.object(setup, "_request", side_effect=routes):
            with self.assertRaises(setup.SetupError) as error:
                setup.import_gateway(self.config)
        self.assertNotIn("synthetic-secret", str(error.exception))
        self.assertEqual(self.config.read_bytes(), original)

    def test_insecure_config_or_symlink_is_rejected_before_network(self):
        self.config.chmod(0o644)
        with mock.patch.object(setup, "_request") as request:
            with self.assertRaisesRegex(setup.SetupError, "mode 600"):
                setup.import_gateway(self.config)
            request.assert_not_called()
        self.config.chmod(0o600)
        link = self.root / "link.json"
        link.symlink_to(self.config)
        with mock.patch.object(setup, "_request") as request:
            with self.assertRaises(setup.SetupError):
                setup.import_gateway(link)
            request.assert_not_called()

    def test_config_changed_during_request_is_not_overwritten(self):
        changed = {**self.original, "keep": {"name": "changed elsewhere"}}

        def request(method, token, body):
            result = self.request(method, token, body)
            if method == "EnsureSandBox":
                self.config.write_text(json.dumps(changed), encoding="utf-8")
            return result

        with mock.patch.object(setup, "_request", side_effect=request):
            with self.assertRaisesRegex(setup.SetupError, "changed during setup"):
                setup.import_gateway(self.config)
        self.assertEqual(json.loads(self.config.read_text(encoding="utf-8")), changed)
        self.assertFalse(list(self.root.glob(".avatarcast-gateway-*")))

    def test_cli_output_does_not_expose_credentials(self):
        out, err = io.StringIO(), io.StringIO()
        with (mock.patch.object(setup, "_request", side_effect=self.request),
              mock.patch("sys.argv", ["setup", "--config", str(self.config)]),
              contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)):
            self.assertEqual(setup.main(), 0)
        self.assertNotIn("synthetic-gateway", out.getvalue() + err.getvalue())
        self.assertNotIn("eyJtest", out.getvalue() + err.getvalue())

    def test_backend_request_is_fixed_origin_and_disallows_redirects(self):
        with mock.patch.object(setup.urllib.request, "build_opener") as build:
            build.return_value.open.return_value = io.BytesIO(b'{"state": 3}')
            self.assertEqual(setup._request("GetSandBoxRunState", self.original["accessToken"], {}), {"state": 3})
        self.assertIs(build.call_args.args[0], setup._NoRedirect)
        request = build.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://api2.cursor.sh/aiserver.v1.GrokBotService/GetSandBoxRunState")
        self.assertEqual(json.loads(request.data), {})
        self.assertEqual(request.get_header("Authorization"), "Bearer " + self.original["accessToken"])

    def test_backend_error_does_not_expose_credentials(self):
        with mock.patch.object(setup.urllib.request, "build_opener") as build:
            build.return_value.open.side_effect = setup.urllib.error.URLError("synthetic-secret")
            with self.assertRaises(setup.SetupError) as error:
                setup._request("GetSandBoxRunState", self.original["accessToken"], {})
        self.assertNotIn("synthetic-secret", str(error.exception))
        self.assertNotIn(self.original["accessToken"], str(error.exception))


if __name__ == "__main__":
    unittest.main()
