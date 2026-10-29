import json
import shutil
from pathlib import Path

import pytest

from dhp.demo import run_demo

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed")

ROOT = Path(__file__).resolve().parents[1]


def test_offline_demo_produces_warn_qa_not_pass(tmp_path):
    report = run_demo(
        tmp_path / "demo",
        ROOT / "examples" / "demo-script.json",
        ROOT / "examples" / "demo-brief.json",
    )
    assert report["demo"] is True
    assert report["spent"] == 0.0
    assert report["lipsync"] == "not_evaluated"
    assert report["face_consistency"] == "not_evaluated"
    assert report["asr"] == "not_evaluated"
    # 3 demo segments x 2.0s synthetic each.
    assert abs(report["duration_sec"] - 6.0) < 0.5
    qa = json.loads((tmp_path / "demo" / "qa.json").read_text(encoding="utf-8"))
    assert len(qa) == 3
    assert all(r["verdict"] == "warn" for r in qa)
    assert all(r["cost"] == 0.0 for r in qa)
    srt = (tmp_path / "demo" / "demo.srt").read_text(encoding="utf-8")
    script = json.loads((ROOT / "examples" / "demo-script.json").read_text(encoding="utf-8"))
    assert all(" ".join(segment["text"].splitlines()) in srt for segment in script)


def test_cli_demo_dispatch_uses_sys_argv(tmp_path, monkeypatch):
    """Console scripts call main() with no argv; demo must still dispatch."""
    import sys

    from dhp.cli import main

    monkeypatch.setattr(sys, "argv", [
        "dhp", "demo", "--script", str(ROOT / "examples" / "demo-script.json"),
        "--brief", str(ROOT / "examples" / "demo-brief.json"),
        "--out", str(tmp_path / "cli-demo"),
    ])
    assert main() == 0
    assert (tmp_path / "cli-demo" / "demo-final.mp4").exists()
