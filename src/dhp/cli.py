"""CLI skeleton. Phase 1: validate contracts, print the cost quote, stop.

This intentionally does NOT generate anything yet. The first milestone is:
contracts pass -> quote printed -> cache key printed. Generation adapters
plug in behind the provider interfaces in providers.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .cache import segment_cache_key


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="dhp")
    p.add_argument("script", help="script.json path")
    p.add_argument("--brief", default="examples/demo-brief.json")
    args = p.parse_args(argv)

    script = json.loads(Path(args.script).read_text(encoding="utf-8"))
    brief = json.loads(Path(args.brief).read_text(encoding="utf-8"))
    for seg in script:
        if seg["shot"] not in ("talking_head", "b_roll", "demo", "scene"):
            print(f"invalid shot: {seg}", file=sys.stderr)
            return 2
        key = segment_cache_key(seg, brief["persona_id"], "TBD", "TBD", {}, "TBD")
        print(f"{seg['id']}: shot={seg['shot']} cache_key={key[:16]}... (provider TBD)")
    print("contracts OK. Next step: implement one TTSProvider + one LipSyncProvider.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
