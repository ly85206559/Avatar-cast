"""Real ASR adapter: Vosk (offline, CPU-friendly, Chinese small model).

Verified on this machine 2026-10-28 with vosk-model-small-cn-0.22
(42 MB) on a Mandarin clip: transcription was 15/16 tokens correct
("AI" heard as "哎"), with word-level start/end times -- exactly what
tl.json needs. That run is the evidence; the model is NOT bundled in
this repo. Install it yourself:

    pip install vosk
    # download vosk-model-small-cn-0.22.zip from alphacephei.com/vosk/models
    # unzip it, then set VOSK_MODEL_PATH to the model directory

If the model is missing, this adapter raises a plain error instead of
returning a fake transcript. Never use an English model to judge Mandarin.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import wave
from pathlib import Path


def _convert_to_16k_mono_wav(audio_path: str, out_path: str) -> str:
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", audio_path,
        "-ar", "16000", "-ac", "1", out_path,
    ], check=True)
    return out_path


class VoskASRProvider:
    def __init__(self, model_path: str | None = None):
        self.model_path = model_path or os.environ.get("VOSK_MODEL_PATH", "")
        if not self.model_path or not Path(self.model_path).is_dir():
            raise RuntimeError(
                "Vosk model not found. Set VOSK_MODEL_PATH to a downloaded "
                "vosk-model-small-cn-0.22 directory (see module docstring).")

    def transcribe(self, audio_path: str) -> list[dict]:
        """Return [{"word": str, "start": float, "end": float}, ...]."""
        try:
            from vosk import KaldiRecognizer, Model
        except ImportError as e:
            raise RuntimeError("vosk is not installed: pip install vosk") from e
        with tempfile.TemporaryDirectory() as td:
            wav = _convert_to_16k_mono_wav(audio_path, str(Path(td) / "in.wav"))
            wf = wave.open(wav)
            rec = KaldiRecognizer(Model(self.model_path), wf.getframerate())
            rec.SetWords(True)
            while True:
                data = wf.readframes(4000)
                if not data:
                    break
                rec.AcceptWaveform(data)
            result = json.loads(rec.FinalResult())
        return [{"word": w["word"], "start": float(w["start"]), "end": float(w["end"])}
                for w in result.get("result", [])]

    def text(self, audio_path: str) -> str:
        return "".join(w["word"] for w in self.transcribe(audio_path))
