---
name: avatarcast
description: Turn an authorized photo and a one-sentence request into a scripted, styled talking-head video, using the user's approved Grok Bot allowance; restyle completed clips locally.
---

# AvatarCast

Use the repository's Python CLI, from the repository root. The project-local Codex and Claude Code entries both point here. If Python 3.10+ is absent, help the user install it using the official instructions for their system. If project dependencies are missing, create a repository-local Python virtual environment and install `.[native]`; use that environment's Python for the commands below. Never claim the Skill itself provides a model, subscription, or credentials.

## Choose a route and check setup

The supported guided route is `grok-native`: each segment generates its own picture and Mandarin voice together at a requested 9:16 and 720p. It does not accept a locked recording or guarantee consistent voice across segments. WaveSpeed's audio-driven adapter is a separate, single-clip entry and has not been verified end to end; see `docs/API_LIPSYNC.md` if the user specifically needs locked audio. Do not offer an unimplemented provider as working.

Run `python -m dhp.cli make doctor`. For a real Grok Bot project also run `python -m dhp.cli make doctor --online`; this only reads gateway status and lists bots, without generating. On Windows, if the user has signed in to Grok Bot and the remote computer is awake, `pwsh -NoProfile -File scripts/setup_grok_bot_windows.ps1` can import the connection. It reads the local app's credential data and stores gateway credentials in the current user's `~/.gbm/config.json`; explain this before the import and never print the token. On macOS and Linux follow `docs/GROK_SETUP_UNIX.md`: the Unix importer reads the third-party Grok Bot CLI's local login and saves the gateway in the same private config. Explain that CLI's browser login and credential storage before use; do not claim live Unix support has been verified. The gateway is an unofficial, version-dependent interface and was validated on one Windows account.

If FFmpeg or its `subtitles` filter or `libx264` encoder is missing, help install an FFmpeg build with those features using a suitable trusted source and add it to PATH, then rerun `doctor`. The Python-provided fallback may lack the subtitles filter. Install a Chinese font if the check reports one missing; if font status is unknown, verify captions are legible. Explain that the project includes its own gateway client, not the Grok Bot application, account, CLI or MCP. Running an MCP server is not required; the macOS/Linux importer uses the separate CLI login unless a working gateway is already configured.

## Make a video

The normal input is one authorized photo and one sentence such as “用这张照片介绍我的咖啡店”. Treat that sentence as the production request unless the user asks to speak those exact words. Draft the narration and a short title yourself using the current assistant; no separate text-generation API or key is required. Use only supplied facts; ask a concise question if an essential fact is missing rather than inventing prices or claims.

Default to one short Mandarin clip, vertical 720p, with roughly 30–45 Chinese characters of narration. Follow an explicit requested length or ratio only when supported; explain unsupported requirements before planning. Choose packaging without a style questionnaire: `promo` for recommendations/promotions, `explainer` for knowledge/tutorials, `warm` for encouragement/empathy, otherwise `clean`. Preserve the user's explicit style preference. Draft a short headline, generally 8–12 Chinese characters. Do not make the user choose colors, fonts, filenames or technical parameters.

Save a UTF-8 brief with `request` (the user's intent), `script` (the actual spoken narration), `title`, and `style` (`clean`, `promo`, `explainer`, `warm`, or `auto`). Use a new temporary file or project workspace; never overwrite user inputs. For assistant-run commands on Windows PowerShell, set `$env:PYTHONUTF8 = '1'`. Produce a local plan; the output directory is chosen automatically:

```text
python -m dhp.cli make plan --image IMAGE --brief-file BRIEF.json
```

Use the returned `project` path as `NEW_PROJECT`. Run `python -m dhp.cli make show --project NEW_PROJECT` and retain the `plan_sha256`. Present one concise confirmation containing the actual narration, style, estimated duration/segment count, and known or unknown cost. Keep commands, hashes and JSON inside the assistant's work. Check the actual account's subscription, allowance and on-demand/overage setting with the user or an available account view. The CLI cannot verify billing or enforce a spending cap. Unknown cost is not zero. Do not submit if the user requires a no-extra-charge guarantee that cannot be established. Combine questions rather than asking separately for every default.

Only after the user explicitly approves this exact multi-segment plan and its billing conditions, run:

```text
python -m dhp.cli make run --project NEW_PROJECT --plan-sha256 REVIEWED_PLAN_HASH --confirm-allowance
```

Use the hash from the plan the user actually reviewed, not a newly computed hash after approval. If the plan changed, show it and obtain approval again. If more than one bot exists, use `dhp native bots` and add `--agent-id`. On interruption or a pending result, use `python -m dhp.cli make resume --project NEW_PROJECT`: it checks existing submissions without resending them, then may start remaining segments covered by the original approval. If the plan or image changes after approval, make a new project and obtain fresh approval. Never delete a job or blindly resubmit an uncertain request.

The result contains the selected packaging, subtitles, an SRT and QA report. New packaged cuts conservatively shorten long terminal near-silence while keeping original job files. This is not speech recognition; uncertain/quiet clips are preserved and need review. Automatic captions use estimated segment timing, not speech alignment. Inspect decoded frames, captions and audio; deliver the playable video first and explain any observed quality issue briefly. Keep optional files and technical reports out of the main delivery unless requested. AI labeling is burned into the edited video; a publication description still needs the label. Publishing is a separate user action.

When the user says “换成知识讲解风格” or changes only the title, reuse the completed project. Run `python -m dhp.cli make restyle --project NEW_PROJECT --style explainer --title TITLE`. Carry forward the latest title from the current conversation or most recent edited result; omitting the flag uses the original plan's title. This is a local render with zero generation requests and does not need a new provider payment approval. Incomplete jobs cause it to stop; never regenerate merely to change packaging.

For a free synthetic rehearsal, follow the `--dry-run` example in `README.md`: it creates test cards and tones, not real speech or a digital human.

## Component packaging of completed clips

For content-aware local packaging, read `docs/LOCAL_PACKAGING.md`. Eight components are available via `make restyle --pack-file`: choose topic/closing cards, keyword or number emphasis, sourced text evidence, text comparison, steps, safe picture reframing and recap to serve the content. Prepare the JSON yourself; the user can just say “少点花字” or “加个对比”. Use few cards, supplied facts, and the completed original's actual duration. Keep `timing: estimated` until cue boundaries have been checked in playback; no automatic word alignment exists. The explicit timeline preserves the full original duration. Do not infer product demonstrations or an emotional performance from packaging existing test dialogue. Inspect card transitions and readable text, then deliver the video. The local command never submits generation tasks.
