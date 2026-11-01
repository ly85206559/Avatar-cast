---
name: avatarcast
description: Set up AvatarCast and create a presenter-led video from an authorized image and script, using the user's approved Grok Bot allowance.
---

# AvatarCast

Use the repository's Python CLI, from the repository root. The project-local Codex and Claude Code entries both point here. If Python 3.10+ is absent, help the user install it using the official instructions for their system. If project dependencies are missing, create a repository-local Python virtual environment and install `.[native]`; use that environment's Python for the commands below. Never claim the Skill itself provides a model, subscription, or credentials.

## Choose a route and check setup

The supported guided route is `grok-native`: each segment generates its own picture and Mandarin voice together at a requested 9:16 and 720p. It does not accept a locked recording or guarantee consistent voice across segments. WaveSpeed's audio-driven adapter is a separate, single-clip entry and has not been verified end to end; see `docs/API_LIPSYNC.md` if the user specifically needs locked audio. Do not offer an unimplemented provider as working.

Run `python -m dhp.cli make doctor`. For a real Grok Bot project also run `python -m dhp.cli make doctor --online`; this only reads gateway status and lists bots, without generating. On Windows, if the user has signed in to Grok Bot and the remote computer is awake, `pwsh -NoProfile -File scripts/setup_grok_bot_windows.ps1` can import the connection. It reads the local app's credential data and stores gateway credentials in the current user's `~/.gbm/config.json`; explain this before the import and never print the token. On macOS and Linux follow `docs/GROK_SETUP_UNIX.md`: the Unix importer reads the third-party Grok Bot CLI's local login and saves the gateway in the same private config. Explain that CLI's browser login and credential storage before use; do not claim live Unix support has been verified. The gateway is an unofficial, version-dependent interface and was validated on one Windows account.

If FFmpeg or its `subtitles` filter or `libx264` encoder is missing, help install an FFmpeg build with those features using a suitable trusted source and add it to PATH, then rerun `doctor`. The Python-provided fallback may lack the subtitles filter. Install a Chinese font if the check reports one missing; if font status is unknown, verify captions are legible. Explain that the project includes its own gateway client, not the Grok Bot application, account, CLI or MCP. Running an MCP server is not required; the macOS/Linux importer uses the separate CLI login unless a working gateway is already configured.

## Make a video

Get an authorized presenter image, the script, and the desired output directory. Help draft a script when asked; save it as UTF-8 text if that avoids shell encoding problems. For assistant-run commands on Windows PowerShell, set `$env:PYTHONUTF8 = '1'` so captured Chinese output is decoded correctly. If the terminal looks garbled, inspect the saved UTF-8 plan and verify its text before approval. Produce a local plan first:

```text
python -m dhp.cli make plan --image IMAGE --script-file SCRIPT.txt --output-dir NEW_PROJECT
```

Run `python -m dhp.cli make show --project NEW_PROJECT` and present the exact segments, estimated lengths, route, image, and known or unknown costs. Retain the `plan_sha256` shown with that plan. Split points and timings are estimates; allow the user to review them. Check the actual account's subscription, allowance and on-demand/overage setting with the user or an available account view. The CLI cannot verify billing or enforce a spending cap. Unknown cost is not zero. Do not submit if the user requires a no-extra-charge guarantee that cannot be established.

Only after the user explicitly approves this exact multi-segment plan and its billing conditions, run:

```text
python -m dhp.cli make run --project NEW_PROJECT --plan-sha256 REVIEWED_PLAN_HASH --confirm-allowance
```

Use the hash from the plan the user actually reviewed, not a newly computed hash after approval. If the plan changed, show it and obtain approval again. If more than one bot exists, use `dhp native bots` and add `--agent-id`. On interruption or a pending result, use `python -m dhp.cli make resume --project NEW_PROJECT`: it checks existing submissions without resending them, then may start remaining segments covered by the original approval. If the plan or image changes after approval, make a new project and obtain fresh approval. Never delete a job or blindly resubmit an uncertain request.

The result contains a subtitled video, SRT and QA report. Automatic captions use estimated segment timing, not speech alignment; a completed file is ready for human review, not proof of lip sync, identity, exact words, or cross-segment voice consistency. Inspect decoded frames, captions and audio; ask the user to review the result. AI labeling is burned into the edited video; a publication description still needs the label. Publishing is a separate user action.

For a free synthetic rehearsal, follow the `--dry-run` example in `README.md`: it creates test cards and tones, not real speech or a digital human.
