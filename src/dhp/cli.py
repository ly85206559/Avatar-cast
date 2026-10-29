"""CLI: validate contracts, print cache keys, and build a plan.

`dhp demo` runs the offline demo loop (demo.py): synthetic clips only,
zero cost, lip-sync explicitly not evaluated.

Generation itself lives behind the provider interfaces in providers.py
(API lip-sync in lipsync_api.py, local as an explicit extension point).
Planning lives in pipeline.py, overlay components in components.py,
media assembly in render.py, and benchmark comparison in
scripts/benchmark.py.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .cache import segment_cache_key


def main(argv: list[str] | None = None) -> int:
    # Console-script entry points call main() with no argv; argparse then
    # reads sys.argv itself. The demo branch must look at the same source.
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if args_list and args_list[0] == "demo":
        # `dhp demo` is the offline, zero-cost loop in demo.py. It never
        # generates a talking head and never spends money; see demo.py.
        from .demo import main as demo_main

        return demo_main(args_list[1:])
    p = argparse.ArgumentParser(prog="dhp")
    p.add_argument("script", help="script.json path")
    p.add_argument("--brief", default="examples/demo-brief.json")
    p.add_argument("--dry-run", action="store_true", help="run an offline synthetic-media pipeline")
    p.add_argument("--output-dir", default="dry-run-output")
    p.add_argument("--cache-dir", default=".dry-run-cache")
    args = p.parse_args(argv)

    script = json.loads(Path(args.script).read_text(encoding="utf-8"))
    brief = json.loads(Path(args.brief).read_text(encoding="utf-8"))
    if args.dry_run:
        from .dry_run import DryRunError, run_dry_run

        try:
            report = run_dry_run(script, brief, args.output_dir, args.cache_dir)
        except (DryRunError, ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
            print(f"dry-run failed: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
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
