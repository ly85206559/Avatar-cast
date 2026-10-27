#!/usr/bin/env python3
"""API lip-sync: the one command that actually spends money.

Nothing in this script spends anything unless ALL of these are true:
- WAVESPEED_API_KEY is set in the environment (never in chat, never in a file)
- --image-url and --audio-url are public URLs for the locked presenter
  image and locked audio (the API takes URLs, not local files)
- --rate-per-sec is the live price beside Generate for THIS input
- --confirm is passed (a deliberate, separate flag -- not a default)

Without --confirm, the script only runs dry_run and prints the quote.
With --confirm, it submits exactly once (the adapter never retries a
submit) and writes a manifest JSON with the output path and quote.

Usage:
    python scripts/api_lipsync_run.py --image-url https://.../presenter.jpg \\
        --audio-url https://.../s1.mp3 --audio-duration-sec 6.0 \\
        --audio-sha256 <sha256 of the audio file> \\
        --rate-per-sec 0.25 --output clips/s1.mp4
    # then, only after re-checking the live price:
    python scripts/api_lipsync_run.py ... --confirm
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dhp.lipsync_api import ApiLipSyncConfig, ApiLipSyncProvider  # noqa: E402
from dhp.providers import Audio  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="api_lipsync_run")
    p.add_argument("--image-url", required=True)
    p.add_argument("--audio-url", required=True)
    p.add_argument("--audio-duration-sec", type=float, required=True)
    p.add_argument("--audio-sha256", required=True)
    p.add_argument("--rate-per-sec", type=float, required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--confirm", action="store_true",
                   help="Actually submit (spends money). Omit for dry-run only.")
    args = p.parse_args(argv)

    provider = ApiLipSyncProvider(ApiLipSyncConfig(rate_per_sec=args.rate_per_sec))
    audio = Audio(path=args.audio_url, duration_sec=args.audio_duration_sec,
                  sha256=args.audio_sha256, voice_id="locked")
    manifest = provider.dry_run(args.image_url, audio)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
    if not args.confirm:
        print("DRY RUN ONLY: nothing submitted, nothing spent. "
              "Re-check the live Generate price, then re-run with --confirm.")
        return 0
    clip = provider.drive(args.image_url, audio, args.output, confirm_live_price=True)
    print(json.dumps({"output": clip.path, "model": clip.model,
                      "duration_sec": clip.duration_sec, "cost": clip.cost},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
