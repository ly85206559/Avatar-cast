"""Local lip-sync: environment check + explicit extension point.

v0.3 verdict, measured on this VM (2 CPU cores, 7.7 GB RAM, no GPU,
~0.4 GB free at check time): a local audio-driven model is NOT viable
here. MuseTalk / SadTalker / Hallo-class models need torch + model
weights + a GPU (or a large CPU + RAM budget this machine does not
have), and the original OmniHuman-1 weights' public availability is
still unconfirmed. Implementing a "talking head" out of a generic
video generator would be fake lip-sync -- the exact failure AvatarCast
exists to avoid -- so this module does NOT do that.

What it does do: ``check_environment()`` reports, in plain terms,
exactly which pieces are missing, so a capable machine can tell in
one call whether the local route can run. ``drive()`` still refuses
until a real model adapter is registered.
"""

from __future__ import annotations

import shutil
import sys


def check_environment() -> dict:
    """Return {ready: bool, missing: [str], notes: [str]} -- no side effects."""
    missing: list[str] = []
    try:
        import torch  # noqa: F401
    except ImportError:
        missing.append("torch (pip install torch, CPU build at minimum)")
    if shutil.which("nvidia-smi") is None:
        missing.append("GPU (nvidia-smi not found; CPU-only local lip-sync is not recommended)")
    if shutil.which("ffmpeg") is None:
        missing.append("ffmpeg")
    notes = [
        "Local lip-sync needs a real audio-driven model (MuseTalk / SadTalker / Hallo-class),",
        "its weights, and a licence check first. Weights are NOT bundled here.",
        "Judge any local route on the same Mandarin test audio as the API route,",
        "not on English demos, and on the same five QA dimensions.",
    ]
    return {"ready": not missing, "missing": missing, "notes": notes}


class LocalLipSyncProvider:
    def drive(self, *args, **kwargs):
        env = check_environment()
        raise NotImplementedError(
            "Local lip-sync is not implemented. Environment check: "
            f"missing={env['missing']}. "
            "Pick a model, check its licence and VRAM, implement drive() "
            "behind the LipSyncProvider interface, and register it in "
            "registry.py as 'local'. Until then, use the default "
            "'wavespeed-api' route (see docs/API_LIPSYNC.md).")
