import os
import shutil
import subprocess
from pathlib import Path

import pytest

from dhp.live import LiveSession
from dhp.lipsync_local import check_environment
from dhp.qa_scorers import FaceEmbeddingProvider, char_accuracy, frame_hash_similarity


def test_char_accuracy_real_chinese_asr():
    # Script vs the Vosk transcription measured 2026-10-28 on s1.mp3
    # (only "AI" -> "哎" differs). Must stay above the 85% QA gate.
    acc = char_accuracy(
        "这是一次流水线验证，不是真人出镜，画面里是AI生成的虚拟主播。",
        "这是 一次 流水线 验证 不是 真人 出镜 画面 里 是 哎 生成 的 虚拟 主播")
    assert acc >= 0.85


def test_frame_hash_similarity_orders_correctly(tmp_path):
    from PIL import Image
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    c = tmp_path / "c.png"
    Image.new("RGB", (64, 64), (200, 30, 30)).save(a)
    Image.new("RGB", (64, 64), (200, 30, 30)).save(b)
    Image.new("RGB", (64, 64), (30, 30, 200)).save(c)
    assert frame_hash_similarity(str(a), str(b)) >= frame_hash_similarity(str(a), str(c))


def test_face_embedding_refuses_without_model():
    with pytest.raises(RuntimeError):
        FaceEmbeddingProvider().embed("face-crop.jpg")


def test_local_lipsync_environment_is_honest_about_this_vm():
    env = check_environment()
    # This VM has no GPU and no torch; a capable machine may differ,
    # so the test only asserts the report is structured and ffmpeg is found.
    assert "missing" in env and "ready" in env
    assert shutil.which("ffmpeg") is not None


def test_live_session_state_machine():
    s = LiveSession(persona_id="presenter-v1")
    s.transition("listening")
    s.transition("speaking")
    s.interrupt()
    assert s.state == "listening"
    assert s.interruptions == 1
    with pytest.raises(ValueError):
        s.transition("idle")  # listening -> idle is illegal


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_lipsync_heuristic_separates_synced_from_unsynced(tmp_path):
    from dhp.qa_scorers import lipsync_heuristic
    # Synthetic 3s clips built in v0.3 calibration: lower-region brightness
    # pulses in sync (or out of sync) with the audio envelope.
    import numpy as np
    from PIL import Image
    import wave
    import struct

    def build(video_path, synced):
        fps, dur = 10, 3.0
        frames = []
        for i in range(int(fps * dur)):
            t = i / fps
            env = 1.0 if int(t * 2) % 2 == 0 else 0.2
            if not synced:
                env = 1.0 if int(t * 2) % 2 == 1 else 0.2
            arr = np.full((90, 160, 3), 30, dtype=np.uint8)
            arr[60:80, 60:100] = int(30 + 180 * env)
            frames.append(Image.fromarray(arr))
        for i, im in enumerate(frames):
            im.save(tmp_path / f"f{i:03d}.png")
        sr = 16000
        samples = []
        for i in range(sr * 3):
            t = i / sr
            env = 1.0 if int(t * 2) % 2 == 0 else 0.2
            samples.append(int(8000 * env * np.sin(2 * np.pi * 440 * t)))
        wav = tmp_path / "a.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
            w.writeframes(b"".join(struct.pack("<h", s) for s in samples))
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-framerate", "10",
            "-i", str(tmp_path / "f%03d.png"), "-i", str(wav),
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", str(video_path),
        ], check=True)

    synced = tmp_path / "synced.mp4"
    unsynced = tmp_path / "unsynced.mp4"
    build(synced, True)
    build(unsynced, False)
    assert lipsync_heuristic(str(synced))["score"] > 0.9
    assert lipsync_heuristic(str(unsynced))["score"] < 0.3


def test_vosk_asr_on_real_chinese_clip():
    vosk = pytest.importorskip("vosk")
    model = os.environ.get("VOSK_MODEL_PATH", "/tmp/vosk-model-small-cn-0.22")
    if not Path(model).is_dir():
        pytest.skip("Vosk Chinese model not present")
    from dhp.asr_vosk import VoskASRProvider
    from dhp.qa_scorers import char_accuracy
    clip = Path(__file__).resolve().parents[1].parent / "digital-human-verify" / "s1.mp3"
    if not clip.is_file():
        pytest.skip("local Mandarin verification clip not present in this checkout")
    words = VoskASRProvider(model).transcribe(str(clip))
    # s1.mp3 lives in the verify project, not in this repo; if it is absent,
    # the test is about the adapter contract, not the file.
    text = "".join(w["word"] for w in words)
    assert char_accuracy(
        "这是一次流水线验证，不是真人出镜，画面里是AI生成的虚拟主播。", text) >= 0.85
