import shutil

import pytest


@pytest.mark.skipif(shutil.which("tts") is None, reason="sandbox tts command not present")
def test_command_tts_synthesizes_mandarin(tmp_path):
    from dhp.tts_command import CommandTTSProvider
    out = tmp_path / "s1.mp3"
    audio = CommandTTSProvider().synthesize(
        {"text": "今天天气不错。"}, str(out))
    assert out.is_file() and out.stat().st_size > 0
    assert audio.duration_sec > 0
    assert len(audio.sha256) == 64
