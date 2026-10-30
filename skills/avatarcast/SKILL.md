---
name: avatarcast
description: Run AvatarCast's offline rehearsal or an approved Grok Bot native talking-head clip, and inspect the result.
---

# AvatarCast

AvatarCast is a Python pipeline with this thin Skill as an assistant-facing entry point. Use the repository and CLI; do not invent provider capability or pricing. Run from the repository root, with `src` on Python's import path, or install the project locally. The offline rehearsal and native video workflow have different inputs and evidence.

## Native video: Grok Bot

For an approved single short clip, use an authorized presenter image, the desired spoken text, a Grok Bot agent ID, the user's configured Grok Bot gateway, and FFmpeg (or the optional `imageio-ffmpeg` package). Native video generates the image and voice together; it does not preserve a supplied WAV or guarantee exact speech or lip alignment. The gateway is a third-party private interface, not an official stable API; account availability and billing depend on the user's service. The native CLI has not yet been validated by a real end-to-end generation. One separately generated sample was accepted by the user; that does not establish this CLI's reliability.

Install with `python -m pip install -e ".[native]"`. On Windows, with PowerShell 7 and the user signed in to Grok Bot, wake the remote computer and run `pwsh -NoProfile -File scripts/setup_grok_bot_windows.ps1` to attempt to import the gateway connection. Run `dhp native bots` to list IDs without generating media. The import uses the user's local application data and saves credentials in `~/.gbm/config.json`; it may need to be rerun after the remote computer or app changes. Other platforms need an existing working gateway configuration; setup is not verified across accounts or platforms. Never print or share the saved token. Before a real request, verify the subscription, allowance, and whether overage or extra charges are enabled; the command cannot enforce the provider's billing settings.

Check the user's subscription, available allowance and any per-request charges. Start by showing the plan, which does not upload or generate:

```text
dhp native start --image IMAGE --text TEXT --agent-id BOT_ID --output-dir OUTPUT --duration 10 --billing allowance
```

Add `--confirm` only after the user explicitly approves this request and its billing terms. `allowance` records the user's intent to use existing account allowance; it does not technically guarantee the final bill. If the provider requires additional payment, stop for authorization. Never represent unknown cost or quota use as zero, and never infer approval for new generations from a previous sample or dry-run.

After a submission, recover by running `dhp native resume --output-dir OUTPUT`. Resume only checks and downloads the existing result; do not automatically resubmit an uncertain request. Keep gateway tokens out of chat, source control and reports. The single-clip command saves a raw MP4 and a machine-check report; it does not automatically validate exact words or lip sync. Preserve the raw video and its native audio, inspect representative decoded frames and the audio, and record the actual dimensions, duration and human feedback. Record the user's decision using `dhp native review --output-dir OUTPUT --decision accept` or `--decision needs_changes`. Automated transcription can misread names; locate uncertain words for review instead of automatically triggering paid regeneration. Do not claim lip-sync or face metrics that were not measured. One accepted sample does not establish cross-segment quality or a 30-second benchmark.

To assemble at least two completed native clips locally, use `dhp native assemble --job-dir FIRST --job-dir SECOND --output-dir NEW_OUTPUT`. It produces a re-encoded video and audio, estimated burned-in subtitles, an SRT and a QA report. It burns an AI digital-human performance label into the video; add and verify the label in the publication description separately. This requires FFmpeg with the `subtitles` filter and `libx264`, plus a suitable Chinese font. Subtitle timing is estimated from segment length and text, not aligned to speech; inspect captions, speech, lip sync and consistency before reporting or publishing. Repeating one clip tests assembly only; it does not establish quality across independent generations. The report leaves quality and publication approval unverified.

The audio-driven WaveSpeed route is separate: use it when the user needs an already locked recording to drive lip motion. Follow `docs/API_LIPSYNC.md` for its required credentials, accessible inputs, live quote, and explicit cost confirmation; it does not currently prove a multi-segment end-to-end workflow.

## Offline rehearsal

Confirm that Python, FFmpeg, and ffprobe are available.

Given a script JSON and brief JSON, run:

```text
python -m dhp.cli SCRIPT --brief BRIEF --dry-run --output-dir OUTPUT --cache-dir CACHE
```

The brief must set `duration_target_sec` to 30–60; the script must contain at least two segments. Use a new or empty output directory separate from the cache directory. To reuse cached segments, select a new output directory and keep the same cache directory. The existing example files demonstrate the input format. Inspect `qa.json`, the video, and the SRT before reporting the result. Report cache hits and simulated costs separately from actual spending.

The dry-run uses synthetic tones and labeled test cards, with captions burned into the video and also saved as SRT. Its scores, retry failures, and prices are simulated. It does not generate speech, perform real lip sync, or establish real video quality. Never describe its output as a real digital-human video.
