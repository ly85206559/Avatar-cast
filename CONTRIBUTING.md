# Contributing to AvatarCast

## The one rule that matters most

Do not relabel a proxy as the real thing. A heuristic is a heuristic, an
aHash similarity is not a face embedding, and a synthetic demo clip is not
lip-sync. If a score, a demo, or a README claim was not measured on the
stated input, label it `not_evaluated` instead of filling in a number.

## Quick setup (no spending)

```bash
pip install -e ".[test]"
python -m pytest -q
dhp examples/demo-script.json
dhp demo --out outputs/demo
```

`dhp demo` runs entirely offline: it validates the demo script, builds a
zero-cost quote-gate plan, assembles synthetic colour clips with
`render.py`, and writes a `qa.json` whose segments are all `warn` because
lip-sync, face consistency, and ASR are explicitly *not evaluated* on
placeholder video. That is the intended result for a demo, not a failure
to hide.

System requirement: `ffmpeg`/`ffprobe` on PATH. Optional: `vosk` plus a
Vosk model directory (`VOSK_MODEL_PATH`) for real ASR; without a model the
ASR adapter raises instead of returning a fake transcript.

## Spending rules

- Never submit a paid generation from a test, a demo, or CI.
- The API lip-sync path (`scripts/api_lipsync_run.py`) refuses to submit
  unless a live price was confirmed and `--confirm` is passed. Keep it
  that way; do not add an auto-retry on submit.
- Do not commit API keys, `.env` files, model weights, or generated
  media (`.mp4`/`.mp3`/`.wav` are gitignored).

## What a good PR contains

- A test for the changed behaviour (contract, cache, pipeline, component,
  render, or scorer — whichever the change touches).
- A CHANGELOG entry, including an honest "still not implemented" note
  when the PR adds an interface but not the underlying model.
- Benchmark numbers only when they were measured on the fixed test set
  in `examples/`; otherwise say so. See `benchmark/baseline-v0.3.json`
  for the format and provenance of the current baseline.

## Compliance

Only use voices and faces you own or are authorised to use. Generated
output must carry an "AI digital-human performance" label. See
`docs/COMPLIANCE.md` before adding a new model, dataset, or asset.
