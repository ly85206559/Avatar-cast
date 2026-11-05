---
name: avatarcast
description: Turn an authorized photo and one-sentence request into a talking-head video using reusable content templates, with billing review and local packaging; restyle completed clips.
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

If the connection fails, follow the returned `recovery` steps. HTTP 417 can indicate a sleeping computer or stale gateway; it does not prove either cause. After the existing computer is woken, the import scripts poll readiness for up to 30 seconds before refreshing the private gateway. They do not wake or create a computer. If it remains unavailable, report the blocker. Preserve submitted job receipts and use `make resume` after connection recovery; do not start replacement jobs.

If FFmpeg or its `subtitles` filter or `libx264` encoder is missing, help install an FFmpeg build with those features using a suitable trusted source and add it to PATH, then rerun `doctor`. The Python-provided fallback may lack the subtitles filter. Install a Chinese font if the check reports one missing; if font status is unknown, verify captions are legible. Explain that the project includes its own gateway client, not the Grok Bot application, account, CLI or MCP. Running an MCP server is not required; the macOS/Linux importer uses the separate CLI login unless a working gateway is already configured.

## Make a video

The normal input is one authorized photo and one sentence such as “用这张照片介绍我的咖啡店”. Treat that sentence as the production request unless the user asks to speak those exact words. Draft the narration and a short title yourself using the current assistant; no separate text-generation API or key is required. Use only supplied facts; ask a concise question if an essential fact is missing rather than inventing prices or claims.

Default to one approximately 10-second Mandarin clip, vertical 720p, with roughly 30–45 Chinese characters of narration. Choose a content template by meaning without a questionnaire: `three-point` for three practical tips or a short list, `product-demo` when the user chooses a showcase or wants to display supplied product media, `product-intro` for simple product recommendations, `knowledge-share` for explaining a question or method, `empathy` for encouragement or emotional support. Preserve an explicit template choice. Keep the plain `clean` route for generic introductions. Preserve explicit preferences and explain unsupported formats before planning. Draft a short headline; do not ask the user to choose fonts or technical parameters.

Run `python -m dhp.cli make templates TEMPLATE_ID` for the selected template. Read its narrative slots, required facts, format and fallback. Draft each `structure[].key` in order. For `three-point`, write a short hook, three distinct points of at most 18 characters each, and one closing; use `templates/three-point/example.json` as a model. For `product-demo`, arrange a hook, genuine use case, one verified feature to demonstrate, and an appropriate conclusion. These slots are internal writing guidance, not a user form. Ask only for missing essential facts; never invent product features, prices, evidence or testimonials. If the user supplied a local product image or video, include its path as `asset` in the brief; it is used only in local post-production. Without media, explain that the result will use full-screen presenter footage, and proceed if that satisfies the request. The two featured GIFs reuse the existing relaxation narration; the showcase card demonstrates layout, not a product review. See `templates/README.md` for examples.

Save a UTF-8 brief with `request`, `template`, `title`, and the drafted `beats`; omit `script` so the CLI joins the slots and adds missing sentence-end punctuation. If both are supplied, they must match exactly. Explicit `style` overrides the default appearance. For plain non-template narration, retain the existing request/script/title/style brief. Use a new temporary file; never overwrite user inputs. On Windows PowerShell set `$env:PYTHONUTF8 = '1'`. Produce the local plan:

```text
python -m dhp.cli make plan --image IMAGE --brief-file BRIEF.json
```

Use the returned `project` path as `NEW_PROJECT`. Run `python -m dhp.cli make show --project NEW_PROJECT` and retain the `plan_sha256`. Present one concise confirmation containing the actual narration, title, selected showcase media if any, style, estimated duration/segment count, and known or unknown cost. Keep commands, hashes and JSON inside the assistant's work. Check the actual account's subscription, remaining allowance, on-demand/overage and automatic top-up settings with the user or an available account view; guide the user to the account screen if needed. The CLI cannot verify billing or enforce a spending cap. Unknown cost is not zero. Do not submit if the agreed budget cannot be established. Combine questions rather than asking separately for every default.

Only after the user explicitly approves this exact full plan and its billing conditions, run:

```text
python -m dhp.cli make run --project NEW_PROJECT --plan-sha256 REVIEWED_PLAN_HASH --confirm-allowance
```

Use the hash from the plan the user actually reviewed, not a newly computed hash after approval. If the plan changed, show it and obtain approval again. If more than one bot exists, use `dhp native bots` and add `--agent-id`. On interruption or a pending result, use `python -m dhp.cli make resume --project NEW_PROJECT`: it checks existing submissions without resending them, then may start remaining segments covered by the original approval. If the plan or image changes after approval, make a new project and obtain fresh approval. Never delete a job or blindly resubmit an uncertain request.

`waiting` / `awaiting_result` means the existing request still lacks a verified final receipt. Show a short progress update and keep polling that request, without asking to regenerate. For the first 120 seconds, an idle bot with only an initial reply is not itself a failure; explicit approval requests or a bot awaiting user input still stop promptly. After the grace period, `needs_attention` requires inspecting the existing response rather than blindly retrying. CLI exit code 2 represents a non-final state, not permission to submit again.

Template projects already attempt local packaging in `make run` / `resume` and return alignment status and warnings. Set `VOSK_MODEL_PATH` before running them. If the result matches current preferences, inspect and deliver it without a redundant render. For plain projects or changed preferences, read `docs/LOCAL_PACKAGING.md` and run:

```text
python -m dhp.cli make restyle --project NEW_PROJECT --request ORIGINAL_REQUEST --style CHOSEN_STYLE --title TITLE
```

Use the original intent and latest style/title, properly quoted; add `--asr-model MODEL_DIRECTORY` if needed. This reuses completed originals, preserves full normalized duration and submits no generation. A template project inherits its saved template; add `--template TEMPLATE_ID` when changing it. Disclose simple-caption fallback if setup or recognition is unreliable. For plain projects the earlier `make run` cut uses estimated captions and conservative tail trimming; deliver the final restyled output, not that earlier cut.

Inspect decoded representative frames and card transitions, and play the final video to check audible speech, readable captions, face/mouth obstruction and the ending. A QA file or successful ASR match alone does not prove lip-sync or speech accuracy. If playback or a check is unavailable, say what remains unverified. Deliver the playable final MP4 first, the SRT if available, and a short note on actual generation submissions, verifiable allowance/cost and any review needed; do not call unknown charges zero. Keep optional technical reports out of the main delivery unless requested. Preserve the burned-in AI label. A publication description still needs the label; publishing is a separate user action.

When the user says “换成知识讲解风格”, reuse the project and add `--template knowledge-share`; map the other supported templates similarly. For a showcase, use `--template product-demo --asset LOCAL_FILE`. With no stored showcase beats, the middle scene is estimated and needs playback review. A single JPG, PNG, WebP, MP4, MOV or WebM is supported; its own audio is muted. This changes presentation of existing content, not speech. A project must already have saved `three-point` beats to get its three timed cards; switching an old project without those beats yields a title and warning. For existing clips, make a manual component pack based on the actual spoken words if requested. Carry forward the latest title; omitting it uses the original plan title. Local rendering submits zero generation requests and needs no new provider payment approval. Incomplete jobs stop; never regenerate merely to change packaging.

For a free synthetic rehearsal, follow the `--dry-run` example in `README.md`: it creates test cards and tones, not real speech or a digital human.

## Component packaging of completed clips

When asked which effects are available, show `docs/COMPONENT_GALLERY.md`: eight actual silent GIFs, natural-language requests and examples. Prefer a complete template for first use. For individual components, read only the relevant `examples/components/` files and adapt their text, sources and times to the actual clip. These examples quote a specific pilot, not generic facts.

For content-aware local packaging, read `docs/LOCAL_PACKAGING.md`. Prefer `make restyle --project NEW_PROJECT --request "把这条做成知识分享"`: this automatically selects a promo, explainer or warm recipe and attempts local Vosk sentence matching, without writing a component timeline yourself. A completed old native job can use `--job-dir` instead. Reuse the ASR dependency and Chinese model from the one-time setup above; never silently switch to a paid service. Missing setup, mismatched words or low confidence produce estimated captions and a review warning. For a single-segment three-point plan, the three cards also fall back to script-length estimates; multi-segment fallback keeps only a title. Tell the user when this occurs. Recognizer timestamps are estimates, not forced word alignment or human approval. No media is uploaded and no generation is submitted.

Use the eight components through `--pack-file` when the user needs custom evidence, comparisons or a specific edit; this cannot be combined with `--request`. Prepare the JSON yourself using supplied facts and the completed original's actual duration. Keep `timing: estimated` until cue boundaries have been checked in playback. The explicit timeline preserves the full original duration. Do not infer product demonstrations or an emotional performance from packaging existing test dialogue. Inspect card transitions and readable text, then deliver the video.
