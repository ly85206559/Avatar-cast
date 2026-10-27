#!/usr/bin/env python3
"""Benchmark: compare QA reports on the same fixed test set.

Usage:
    python scripts/benchmark.py qa-run-1.json qa-run-2.json ...

Each qa file is a JSON list of per-segment records, each with at least:
verdict ("pass"/"fail"/"warn"), cost, retries, lipsync_score, face_cosine.

Output is the four numbers AvatarCast judges an optimisation by:
- retry rate (lower is better)
- mean lipsync / face scores (higher is better)
- cost per minute (lower is better)
- first-pass rate: segments that passed with 0 retries (higher is better)

A single number improving on its own is not an optimisation; all four
must be read together.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def summarize(records: list[dict]) -> dict:
    n = len(records)
    if n == 0:
        return {"segments": 0}
    retries = sum(r.get("retries", 0) for r in records)
    retried_segments = sum(1 for r in records if r.get("retries", 0) > 0)
    first_pass = sum(1 for r in records
                     if r.get("verdict") == "pass" and r.get("retries", 0) == 0)
    lipsync = [r["lipsync_score"] for r in records if r.get("lipsync_score") is not None]
    face = [r["face_cosine"] for r in records if r.get("face_cosine") is not None]
    total_cost = sum(r.get("cost", 0.0) for r in records)
    total_min = sum(r.get("duration_sec", 0.0) for r in records) / 60.0
    return {
        "segments": n,
        "retry_rate": round(retried_segments / n, 3),
        "mean_retries": round(retries / n, 3),
        "mean_lipsync": round(sum(lipsync) / len(lipsync), 3) if lipsync else None,
        "mean_face_cosine": round(sum(face) / len(face), 3) if face else None,
        "cost_per_minute": round(total_cost / total_min, 2) if total_min else None,
        "first_pass_rate": round(first_pass / n, 3),
        "total_cost": round(total_cost, 2),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="benchmark")
    p.add_argument("qa_files", nargs="+", help="qa.json files to compare")
    args = p.parse_args(argv)
    for f in args.qa_files:
        records = json.loads(Path(f).read_text(encoding="utf-8"))
        print(f"{f}: {json.dumps(summarize(records), ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
