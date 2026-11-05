"""Small, packaged content recipes shared by the CLI and the assistant Skill."""

from __future__ import annotations

import json
import re
from importlib.resources import files


IDS = ("three-point", "product-demo", "product-intro", "knowledge-share", "empathy")


def get(template_id: str) -> dict:
    if template_id not in IDS:
        raise ValueError("Unknown template; use 'dhp make templates' to list available templates.")
    return json.loads(files("dhp").joinpath("template_data", template_id + ".json").read_text(encoding="utf-8"))


def select(request: str) -> str | None:
    if re.search(r"演示种草|素材展示|产品演示|商品演示|展示.{0,8}(产品|商品|截图|录屏)|product.demo", request, re.I):
        return "product-demo"
    if re.search(r"推荐|产品|商品|种草|带货|广告|促销|推广|卖点|product|sell", request, re.I):
        return "product-intro"
    if re.search(r"安慰|陪伴|情感|共鸣|鼓励|empathy", request, re.I):
        return "empathy"
    if re.search(r"三[个点种条招项]|3[个点种条招项]|三点干货|three.point", request, re.I):
        return "three-point"
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
    if selection["id"] == "three-point":
        points = [beats[k].strip().rstrip("，。！？!?；;,") for k in ("point_1", "point_2", "point_3")]
        if any(not p or len(p) > 18 for p in points):
            raise ValueError("Each of the three points must fit in 18 characters.")
    script = "".join(s if s[-1] in "，。！？!?；;," else s + "。" for s in chunks)
    if "script" in brief and brief["script"] != script:
        raise ValueError("Brief script differs from its template beats; review one consistent narration.")
    return script


def _beat_cues(beats: dict, cues: list[dict], duration: float, matched: bool, allow_estimate: bool,
               keys: tuple[str, ...] = ("hook", "point_1", "point_2", "point_3", "closing")) -> list[dict]:
    """Locate written beats, without treating estimates as ASR matches."""
    texts = [beats[k].strip() for k in keys]
    if not matched:
        if not allow_estimate:
            return []
        weights = [len(s) + (s[-1] not in "，。！？!?；;,") for s in texts]
        total, elapsed, result = sum(weights), 0, []
        for text, weight in zip(texts, weights):
            start = duration * elapsed / total
            elapsed += weight
            result.append({"text": text, "start": start, "end": duration * elapsed / total})
        return result
    compact = lambda text: "".join(c for c in text.casefold() if c.isalnum())
    result, index = [], 0
    for text in texts:
        expected, found, selected = compact(text), "", []
        while index < len(cues) and len(found) < len(expected):
            selected.append(cues[index])
            found += compact(cues[index]["text"])
            index += 1
        if not selected or found != expected:
            return []
        result.append({"text": text, "start": selected[0]["start"], "end": selected[-1]["end"]})
    return result if index == len(cues) else []


def recipe(selection: dict, title: str, cues: list[dict], duration: float, matched: bool,
           *, beats: dict | None = None, allow_estimate: bool = True, has_asset: bool = False) -> dict:
    """Bind cards to observed clauses, preserving the conservative ASR fallback."""
    item = get(validate(selection)["id"])
    intro_end = min(duration, cues[1]["start"] if len(cues) > 1 else 1.6)
    cards = [{"use": "TextCard", "at": 0, "until": max(min(0.1, duration), intro_end),
              "title": title if 0 < len(title) <= 16 else item["label"]}]
    if selection["id"] == "product-demo":
        if beats:
            narration({"beats": beats}, selection)
            roles = _beat_cues(beats, cues, duration, matched, allow_estimate,
                               keys=("hook", "problem", "demo", "fit"))
            if roles:
                cards[0]["until"] = max(min(0.1, duration), roles[1]["start"])
                for role in ([roles[3]] if has_asset else [roles[2], roles[3]]):
                    value = role["text"].rstrip("，。！？!?；;,")
                    if 2 <= len(value) <= 24 and role["end"] - role["start"] >= 0.5:
                        cards.append({"use": "KeywordEmphasis", "at": role["start"],
                                      "until": role["end"], "text": value})
        return {"timing": "asr_matched" if matched else "estimated", "components": cards}
    if selection["id"] == "three-point" and not beats:
        return {"timing": "asr_matched" if matched else "estimated", "components": cards}
    if selection["id"] == "three-point":
        # Validate the same role values used to create and review the plan.
        narration({"beats": beats}, selection)
        roles = _beat_cues(beats, cues, duration, matched, allow_estimate)
        if roles:
            points, closing = roles[1:4], roles[4]
            steps = [c["text"].rstrip("，。！？!?；;,") for c in points]
            times = [c["start"] for c in points]
            if (times == sorted(set(times)) and points[-1]["end"] > times[-1]
                    and all(0 < len(s) <= 18 for s in steps)):
                cards[0]["until"] = max(min(0.1, duration), points[0]["start"])
                for index, (point, step) in enumerate(zip(points, steps), 1):
                    cards.append({"use": "KeywordEmphasis", "at": point["start"], "until": point["end"],
                                  "text": f"{index:02}  {step}"})
                if points[1]["end"] - points[1]["start"] >= 0.5:
                    cards.append({"use": "HostReframe", "at": points[1]["start"],
                                  "until": points[1]["end"], "scale": 1.04})
                end_text = closing["text"].rstrip("，。！？!?；;,")
                if 2 <= len(end_text) <= 24 and closing["end"] - closing["start"] >= 0.5:
                    cards.append({"use": "KeywordEmphasis", "at": closing["start"],
                                  "until": closing["end"], "text": end_text})
        return {"timing": "asr_matched" if matched else "estimated", "components": cards}
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
