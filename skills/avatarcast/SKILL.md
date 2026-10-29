---
name: avatarcast
description: Run and inspect AvatarCast's offline digital-human video workflow rehearsal from a script and brief.
---

# AvatarCast

Use the AvatarCast repository and its CLI for an offline workflow rehearsal. Confirm that Python, FFmpeg, and ffprobe are available. Run from the repository root, with the `src` directory on Python's import path, or install the project locally.

Given a script JSON and brief JSON, run:

```text
python -m dhp.cli SCRIPT --brief BRIEF --dry-run --output-dir OUTPUT --cache-dir CACHE
```

The brief must set `duration_target_sec` to 30–60; the script must contain at least two segments. Use a new or empty output directory separate from the cache directory. To reuse cached segments, select a new output directory and keep the same cache directory. The existing example files demonstrate the input format. Inspect `qa.json`, the video, and the SRT before reporting the result. Report cache hits and simulated costs separately from actual spending.

The dry-run uses synthetic tones and labeled test cards, with captions burned into the video and also saved as SRT. Its scores, retry failures, and prices are simulated. It does not generate speech, perform real lip sync, or establish real video quality. Never describe its output as a real digital-human video. The current CLI is not an end-to-end real-provider workflow.

For real API generation, use only inputs the user is authorized to use. Before any paid request, obtain the required credentials and public media URLs, verify the current price for the specific request, and obtain explicit authorization for that cost. Do not infer approval from a dry-run. Follow `docs/API_LIPSYNC.md` for the current adapter and avoid blindly resubmitting an uncertain request.
