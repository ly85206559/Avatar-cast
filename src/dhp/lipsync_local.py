"""Local lip-sync extension point (NOT the default route).

This is intentionally a stub, not a fake implementation. To add a local
route, implement drive() behind the same LipSyncProvider interface and
register it in registry.py, for example:

  - MuseTalk / SadTalker / Hallo-class audio-driven models
  - requirements: a GPU machine, model weights, licence check first
  - judge it on the same Mandarin test audio as the API route, not on
    English demos, and on the same five QA dimensions (see docs/QA_BENCHMARK.md)

Do not weaken the API route's rules when adding a local route: cache key,
QA thresholds and the qa.json report stay the same whichever route runs.
"""


class LocalLipSyncProvider:
    def drive(self, *args, **kwargs):
        raise NotImplementedError(
            "Local lip-sync is an extension point, not yet implemented. "
            "Pick a model, check its licence and VRAM, implement drive() "
            "behind the LipSyncProvider interface, and register it in "
            "registry.py as 'local'. Until then, use the default "
            "'wavespeed-api' route (see docs/API_LIPSYNC.md).")
