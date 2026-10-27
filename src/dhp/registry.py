"""Provider registry. Default route is API-first; local stays pluggable.

Switching routes is a config change, not a code rewrite:
    provider = get_lipsync_provider("wavespeed-api")   # default
    provider = get_lipsync_provider("local")           # extension point
"""

from __future__ import annotations

from .lipsync_api import ApiLipSyncConfig, ApiLipSyncProvider
from .lipsync_local import LocalLipSyncProvider

DEFAULT_LIPSYNC_PROVIDER = "wavespeed-api"


def get_lipsync_provider(name: str = DEFAULT_LIPSYNC_PROVIDER,
                         config: ApiLipSyncConfig | None = None):
    if name == "wavespeed-api":
        return ApiLipSyncProvider(config)
    if name == "local":
        return LocalLipSyncProvider()
    raise ValueError(f"Unknown lip-sync provider: {name!r}. "
                     f"Known: 'wavespeed-api' (default), 'local' (extension point).")
