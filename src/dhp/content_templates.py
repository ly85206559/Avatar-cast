"""Small, packaged content recipes shared by the CLI and the assistant Skill."""

from __future__ import annotations

import json
import re
from importlib.resources import files


IDS = ("product-intro", "knowledge-share", "empathy")


def get(template_id: str) -> dict:
    if template_id not in IDS:
        raise ValueError("Unknown template; use 'dhp make templates' to list available templates.")
    return json.loads(files("dhp").joinpath("template_data", template_id + ".json").read_text(encoding="utf-8"))


def select(request: str) -> str | None:
    if re.search(r"推荐|产品|商品|种草|带货|广告|促销|推广|卖点|product|sell", request, re.I):
        return "product-intro"
    if re.search(r"安慰|陪伴|情感|共鸣|鼓励|empathy", request, re.I):
        return "empathy"
    if re.search(r"分享|讲解|科普|教程|知识|解释|教学|方法|步骤|explain|tutorial", request, re.I):
        return "knowledge-share"
    return None


def resolve(template_id: str | None, request: str = "") -> dict | None:
    if template_id == "auto":
        template_id = select(request)
    if template_id is None:
        return None
    item = get(template_id)
    return {"id": item["id"], "version": item["version"]}


def validate(selection: dict) -> dict:
    if (not isinstance(selection, dict) or set(selection) != {"id", "version"}
            or type(selection.get("version")) is not int
            or selection != resolve(selection.get("id"))):
        raise ValueError("The template selection is invalid or its version is unsupported.")
    return selection


def narration(brief: dict, selection: dict | None) -> str:
    """Join assistant-written narrative slots; never invent facts or call a model."""
    if "beats" not in brief:
        return brief.get("script", "")
    if selection is None:
        raise ValueError("A brief with beats must select a template.")
    roles = [item["key"] for item in get(selection["id"])["structure"]]
    beats = brief["beats"]
    if (not isinstance(beats, dict) or set(beats) != set(roles)
            or any(not isinstance(beats[k], str) or not beats[k].strip() for k in roles)):
        raise ValueError("Template beats must fill exactly these slots: " + ", ".join(roles))
    chunks = [beats[k].strip() for k in roles]
    script = "".join(s if s[-1] in "，。！？!?；;," else s + "。" for s in chunks)
    if "script" in brief and brief["script"] != script:
        raise ValueError("Brief script differs from its template beats; review one consistent narration.")
    return script


def recipe(selection: dict, title: str, cues: list[dict], duration: float, matched: bool) -> dict:
    """Bind cards to observed clauses, preserving the conservative ASR fallback."""
    item = get(validate(selection)["id"])
    intro_end = min(duration, cues[1]["start"] if len(cues) > 1 else 1.6)
    cards = [{"use": "TextCard", "at": 0, "until": max(min(0.1, duration), intro_end),
              "title": title if 0 < len(title) <= 16 else item["label"]}]
    if not matched:
        return {"timing": "estimated", "components": cards}
    units = [c for c in cues if c["start"] >= intro_end and c["end"] - c["start"] >= 1
             and 2 <= len(c["text"]) <= 18]
    if selection["id"] == "product-intro":
        for cue in units[:2]:
            cards.append({"use": "KeywordEmphasis", "at": cue["start"], "until": cue["end"],
                          "text": cue["text"].rstrip("，。！？!?；;,")})
        if units:
            cards.append({"use": "HostReframe", "at": units[0]["start"], "until": units[0]["end"], "scale": 1.06})
    elif selection["id"] == "knowledge-share" and len(units) >= 2:
        steps = units[:4]
        cards.append({"use": "StepProgress", "at": steps[0]["start"], "until": steps[-1]["end"],
                      "steps": [c["text"].rstrip("，。！？!?；;,") for c in steps],
                      "step_times": [c["start"] for c in steps]})
    elif units:
        cue = units[-1]
        cards.append({"use": "KeywordEmphasis", "at": cue["start"], "until": cue["end"],
                      "text": cue["text"].rstrip("，。！？!?；;,")})
    return {"timing": "asr_matched", "components": cards}
