"""Eight local presentation components, using seconds on the original cut."""

from __future__ import annotations

import copy
import math
import textwrap


COMPONENTS = {
    "TextCard": ("title",),
    "KeywordEmphasis": ("text",),
    "MetricCard": ("value", "unit", "label", "source"),
    "EvidenceFocus": ("claim", "evidence", "source"),
    "ComparePanel": ("dimension", "left", "right"),
    "StepProgress": ("steps", "step_times"),
    "HostReframe": ("scale",),
    "RecapBoard": ("title", "items"),
}


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _text(value: object, limit: int = 160) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit


def validate(pack: dict, duration: float | None = None) -> dict:
    """Reject missing evidence and unusable timing before rendering."""
    if (not isinstance(pack, dict) or set(pack) != {"timing", "components"}
            or pack["timing"] not in ("estimated", "manual_reviewed")
            or not isinstance(pack["components"], list)):
        raise ValueError("Pack needs timing (estimated/manual_reviewed) and a components list.")
    for item in pack["components"]:
        if (not isinstance(item, dict) or not isinstance(item.get("use"), str)
                or item["use"] not in COMPONENTS):
            raise ValueError("Unknown packaging component.")
        use = item["use"]
        start, end = item.get("at"), item.get("until")
        if not _number(start) or not _number(end) or not 0 <= start < end:
            raise ValueError(f"{use} needs finite seconds: 0 <= at < until.")
        if duration is not None and end > duration + 0.05:
            raise ValueError(f"{use} extends beyond the original cut ({duration:.2f}s).")
        if any(key not in item for key in COMPONENTS[use]):
            raise ValueError(f"{use} needs {', '.join(COMPONENTS[use])}.")
        allowed = {"use", "at", "until", *COMPONENTS[use]}
        if use == "TextCard":
            allowed.add("body")
        if set(item) - allowed:
            raise ValueError(f"{use} has unsupported fields: {', '.join(sorted(set(item) - allowed))}.")
        if use == "HostReframe":
            if not _number(item["scale"]) or not 1 <= item["scale"] <= 1.35:
                raise ValueError("HostReframe scale must be between 1 and 1.35.")
        elif use == "ComparePanel":
            if not _text(item["dimension"], 20):
                raise ValueError("ComparePanel needs a short comparison dimension.")
            for side in ("left", "right"):
                if (not isinstance(item[side], dict) or not _text(item[side].get("title"), 12)
                        or not _text(item[side].get("text"), 48)):
                    raise ValueError("ComparePanel needs title and text for both sides.")
        elif use in ("StepProgress", "RecapBoard"):
            values = item["steps" if use == "StepProgress" else "items"]
            if not isinstance(values, list) or not 2 <= len(values) <= 4 or not all(_text(x, 18) for x in values):
                raise ValueError(f"{use} needs two to four short items.")
            if use == "StepProgress":
                times = item["step_times"]
                if (not isinstance(times, list) or len(times) != len(values)
                        or not all(_number(t) and start <= t < end for t in times)
                        or times != sorted(set(times)) or times[0] != start):
                    raise ValueError("StepProgress needs increasing step_times, beginning at at.")
            elif not _text(item["title"], 18):
                raise ValueError("RecapBoard needs a short title.")
        elif any(not _text(item[key], 84 if key == "evidence" else 48) for key in COMPONENTS[use]):
            raise ValueError(f"{use} needs non-empty text with readable lengths.")
        if use == "TextCard" and (len(item["title"]) > 16 or not isinstance(item.get("body", ""), str)
                                   or len(item.get("body", "")) > 80):
            raise ValueError("TextCard title/body must fit a readable card.")
        if use == "KeywordEmphasis" and len(item["text"]) > 24:
            raise ValueError("KeywordEmphasis needs a short phrase of at most 24 characters.")
        if use == "MetricCard" and (len(item["value"] + " " + item["unit"]) > 12
                                    or len(item["label"]) > 40):
            raise ValueError("MetricCard value, unit and label must fit a readable card.")
        if use == "EvidenceFocus" and len(item["claim"]) > 18:
            raise ValueError("EvidenceFocus needs a short claim.")
    return copy.deepcopy(pack)


def _time(seconds: float) -> str:
    cs = round(seconds * 100)
    return f"{cs // 360000}:{(cs // 6000) % 60:02}:{(cs // 100) % 60:02}.{cs % 100:02}"


def _safe(text: str, width: int = 20) -> str:
    text = " ".join(text.split()).translate(str.maketrans({"\\": "＼", "{": "｛", "}": "｝"}))
    return r"\N".join(textwrap.wrap(text, width=width, break_long_words=True, break_on_hyphens=False))


def ass_events(pack: dict, duration: float, accent: str, *, warm: bool = False) -> str:
    """Independent ASS events on a 720x1280 canvas, leaving the face clear."""
    pack = validate(pack, duration)
    events = []

    def event(item, contents, layer=3, start=None, end=None):
        a = item["at"] if start is None else start
        b = item["until"] if end is None else end
        events.append(f"Dialogue: {layer},{_time(a)},{_time(min(b, duration))},Title,,0,0,0,,{contents}")

    def box(item, x=36, y=912, w=648, h=174, color="202023", start=None, end=None):
        if warm:
            color = "353D4A"
        draw = rf"{{\an7\pos({x},{y})\bord0\shad0\1c&H{color}&\alpha&H18&\p1}}"
        event(item, draw + f"m 0 0 l {w} 0 {w} {h} 0 {h}", 2, start, end)

    def text(item, content, x=60, y=940, size=32, color="FFFFFF", width=20, start=None, end=None):
        tags = (rf"{{\an7\pos({x},{y})\fs{size}\bord0\shad0\1c&H{color}&"
                rf"\fad({300 if warm else 120},120)}}")
        event(item, tags + _safe(content, width), 3, start, end)

    for item in pack["components"]:
        use = item["use"]
        if use == "HostReframe":
            continue
        if use == "TextCard":
            body = item.get("body", "")
            y = 890 if body else 128
            box(item, y=y, h=202 if body else 96)
            text(item, item["title"], y=y + 23, size=38, color=accent, width=16)
            if body:
                text(item, body, y=y + 84, size=27, width=22)
        elif use == "KeywordEmphasis":
            box(item, y=938, h=126)
            text(item, item["text"], y=970, size=42, color=accent, width=14)
        elif use == "MetricCard":
            box(item, y=866, h=226)
            text(item, item["value"] + " " + item["unit"], y=882, size=62, color=accent, width=12)
            text(item, item["label"], y=962, size=30, width=20)
            text(item, "来源：" + item["source"], y=1042, size=20, color="CCCCCC", width=28)
        elif use == "EvidenceFocus":
            box(item, y=808, h=284)
            text(item, item["claim"], y=828, size=32, color=accent, width=18)
            text(item, item["evidence"], y=884, size=29, width=21)
            text(item, "来源：" + item["source"], y=1050, size=20, color="CCCCCC", width=28)
        elif use == "ComparePanel":
            box(item, y=822, h=270)
            text(item, item["dimension"], y=842, size=30, color=accent)
            for key, x in (("left", 60), ("right", 385)):
                text(item, item[key]["title"], x=x, y=900, size=27, color=accent, width=12)
                text(item, item[key]["text"], x=x, y=950, size=25, width=10)
        elif use == "StepProgress":
            for index, start in enumerate(item["step_times"]):
                end = item["step_times"][index + 1] if index + 1 < len(item["steps"]) else item["until"]
                box(item, y=912, h=180, start=start, end=end)
                for n, step in enumerate(item["steps"]):
                    text(item, f"{n + 1:02}  {step}", y=929 + n * 36, size=27,
                         color=accent if index == n else "BBBBBB", width=24, start=start, end=end)
        elif use == "RecapBoard":
            box(item, y=822, h=270)
            text(item, item["title"], y=844, size=34, color=accent)
            for index, entry in enumerate(item["items"]):
                text(item, f"{index + 1}. {entry}", y=905 + index * 39, size=27, width=24)
    return "\n".join(events) + "\n"


def reframe_filter(pack: dict) -> str:
    """Change the picture before overlays, preserving audio and frame rate."""
    expression = "1"
    for item in reversed(pack["components"]):
        if item["use"] == "HostReframe":
            expression = (f"if(gte(on/30,{item['at']})*lt(on/30,{item['until']}),"
                          f"{item['scale']},{expression})")
    if expression == "1":
        return ""
    return (f"zoompan=z='{expression}':x='iw/2-iw/zoom/2':y='(ih-ih/zoom)*0.36':"
            "d=1:s=720x1280:fps=30,")
