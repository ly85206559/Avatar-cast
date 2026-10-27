"""QA scorers that actually run on CPU with only numpy + Pillow + ffmpeg.

Read the labels carefully -- AvatarCast does not relabel a proxy as
the real thing:

- ``char_accuracy``: character-level accuracy of an ASR transcript
  against the script. Real, measured on Vosk output in v0.3.
- ``frame_hash_similarity``: average-hash similarity between two
  frames. A *proxy* for cross-segment visual consistency. It is NOT
  a face embedding: it cannot tell "same person" from "same background".
- ``lipsync_heuristic``: Pearson correlation between lower-face-region
  brightness level (mouth-openness proxy) and the audio RMS envelope,
  best over a small lag window.
  A *heuristic*, NOT SyncNet. SyncNet (a trained audio-visual model)
  needs torch + weights + GPU/CPU time this VM does not have; see
  docs/QA_BENCHMARK.md for the exact gap. A high heuristic score is
  evidence of motion-audio alignment, not a SyncNet score.
- ``FaceEmbeddingProvider``: interface for a real embedding model.
  It loads an ONNX ArcFace-style model ONLY if the caller supplies
  onnxruntime + a model file + already-cropped face images. With
  none of those present it raises instead of inventing a vector.
"""

from __future__ import annotations

import difflib
import math
import re
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np
from PIL import Image


def _clean(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]", "", text)


def char_accuracy(script_text: str, asr_text: str) -> float:
    """Character accuracy (0..1) between script and transcript."""
    a, b = _clean(script_text), _clean(asr_text)
    if not a:
        return 0.0
    return round(difflib.SequenceMatcher(None, a, b).ratio(), 4)


def average_hash(image_path: str) -> int:
    img = Image.open(image_path).convert("L").resize((8, 8))
    px = np.asarray(img, dtype=float)
    bits = (px > px.mean()).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def frame_hash_similarity(path_a: str, path_b: str) -> float:
    """0..1 similarity of two frames by average hash (proxy, not face)."""
    ha, hb = average_hash(path_a), average_hash(path_b)
    distance = bin(ha ^ hb).count("1")
    return round(1.0 - distance / 64.0, 4)


def _extract_frames(video_path: str, fps: int, out_dir: Path) -> list[Path]:
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", video_path,
        "-vf", f"fps={fps}", str(out_dir / "frame-%04d.png"),
    ], check=True)
    return sorted(out_dir.glob("frame-*.png"))


def _audio_envelope(audio_path: str, fps: int, n_frames: int) -> list[float]:
    with tempfile.TemporaryDirectory() as td:
        wav = str(Path(td) / "a.wav")
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-i", audio_path,
            "-ar", "16000", "-ac", "1", wav,
        ], check=True)
        with wave.open(wav) as wf:
            raw = wf.readframes(wf.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16).astype(float) / 32768.0
    per_frame = max(1, len(samples) // max(1, n_frames))
    envelope = []
    for i in range(n_frames):
        chunk = samples[i * per_frame:(i + 1) * per_frame]
        envelope.append(float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) else 0.0)
    return envelope


def _mouth_level_series(frame_paths: list[Path]) -> list[float]:
    """Mean brightness of the lower-centre region (mouth-openness proxy).

    This is a level, not a frame difference: an open mouth stays bright
    while sound continues, so the level -- not the change -- tracks the
    audio envelope. A change-based series correlates with nothing but
    transitions and was rejected during v0.3 calibration.
    """
    levels: list[float] = []
    for p in frame_paths:
        img = np.asarray(Image.open(p).convert("L"), dtype=float)
        h, w = img.shape
        region = img[int(h * 0.6):int(h * 0.9), int(w * 0.35):int(w * 0.65)]
        levels.append(float(np.mean(region)))
    return levels


def _pearson(a: list[float], b: list[float]) -> float:
    if len(a) < 3 or len(b) < 3:
        return 0.0
    x, y = np.asarray(a, float), np.asarray(b, float)
    if x.std() == 0 or y.std() == 0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def lipsync_heuristic(video_path: str, fps: int = 10) -> dict:
    """Best-lag correlation between mouth-region motion and audio RMS.

    Returns {"score": float, "best_lag_frames": int, "note": str}.
    This is a heuristic, NOT a SyncNet score -- see module docstring.
    """
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "frames"
        out_dir.mkdir()
        frames = _extract_frames(video_path, fps, out_dir)
        if len(frames) < 3:
            return {"score": 0.0, "best_lag_frames": 0,
                    "note": "too few frames for a heuristic score"}
        motion = _mouth_level_series(frames)
        envelope = _audio_envelope(video_path, fps, len(frames))
    best_score, best_lag = -1.0, 0
    for lag in (-2, -1, 0, 1, 2):
        if lag >= 0:
            m, e = motion[lag:], envelope[:len(motion) - lag] if lag else envelope
        else:
            m, e = motion[:lag], envelope[-lag:]
        n = min(len(m), len(e))
        score = _pearson(m[:n], e[:n])
        if score > best_score:
            best_score, best_lag = score, lag
    return {"score": round(best_score, 4), "best_lag_frames": best_lag,
            "note": "heuristic (mouth-level / audio-envelope correlation), NOT SyncNet"}


class FaceEmbeddingProvider:
    """Real embedding, only when onnxruntime + model + face crops exist.

    Usage on a capable machine:
        provider = FaceEmbeddingProvider(model_path="arcface.onnx")
        v1 = provider.embed("face-crop-s1.jpg")
        v2 = provider.embed("face-crop-s2.jpg")
        cosine = provider.cosine(v1, v2)

    The model file is NOT bundled, and no vector is ever fabricated.
    Without onnxruntime or a model file, embed() raises with the
    exact missing piece. Face detection/cropping is the caller's job;
    feeding a whole frame in as a "face" would produce a meaningless
    vector, so this class deliberately takes crops, not frames.
    """

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        if model_path and not Path(model_path).is_file():
            raise RuntimeError(f"Face embedding model not found: {model_path}")

    def embed(self, face_crop_path: str) -> list[float]:
        if not self.model_path:
            raise RuntimeError(
                "No face embedding model configured. Supply an ONNX "
                "ArcFace-style model path; this VM has neither onnxruntime "
                "nor GPU, so embedding is untested here (see docs/QA_BENCHMARK.md).")
        try:
            import onnxruntime as ort
        except ImportError as e:
            raise RuntimeError(
                "onnxruntime is not installed: pip install onnxruntime") from e
        img = Image.open(face_crop_path).convert("RGB").resize((112, 112))
        arr = (np.asarray(img, dtype=np.float32) / 255.0 - 0.5) / 0.5
        arr = np.transpose(arr, (2, 0, 1))[None, :]
        session = ort.InferenceSession(self.model_path,
                                       providers=["CPUExecutionProvider"])
        out = session.run(None, {session.get_inputs()[0].name: arr})[0][0]
        norm = float(np.linalg.norm(out))
        return (out / norm).tolist() if norm else out.tolist()

    @staticmethod
    def cosine(a: list[float], b: list[float]) -> float:
        x, y = np.asarray(a, float), np.asarray(b, float)
        denom = float(np.linalg.norm(x) * np.linalg.norm(y))
        return round(float(np.dot(x, y) / denom), 4) if denom else 0.0
