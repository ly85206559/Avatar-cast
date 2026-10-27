"""API-first lip-sync provider (default route).

Default vendor, verified against its official docs on 2026-10-27:
WaveSpeed OmniHuman 1.5.
  Submit: POST https://api.wavespeed.ai/api/v3/bytedance/avatar-omni-human-1.5
  Auth:   Authorization: Bearer $WAVESPEED_API_KEY
  Body:   {"image": "<image_url>", "audio": "<audio_url>"}
  Poll:   GET https://api.wavespeed.ai/api/v3/predictions/{id}/result
  Status: completed / failed / cancelled / timeout / deleted
  Output: result.outputs[0] is the video URL (per the docs example).

Two hard rules, copied from the vendor docs, not invented here:
1. NEVER retry the submit request automatically. A retry after an unclear
   failure can create a second, billed task. Check History / predictions
   first if a submit outcome is unknown.
2. NEVER treat a displayed base price as the final price. The vendor page
   says the final charge scales with size/length and is shown live beside
   Generate. This adapter therefore refuses to submit until the caller
   passes confirm_live_price=True AND a rate_per_sec from that live page.

Local files are NOT uploaded by this adapter: the vendor endpoint takes
URLs. Upload image/audio to a URL you control first, then pass the URLs.
That step is deliberately left explicit, not hidden behind a fake uploader.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .cache import cache_key
from .providers import Audio, Clip, Quote

TERMINAL_FAILED = {"failed", "cancelled", "timeout", "deleted"}


@dataclass
class ApiLipSyncConfig:
    provider: str = "wavespeed-api"
    model: str = "avatar-omni-human-1.5"
    submit_url: str = "https://api.wavespeed.ai/api/v3/bytedance/avatar-omni-human-1.5"
    result_url_template: str = "https://api.wavespeed.ai/api/v3/predictions/{id}/result"
    api_key_env: str = "WAVESPEED_API_KEY"
    # Fill from the live price beside Generate before the first run.
    # None means "unknown" -- never guess a price, and never submit on a guess.
    rate_per_sec: float | None = None
    poll_interval_sec: float = 2.0
    timeout_sec: float = 600.0


def _http_json(url: str, api_key: str, method: str = "GET",
               body: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode("utf-8")
    try:
        with urllib.request.urlopen(req, data=data, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"error": raw}


class ApiLipSyncProvider:
    """Lip-sync via a hosted API. Extension point: subclass and override
    submit_url / result parsing for another vendor, keeping this class's
    no-retry-submit and price-confirmation rules."""

    def __init__(self, config: ApiLipSyncConfig | None = None,
                 api_key: str | None = None):
        self.config = config or ApiLipSyncConfig()
        self.api_key = api_key or os.environ.get(self.config.api_key_env, "")

    def estimate(self, audio_duration_sec: float) -> Quote:
        if self.config.rate_per_sec is None:
            return Quote(
                estimated_cost=0.0,
                notes="PRICE UNKNOWN: read the live price beside Generate, "
                      "set rate_per_sec in config, then re-quote. "
                      "0.0 here is a placeholder, NOT a price.",
            )
        return Quote(
            estimated_cost=round(audio_duration_sec * self.config.rate_per_sec, 2),
            notes=f"at configured rate_per_sec={self.config.rate_per_sec}, "
                  "re-confirm the live Generate price before submitting.",
        )

    def dry_run(self, image_url: str, audio: Audio) -> dict:
        """No network, no charge. Validates the job and prints its quote."""
        return {
            "provider": self.config.provider,
            "model": self.config.model,
            "submit_url": self.config.submit_url,
            "image_url": image_url,
            "audio_sha256": audio.sha256,
            "audio_duration_sec": audio.duration_sec,
            "quote": self.estimate(audio.duration_sec),
            "cache_key": cache_key({
                "image_url": image_url, "audio_sha256": audio.sha256,
                "model": self.config.model}),
            "will_submit": False,
        }

    def drive(self, image_url: str, audio: Audio, output_path: str,
              *, confirm_live_price: bool = False) -> Clip:
        if not confirm_live_price:
            raise RuntimeError(
                "Refusing to submit: pass confirm_live_price=True only after "
                "reading the live price beside Generate for this exact input.")
        if self.config.rate_per_sec is None:
            raise RuntimeError(
                "Refusing to submit: rate_per_sec is unset. Set it from the "
                "live Generate price first; do not guess it.")
        if not self.api_key:
            raise RuntimeError(
                f"Refusing to submit: {self.config.api_key_env} is not set. "
                "API keys go in environment variables, never in the repo.")
        # Submit exactly once. No retry here, ever (see module docstring).
        status, resp = _http_json(self.config.submit_url, self.api_key,
                                  method="POST",
                                  body={"image": image_url, "audio": audio.path})
        data = resp.get("data", resp) if isinstance(resp, dict) else {}
        prediction_id = data.get("id") if isinstance(data, dict) else None
        if status >= 400 or not prediction_id:
            raise RuntimeError(
                f"Submit failed (HTTP {status}). Do NOT resubmit blindly: "
                f"check History/predictions first. Response: {resp}")
        video_url = self._poll(prediction_id)
        self._download(video_url, output_path)
        return Clip(path=output_path, model=self.config.model,
                    model_version=self.config.model,
                    params={"provider": self.config.provider},
                    duration_sec=audio.duration_sec,
                    cost=self.estimate(audio.duration_sec).estimated_cost)

    def _poll(self, prediction_id: str) -> str:
        url = self.config.result_url_template.format(id=prediction_id)
        deadline = time.time() + self.config.timeout_sec
        while time.time() < deadline:
            status, resp = _http_json(url, self.api_key)
            if status in (429,) or status >= 500:
                time.sleep(10)
                continue
            data = resp.get("data", resp) if isinstance(resp, dict) else {}
            state = data.get("status") if isinstance(data, dict) else None
            if state == "completed":
                outputs = data.get("outputs") or []
                if not outputs:
                    raise RuntimeError(f"Task {prediction_id} completed without outputs: {resp}")
                return outputs[0]
            if state in TERMINAL_FAILED:
                raise RuntimeError(f"Task {prediction_id} ended with status {state}: {resp}")
            time.sleep(self.config.poll_interval_sec)
        raise RuntimeError(f"Task {prediction_id} timed out after {self.config.timeout_sec}s")

    @staticmethod
    def _download(url: str, output_path: str) -> None:
        with urllib.request.urlopen(url, timeout=120) as resp, \
                open(output_path, "wb") as f:
            f.write(resp.read())
