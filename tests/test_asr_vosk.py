import json
import sys
import types
import wave

import pytest

from dhp.asr_vosk import VoskASRProvider


@pytest.mark.parametrize(
    ("finished", "final", "expected"),
    [
        (
            [[{"word": "你好", "start": 0.0, "end": 0.5, "conf": 0.9}],
             [{"word": "世界", "start": 0.6, "end": 1.0, "conf": 0.8}]],
            [],
            ["你好", "世界"],
        ),
        (
            [[{"word": "第一句", "start": 0.0, "end": 0.5}]],
            [{"word": "结尾", "start": 0.6, "end": 1.0, "conf": 0.7}],
            ["第一句", "结尾"],
        ),
    ],
)
def test_transcribe_keeps_all_finished_and_final_segments(
    tmp_path, monkeypatch, finished, final, expected
):
    # Multiple Vosk endpoints can precede an empty or nonempty FinalResult.
    wav_path = tmp_path / "converted.wav"
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 12000)

    class FakeRecognizer:
        def __init__(self, _model, _rate):
            self.index = 0
            self.results = iter(finished)

        def SetWords(self, enabled):
            assert enabled is True

        def AcceptWaveform(self, _data):
            self.index += 1
            return self.index <= len(finished)

        def Result(self):
            return json.dumps({"result": next(self.results)})

        def FinalResult(self):
            return json.dumps({"result": final})

    fake_vosk = types.ModuleType("vosk")
    fake_vosk.Model = lambda _path: object()
    fake_vosk.KaldiRecognizer = FakeRecognizer
    monkeypatch.setitem(sys.modules, "vosk", fake_vosk)
    monkeypatch.setattr("dhp.asr_vosk._convert_to_16k_mono_wav", lambda *_: str(wav_path))

    words = VoskASRProvider(str(tmp_path)).transcribe("unused.wav")

    assert [word["word"] for word in words] == expected
    assert words[0]["start"] == 0.0
    assert words[-1]["end"] == 1.0
    for source in [*finished, final]:
        for item in source:
            actual = next(word for word in words if word["word"] == item["word"])
            if "conf" in item:
                assert actual["conf"] == item["conf"]
            else:
                assert "conf" not in actual
