import pytest

from dhp.components import Component, filter_renderable
from dhp.pipeline import MAX_RETRIES, plan, quote_summary


def _script():
    return [
        {"id": "s1", "shot": "talking_head", "text": "hello"},
        {"id": "s2", "shot": "b_roll", "text": "world"},
    ]


def test_plan_gate_first_segment_and_cache_savings():
    quotes = [
        {"estimated_cost": 2.0, "cache_hit": False, "duration_sec": 6.0},
        {"estimated_cost": 3.0, "cache_hit": True, "duration_sec": 5.0},
    ]
    p = plan(_script(), quotes, budget=10.0, cache_keys=["k1", "k2"])
    assert p.segments[0].status == "gate"
    assert p.segments[1].status == "waiting_on_gate"
    assert p.total_cost == 2.0  # cached segment costs 0
    assert p.cache_savings == 3.0
    assert p.over_budget is False
    assert "gate=s1" in quote_summary(p)


def test_plan_over_budget_flagged():
    p = plan(_script(), [
        {"estimated_cost": 9.0, "cache_hit": False, "duration_sec": 6.0},
        {"estimated_cost": 9.0, "cache_hit": False, "duration_sec": 5.0},
    ], budget=10.0)
    assert p.over_budget is True


def test_retry_order_ends_at_human():
    p = plan(_script(), [
        {"estimated_cost": 1.0, "cache_hit": False, "duration_sec": 6.0},
        {"estimated_cost": 1.0, "cache_hit": False, "duration_sec": 5.0},
    ])
    seg = p.segments[0]
    assert seg.next_retry_step() == "same_model_new_prompt"
    seg.retries = 1
    assert seg.next_retry_step() == "different_model_same_kind"
    seg.retries = 2
    assert seg.next_retry_step() == "lower_resolution_or_duration"
    seg.retries = MAX_RETRIES
    assert seg.next_retry_step() == "stop_for_human"


def test_components_drop_missing_data_never_invent():
    ok, dropped = filter_renderable([
        {"use": "PriceTag", "at": "s1:不到十块钱", "props": {"value": 9.9}},
        {"use": "PriceTag", "at": "s1:不到十块钱", "props": {}},
        {"use": "NoSuchWidget", "at": "s1:x", "props": {}},
    ])
    assert len(ok) == 1 and ok[0].use == "PriceTag"
    assert len(dropped) == 2
    assert Component(use="FactCard", at="s1:x", props={"claim": "a"}).validate()


def test_benchmark_summary():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from benchmark import summarize
    out = summarize([
        {"verdict": "pass", "retries": 0, "cost": 2.0, "duration_sec": 60.0,
         "lipsync_score": 0.8, "face_cosine": 0.9},
        {"verdict": "pass", "retries": 1, "cost": 4.0, "duration_sec": 60.0,
         "lipsync_score": 0.7, "face_cosine": 0.85},
    ])
    assert out["segments"] == 2
    assert out["retry_rate"] == 0.5
    assert out["first_pass_rate"] == 0.5
    assert out["cost_per_minute"] == 3.0
