"""Small local packaging presets; no model or account is needed to change a style."""

from __future__ import annotations

import math
import re
import textwrap
from pathlib import Path


STYLES = {
    "clean": {"label": "简洁口播", "accent": "FFFFFF", "panel": "202020", "y": 110},
    "promo": {"label": "重点推荐", "accent": "00BFFF", "panel": "181818", "y": 970},
    "explainer": {"label": "知识讲解", "accent": "FFCC66", "panel": "482510", "y": 110},
}


def prepare(style: str = "auto", title: str = "", request: str = "") -> dict:
    if not isinstance(style, str) or not isinstance(title, str) or not isinstance(request, str):
        raise ValueError("Presentation title and request must be text.")
    if style == "auto":
        if re.search(r"推荐|种草|带货|广告|促销|推广|优惠|promot|sell", request, re.I):
            style = "promo"
        elif re.search(r"讲解|科普|教程|知识|解释|教学|explain|tutorial|teach", request, re.I):
            style = "explainer"
        else:
            style = "clean"
    if style not in STYLES:
        raise ValueError("Style must be auto, clean, promo, or explainer.")
    title = " ".join(title.split())
    if len(title) > 32:
        raise ValueError("Use a short video title of at most 32 characters.")
    return {"style": style, "title": title}


def write_overlay(path: Path, duration: float, presentation: dict) -> None:
    preset = STYLES[presentation["style"]]
    end_cs = math.ceil((duration + 1) * 100)
    end = f"{end_cs // 360000}:{(end_cs // 6000) % 60:02}:{(end_cs // 100) % 60:02}.{end_cs % 100:02}"
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 720\nPlayResY: 1280\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV,Encoding\n"
        "Style: Label,Microsoft YaHei,28,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
        "-1,0,0,0,100,100,0,0,1,2,0,8,20,20,24,1\n"
        "Style: Title,Microsoft YaHei,42,&H00FFFFFF,&H00FFFFFF,&H00202020,&H80000000,"
        "-1,0,0,0,100,100,0,0,1,1,0,5,24,24,0,1\n"
        "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )
    events = [f"Dialogue: 2,0:00:00.00,{end},Label,,0,0,0,,AI 数字人演绎"]
    title = presentation["title"]
    if title:
        # User text is data, never an ASS override or drawing command.
        safe = title.translate(str.maketrans({"\\": "＼", "{": "｛", "}": "｝"}))
        lines = textwrap.wrap(safe, width=16, break_long_words=True, break_on_hyphens=False)
        text = r"\N".join(lines)
        y = preset["y"]
        height = 64 if len(lines) == 1 else 112
        panel = (rf"{{\an7\pos(24,{y - 16})\bord0\shad0\1c&H{preset['panel']}&\alpha&H25&\p1}}"
                 f"m 0 0 l 672 0 672 {height} 0 {height}")
        if presentation["style"] != "clean":
            events.append(f"Dialogue: 0,0:00:00.00,{end},Title,,0,0,0,,{panel}")
            stripe = (rf"{{\an7\pos(24,{y - 16})\bord0\shad0\1c&H{preset['accent']}&\p1}}"
                      f"m 0 0 l 8 0 8 {height} 0 {height}")
            events.append(f"Dialogue: 1,0:00:00.00,{end},Title,,0,0,0,,{stripe}")
        caption = rf"{{\an5\pos(360,{y - 16 + height // 2})\bord2\1c&H{preset['accent']}&\fad(150,0)}}" + text
        events.append(f"Dialogue: 1,0:00:00.00,{end},Title,,0,0,0,,{caption}")
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def subtitle_filter(presentation: dict) -> str:
    accent = STYLES[presentation["style"]]["accent"]
    return ("subtitles=subtitles.srt:force_style='FontName=Microsoft YaHei,FontSize=9,"
            f"Bold=1,Outline=1,MarginV=18,PrimaryColour=&H{accent}&',subtitles=ai-label.ass")
