"""Cache key: script + persona + model + params + reference + audio hash.

Same input -> same key -> cache hit, zero regeneration cost.
Change any input -> different key -> must regenerate. That is the point.
"""

from __future__ import annotations

import hashlib
import json


def cache_key(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def segment_cache_key(segment: dict, persona_id: str, model: str,
                      model_version: str, params: dict, audio_sha256: str) -> str:
    return cache_key({
        "text": segment["text"],
        "persona_id": persona_id,
        "model": model,
        "model_version": model_version,
        "params": params,
        "audio_sha256": audio_sha256,
    })
