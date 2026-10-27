"""CLI v0.2: validate contracts, print cache keys, and build a plan.

Generation itself lives behind the provider interfaces in providers.py
(API lip-sync in lipsync_api.py, local as an explicit extension point).
Planning lives in pipeline.py, overlay components in components.py,
media assembly in render.py, and benchmark comparison in
scripts/benchmark.py.
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
    print("contracts OK. See pipeline.plan() for the quote gate, "
          "components.filter_renderable() for overlays, and render.py for assembly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
