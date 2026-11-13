"""Local CPU Whisper transcription. Model downloads are a separate setup step."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import wave

import numpy as np

from .asr_vosk import _convert_to_16k_mono_wav


class WhisperASRProvider:
    def __init__(self, model_path: str | None = None):
        self.model_path = model_path or os.environ.get("WHISPER_MODEL_PATH", "")
        if not self.model_path or not Path(self.model_path).is_dir():
            raise RuntimeError("Set WHISPER_MODEL_PATH to a local faster-whisper model directory.")

    def transcribe(self, audio_path: str) -> list[dict]:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("Install the local Whisper extra: pip install '.[whisper]'") from exc
        try:
            with tempfile.TemporaryDirectory() as directory:
                wav = _convert_to_16k_mono_wav(audio_path, str(Path(directory) / "audio.wav"))
                with wave.open(wav, "rb") as source:
                    audio = np.frombuffer(source.readframes(source.getnframes()), dtype=np.int16).astype(np.float32) / 32768
            model = WhisperModel(self.model_path, device="cpu", compute_type="int8",
                                 cpu_threads=min(8, os.cpu_count() or 1), local_files_only=True)
            segments, _ = model.transcribe(audio, language="zh", word_timestamps=True,
                                            condition_on_previous_text=False, beam_size=5,
                                            initial_prompt="以下是简体中文的普通话。")
            return [{"word": word.word.strip(), "start": word.start, "end": word.end,
                     "conf": word.probability}
                    for segment in segments for word in (segment.words or []) if word.word.strip()]
        except (RuntimeError, ValueError, OSError) as exc:
            raise RuntimeError("Local Whisper transcription failed; check the model directory and audio.") from exc
