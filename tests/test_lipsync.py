import pytest

from dhp.lipsync_api import ApiLipSyncConfig, ApiLipSyncProvider
from dhp.providers import Audio
from dhp.registry import DEFAULT_LIPSYNC_PROVIDER, get_lipsync_provider


def _audio():
    return Audio(path="https://example.invalid/s1.mp3", duration_sec=6.0,
                 sha256="abc", voice_id="v1")


def test_default_provider_is_api_first():
    assert DEFAULT_LIPSYNC_PROVIDER == "wavespeed-api"
    assert isinstance(get_lipsync_provider(), ApiLipSyncProvider)


def test_unknown_price_is_not_presented_as_free():
    p = ApiLipSyncProvider(ApiLipSyncConfig(rate_per_sec=None))
    q = p.estimate(6.0)
    assert "UNKNOWN" in q.notes


def test_dry_run_spends_nothing_and_needs_no_key():
    p = ApiLipSyncProvider(ApiLipSyncConfig(rate_per_sec=None), api_key="")
    manifest = p.dry_run("https://example.invalid/presenter.jpg", _audio())
    assert manifest["will_submit"] is False
    assert manifest["model"] == "avatar-omni-human-1.5"


def test_generate_refuses_without_live_price_confirmation():
    p = ApiLipSyncProvider(ApiLipSyncConfig(rate_per_sec=0.25), api_key="x")
    with pytest.raises(RuntimeError, match="confirm_live_price"):
        p.drive("https://example.invalid/presenter.jpg", _audio(), "out.mp4")


def test_local_provider_is_an_explicit_extension_point():
    local = get_lipsync_provider("local")
    with pytest.raises(NotImplementedError):
        local.drive()
