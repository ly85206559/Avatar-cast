"""Local recipe selection and conservative ASR sentence matching. No provider calls."""

from __future__ import annotations

import difflib
import math
import re
import subprocess

from .asr_vosk import VoskASRProvider


def _clean(text: str) -> str:
    return "".join(c for c in text.casefold() if c.isalnum())


def match_cues(text: str, words: list[dict], duration: float) -> dict:
    """Use only exact, confident matches; never interpolate missing word times."""
    recognized, owners = "", []
    previous_end = 0.0
    for index, word in enumerate(words):
        start, end, confidence = (word.get(k) for k in ("start", "end", "conf"))
        if (not isinstance(word.get("word"), str)
                or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
                       for v in (start, end, confidence))
                or not 0 <= confidence <= 1 or not 0 <= start < end <= duration + 0.05
                or start < previous_end - 0.05):
            return {"status": "fallback", "reason": "invalid_or_missing_word_timing", "cues": []}
        value = _clean(word["word"])
        recognized += value
        owners.extend([index] * len(value))
        previous_end = end
    expected = _clean(text)
    mapping = {}
    for block in difflib.SequenceMatcher(None, expected, recognized, autojunk=False).get_matching_blocks():
        mapping.update({block.a + n: block.b + n for n in range(block.size)})
    cues, offset, last_end = [], 0, 0.0
    for chunk in re.findall(r"[^，。！？!?；;]+[，。！？!?；;]?", text):
        normalized = _clean(chunk)
        if not normalized:
            continue
        positions = [mapping.get(offset + n) for n in range(len(normalized))]
        offset += len(normalized)
        if any(p is None for p in positions) or positions != list(range(positions[0], positions[0] + len(positions))):
            return {"status": "fallback", "reason": "script_transcript_mismatch", "cues": []}
        indexes = sorted({owners[p] for p in positions})
        # A cue must use complete recognized words, including at punctuation boundaries.
        if positions[0] > 0 and owners[positions[0] - 1] == indexes[0]:
            return {"status": "fallback", "reason": "ambiguous_sentence_boundary", "cues": []}
        if positions[-1] + 1 < len(owners) and owners[positions[-1] + 1] == indexes[-1]:
            return {"status": "fallback", "reason": "ambiguous_sentence_boundary", "cues": []}
        if min(words[i]["conf"] for i in indexes) < 0.8:
            return {"status": "fallback", "reason": "low_word_confidence", "cues": []}
        start, end = words[indexes[0]]["start"], min(duration, words[indexes[-1]]["end"])
        if start < last_end or end <= start:
            return {"status": "fallback", "reason": "overlapping_sentence_bounds", "cues": []}
        cues.append({"text": chunk.strip(), "start": start, "end": end})
        last_end = end
    # Unmatched recognized speech must not silently disappear from the displayed script.
    if not cues or recognized != expected:
        return {"status": "fallback", "reason": "script_transcript_mismatch", "cues": []}
    return {"status": "matched", "reason": None, "cues": cues}


def recipe(style: str, title: str, cues: list[dict], duration: float, matched: bool) -> dict:
    """Select a small set of components from actual spoken clauses, not invented claims."""
    titles = {"promo": "看见这段介绍的重点", "explainer": "这段内容，一步步看", "warm": "慢慢听，慢慢说", "clean": "这段口播"}
    heading = title if 0 < len(title) <= 16 else titles[style]
    intro_end = min(duration, cues[1]["start"] if len(cues) > 1 else 1.6)
    items = [{"use": "TextCard", "at": 0, "until": max(min(0.1, duration), intro_end), "title": heading}]
    if not matched:
        return {"timing": "estimated", "components": items}
    units = [c for c in cues if 4 <= len(c["text"]) <= 18 and c["end"] - c["start"] >= 1]
    units = [c for c in units if c["start"] >= intro_end]
    if style == "explainer" and len(units) >= 2:
        chosen = units[:4]
        items.append({"use": "StepProgress", "at": chosen[0]["start"], "until": chosen[-1]["end"],
                      "steps": [c["text"].rstrip("，。！？!?；;") for c in chosen],
                      "step_times": [c["start"] for c in chosen]})
    elif style == "promo":
        for cue in units[:3]:
            items.append({"use": "KeywordEmphasis", "at": cue["start"], "until": cue["end"],
                          "text": cue["text"].rstrip("，。！？!?；;")})
        if units:
            items.append({"use": "HostReframe", "at": units[0]["start"], "until": units[0]["end"], "scale": 1.06})
    elif style == "warm" and units:
        cue = units[-1]
        items.append({"use": "KeywordEmphasis", "at": cue["start"], "until": cue["end"],
                      "text": cue["text"].rstrip("，。！？!?；;")})
    elif style == "explainer" and units:
        cue = units[0]
        items.append({"use": "EvidenceFocus", "at": cue["start"], "until": cue["end"],
                      "claim": "这句原话", "evidence": cue["text"], "source": "原片台词与本地转写匹配"})
    return {"timing": "asr_matched", "components": items}


def prepare(video: str, text: str, duration: float, style: str, title: str,
            model_path: str | None = None, *, template: dict | None = None) -> dict:
    words = []
    try:
        words = VoskASRProvider(model_path).transcribe(video)
        alignment = match_cues(text, words, duration)
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        alignment = {"status": "fallback", "reason": "local_asr_unavailable", "detail": str(exc), "cues": []}
    matched = alignment["status"] == "matched"
    if template is not None:
        from . import content_templates

        pack = content_templates.recipe(template, title, alignment["cues"], duration, matched)
    else:
        pack = recipe(style, title, alignment["cues"], duration, matched)
    warnings = [] if matched else ["语音匹配不可靠或本地识别不可用：已降级为简单字幕，请复核台词与时间。"]
    if template is not None and matched and len(pack["components"]) == 1:
        warnings.append("语音已匹配，但缺少适合卡片长度的短句：仅保留标题，请缩短文案或人工调整包装。")
    return {"alignment": {**alignment, "engine": "vosk", "minimum_word_confidence": 0.8,
                           "word_times_are": "recognizer_estimates_not_forced_alignment",
                           "review_required": True, "words": words},
            "pack": pack,
            "warnings": warnings}
