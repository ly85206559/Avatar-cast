"""Pipeline planning: quote gate, retry policy, per-segment tasks.

This module does no generation and no network calls. It turns a validated
script + a per-segment quote into a plan a human (or a policy) can approve
before any money is spent, and it encodes the retry order so a failed
segment never retries forever or silently.

Quote gate (v0.2 rules):
- A plan always prints: segment count, total seconds, estimated total,
  cache savings (segments that would hit cache cost 0).
- The first segment is a gate: it must pass QA before the rest are
  batched. ``plan()`` therefore marks segment 0 as ``gate`` and the
  rest as ``waiting_on_gate``.
- A plan whose estimated total exceeds ``budget`` is marked
  ``over_budget`` and must not run without an explicit override.

Retry order (fixed, not configurable per segment):
1. same model, new prompt
2. same kind of model, different model
3. lower resolution / shorter duration
4. stop, record in qa.json, hand to a human
"""

from __future__ import annotations

from dataclasses import dataclass, field

RETRY_ORDER = (
    "same_model_new_prompt",
    "different_model_same_kind",
    "lower_resolution_or_duration",
    "stop_for_human",
)

MAX_RETRIES = 3


@dataclass
class SegmentPlan:
    segment_id: str
    shot: str
    duration_sec: float
    estimated_cost: float
    cache_hit: bool
    cache_key: str
    status: str = "waiting_on_gate"  # gate | waiting_on_gate | approved
    retries: int = 0
    retry_reasons: list[str] = field(default_factory=list)

    def next_retry_step(self) -> str:
        """What to do on the next failure, given how many retries happened."""
        if self.retries >= MAX_RETRIES:
            return "stop_for_human"
        return RETRY_ORDER[self.retries]


@dataclass
class Plan:
    segments: list[SegmentPlan]
    total_cost: float
    cache_savings: float
    over_budget: bool

    @property
    def total_seconds(self) -> float:
        return round(sum(s.duration_sec for s in self.segments), 3)


def plan(script: list[dict], quotes: list[dict], budget: float | None = None,
         cache_keys: list[str] | None = None) -> Plan:
    """Build a plan from a script and per-segment quote dicts.

    Each quote dict: {"estimated_cost": float, "cache_hit": bool,
    "duration_sec": float}. ``cache_keys`` is parallel to ``script``;
    missing entries fall back to ``<segment_id>`` (a placeholder that
    can never collide with a real cache key in production, where keys
    are sha256 hex from cache.py).
    """
    if len(script) != len(quotes):
        raise ValueError("script and quotes must have the same length")
    keys = cache_keys or [seg["id"] for seg in script]
    segments: list[SegmentPlan] = []
    total = 0.0
    savings = 0.0
    for i, (seg, quote) in enumerate(zip(script, quotes)):
        cost = float(quote.get("estimated_cost", 0.0))
        hit = bool(quote.get("cache_hit", False))
        if hit:
            savings += cost
            cost = 0.0
        segments.append(SegmentPlan(
            segment_id=seg["id"],
            shot=seg["shot"],
            duration_sec=float(quote.get("duration_sec", 0.0)),
            estimated_cost=round(cost, 2),
            cache_hit=hit,
            cache_key=keys[i],
            status="gate" if i == 0 else "waiting_on_gate",
        ))
        total += cost
    total = round(total, 2)
    return Plan(
        segments=segments,
        total_cost=total,
        cache_savings=round(savings, 2),
        over_budget=budget is not None and total > budget,
    )


def quote_summary(p: Plan) -> str:
    return (
        f"segments={len(p.segments)} seconds={p.total_seconds} "
        f"estimated_cost={p.total_cost} cache_savings={p.cache_savings} "
        f"over_budget={p.over_budget} gate={p.segments[0].segment_id if p.segments else '-'}"
    )
