---
name: avatarcast
description: Set up AvatarCast and turn an authorized photo and a one-sentence request into a finished talking-head video, with billing review before generation and local automatic packaging.
---

# AvatarCast

Use the repository's Python CLI, from the repository root. The project-local Codex and Claude Code entries both point here. Never claim the Skill itself provides a model, subscription, or credentials.

## Start from one photo and one sentence

A request to install AvatarCast and make a video authorizes local setup, drafting, planning and packaging. Carry out that workflow rather than returning installation instructions or asking the user to repeat the workflow in a longer prompt. Reuse a suitable existing checkout and environment; otherwise clone `https://github.com/ly85206559/Avatar-cast.git` into a new directory without overwriting unrelated work. Resolve the paths below from that checkout, including when this Skill was installed separately.

Unless the user specifies another video-generation budget, use existing subscription allowance only, with no extra spending. Explain early that the assistant account may incur usage charges, Grok Bot generation consumes account allowance and may incur overage, and local ASR/packaging makes no paid generation calls. Existing subscription does not establish zero extra cost. Never enable on-demand billing, top up, upgrade, buy assets, or switch to a paid service automatically. If this budget cannot be established, complete local setup and the plan, then stop before uploading the photo or submitting generation.

Handle files, defaults and commands yourself. Ask only for essential missing facts, user-only login actions, and one combined narration/billing approval before submission. After approval, continue through generation, local automatic packaging, playback checks and delivery without asking whether to continue each stage. Do not publish the result.

## Choose a route and check setup

If Python 3.10+ is absent, help install it using the official instructions for the current system. Create or reuse a repository-local virtual environment and install `.[native,asr]`; use that environment's Python for all commands below. Read `docs/LOCAL_PACKAGING.md` for the one-time Chinese Vosk model setup: download the documented model from its official source, unpack it in a local cache and pass its directory with `--asr-model` during packaging, or reuse `VOSK_MODEL_PATH`. Do not make the user find a model or type a path. If setup fails, report the limitation and use the documented simple-caption fallback rather than a paid ASR service.

The supported guided route is `grok-native`: each segment generates its own picture and Mandarin voice together at a requested 9:16 and 720p. It does not accept a locked recording or guarantee consistent voice across segments. WaveSpeed's audio-driven adapter is a separate, single-clip entry and has not been verified end to end; see `docs/API_LIPSYNC.md` if the user specifically needs locked audio. Do not offer an unimplemented provider as working.

Run `python -m dhp.cli make doctor`. For a real Grok Bot project also run `python -m dhp.cli make doctor --online`; this only reads gateway status and lists bots, without generating. On Windows, if the user has signed in to Grok Bot and the remote computer is awake, `pwsh -NoProfile -File scripts/setup_grok_bot_windows.ps1` can import the connection. It reads the local app's credential data and stores gateway credentials in the current user's `~/.gbm/config.json`; explain this before the import and never print the token. On macOS and Linux follow `docs/GROK_SETUP_UNIX.md`: the Unix importer reads the third-party Grok Bot CLI's local login and saves the gateway in the same private config. Explain that CLI's browser login and credential storage before use; do not claim live Unix support has been verified. The gateway is an unofficial, version-dependent interface and was validated on one Windows account.

If FFmpeg or its `subtitles` filter or `libx264` encoder is missing, help install an FFmpeg build with those features using a suitable trusted source and add it to PATH, then rerun `doctor`. The Python-provided fallback may lack the subtitles filter. Install a Chinese font if the check reports one missing; if font status is unknown, verify captions are legible. Explain that the project includes its own gateway client, not the Grok Bot application, account, CLI or MCP. Running an MCP server is not required; the macOS/Linux importer uses the separate CLI login unless a working gateway is already configured.

## Make a video

The normal input is one authorized photo and one sentence such as “用这张照片介绍我的咖啡店”. Treat that sentence as the production request unless the user asks to speak those exact words. Draft the narration and a short title yourself using the current assistant; no separate text-generation API or key is required. Use only supplied facts; ask a concise question if an essential fact is missing rather than inventing prices or claims.

Default to one approximately 10-second Mandarin clip, vertical 720p, with roughly 30–45 Chinese characters of narration. Follow an explicit requested length or ratio only when supported; explain unsupported requirements before planning. Choose packaging without a style questionnaire: `promo` for recommendations/promotions, `explainer` for knowledge/tutorials, `warm` for encouragement/empathy, otherwise `clean`. Preserve the user's explicit style preference. Draft a short headline, generally 8–12 Chinese characters. Do not make the user choose colors, fonts, filenames or technical parameters.

Save a UTF-8 brief with `request` (the user's intent), `script` (the actual spoken narration), `title`, and `style` (`clean`, `promo`, `explainer`, `warm`, or `auto`). Use a new temporary file or project workspace; never overwrite user inputs. For assistant-run commands on Windows PowerShell, set `$env:PYTHONUTF8 = '1'`. Produce a local plan; the output directory is chosen automatically:

```text
python -m dhp.cli make plan --image IMAGE --brief-file BRIEF.json
```

Use the returned `project` path as `NEW_PROJECT`. Run `python -m dhp.cli make show --project NEW_PROJECT` and retain the `plan_sha256`. Present one concise confirmation containing the actual narration, title, style, estimated duration/segment count, and known or unknown cost. Keep commands, hashes and JSON inside the assistant's work. Check the actual account's subscription, remaining allowance, on-demand/overage and automatic top-up settings with the user or an available account view; guide the user to the account screen if needed. The CLI cannot verify billing or enforce a spending cap. Unknown cost is not zero. Do not submit if the agreed budget cannot be established. Combine questions rather than asking separately for every default.

Only after the user explicitly approves this exact full plan and its billing conditions, run:

```text
python -m dhp.cli make run --project NEW_PROJECT --plan-sha256 REVIEWED_PLAN_HASH --confirm-allowance
```

Use the hash from the plan the user actually reviewed, not a newly computed hash after approval. If the plan changed, show it and obtain approval again. If more than one bot exists, use `dhp native bots` and add `--agent-id`. On interruption or a pending result, use `python -m dhp.cli make resume --project NEW_PROJECT`: it checks existing submissions without resending them, then may start remaining segments covered by the original approval. If the plan or image changes after approval, make a new project and obtain fresh approval. Never delete a job or blindly resubmit an uncertain request.

Once generation is complete, finish the default workflow with local automatic packaging; do not wait for a separate restyle request. Read `docs/LOCAL_PACKAGING.md` and run:

```text
python -m dhp.cli make restyle --project NEW_PROJECT --request ORIGINAL_REQUEST --style CHOSEN_STYLE --title TITLE
```

Use the original production intent and the reviewed style/title, properly quoted for the shell; add `--asr-model MODEL_DIRECTORY` if the model is not configured through the environment. This reuses completed originals, preserves their full normalized duration, and submits no generation. Missing setup or unreliable recognition yields simple estimated captions with a warning; disclose that fallback. The earlier `make run` cut uses estimated captions and conservative terminal near-silence trimming, so deliver the final restyled output path returned by this command, not the earlier cut. For a packaging/title change, reuse the completed project and latest conversational preferences rather than regenerating video.

Inspect decoded representative frames and card transitions, and play the final video to check audible speech, readable captions, face/mouth obstruction and the ending. A QA file or successful ASR match alone does not prove lip-sync or speech accuracy. If playback or a check is unavailable, say what remains unverified. Deliver the playable final MP4 first, the SRT if available, and a short note on actual generation submissions, verifiable allowance/cost and any review needed; do not call unknown charges zero. Keep optional technical reports out of the main delivery unless requested. Preserve the burned-in AI label. A publication description still needs the label; publishing is a separate user action.

When the user says “换成知识讲解风格” or changes only the title, reuse the completed project with the same automatic packaging command and the updated request/style/title. Carry forward the latest title from the current conversation or most recent edited result; omitting the flag uses the original plan's title. This is a local render with zero generation requests and does not need a new provider payment approval. Incomplete jobs cause it to stop; never regenerate merely to change packaging.

For a free synthetic rehearsal, follow the `--dry-run` example in `README.md`: it creates test cards and tones, not real speech or a digital human.

## Component packaging of completed clips

For content-aware local packaging, read `docs/LOCAL_PACKAGING.md`. Prefer `make restyle --project NEW_PROJECT --request "把这条做成知识分享"`: this automatically selects a promo, explainer or warm recipe and attempts local Vosk sentence matching, without writing a component timeline yourself. A completed old native job can use `--job-dir` instead. Reuse the ASR dependency and Chinese model from the one-time setup above; never silently switch to a paid service. Missing setup, mismatched words or low confidence produce simple estimated captions and a review warning. Tell the user when this fallback occurs. Recognizer timestamps are estimates, not forced word alignment or human approval. No media is uploaded and no generation is submitted.

Use the eight components through `--pack-file` when the user needs custom evidence, comparisons or a specific edit; this cannot be combined with `--request`. Prepare the JSON yourself using supplied facts and the completed original's actual duration. Keep `timing: estimated` until cue boundaries have been checked in playback. The explicit timeline preserves the full original duration. Do not infer product demonstrations or an emotional performance from packaging existing test dialogue. Inspect card transitions and readable text, then deliver the video.
