"""Scheduled DRM sweeps re-check learned DRM stations once their check is stale.

Live 2026-11-10: BTN (learned DRM on 2026-08-13) was clear again, BTN2 had gone DRM.
Before this change only ``force=true`` re-probed learned stations, so BTN stayed
hidden from the playlist indefinitely.
"""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from app.fubo.client import FuboClient
from app.fubo.models import Channel
from tests.test_auth_session import _settings

BTN = Channel(id="71605", call_sign="BTN", name="Big Ten Network")
BTN2 = Channel(id="84686", call_sign="BTN2", name="Big Ten Network Alternate 2")
FNC = Channel(id="70522", call_sign="FNCHD", name="FOX News Channel")
HOUR = 3600


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _client(tmp_path: Path, outcomes: dict[str, str], *, max_age_h: int = 24) -> tuple[FuboClient, list[str]]:
    client = FuboClient(replace(_settings(tmp_path), drm_scan_max_age_hours=max_age_h))
    probed: list[str] = []
    def lineup(*, include_learned_drm: bool) -> list[Channel]:
        # Same contract as the real _lineup_channels.
        chans = [BTN, BTN2, FNC]
        if include_learned_drm:
            return chans
        return [ch for ch in chans if ch.id not in client._drm_learned_ids]

    client._lineup_channels = lineup  # type: ignore[method-assign]

    def probe(channel_id: str) -> str:
        probed.append(str(channel_id))
        return outcomes[str(channel_id)]

    client.probe_asset = probe  # type: ignore[method-assign]
    return client, probed


def _learn(client: FuboClient, ch: Channel, *, checked_at: float | None) -> None:
    client._drm_learned_ids.add(ch.id)
    client._drm_records[ch.id] = {"drm": True, "via": "scan", "call_sign": ch.call_sign}
    if checked_at is not None:
        client._drm_records[ch.id]["checked_at"] = _iso(checked_at)


def test_stale_learned_drm_station_is_rechecked_and_restored(tmp_path: Path) -> None:
    client, probed = _client(tmp_path, {"71605": "ok", "84686": "drm", "70522": "drm"})
    now = time.time()
    try:
        _learn(client, BTN, checked_at=now - 25 * HOUR)  # stale: re-probe
        _learn(client, FNC, checked_at=now - 1 * HOUR)  # fresh: leave alone
        client._channels_cache = [BTN2]

        result = client.scan_drm(force=False)

        assert result["status"] == "completed"
        assert sorted(probed) == ["71605", "84686"]
        assert result["rechecked_drm"] == 1
        assert "71605" not in client._drm_learned_ids  # BTN back in the lineup
        assert "71605" in client._drm_playable
        assert "70522" in client._drm_learned_ids  # FNC untouched
        assert "84686" in client._drm_learned_ids  # BTN2 newly DRM
        assert client._channels_cache is None  # playlist rebuilds
    finally:
        client.close()


def test_reconfirmed_drm_is_not_rechecked_again_within_max_age(tmp_path: Path) -> None:
    client, probed = _client(tmp_path, {"71605": "drm", "84686": "ok", "70522": "ok"})
    try:
        _learn(client, BTN, checked_at=time.time() - 25 * HOUR)
        client.scan_drm(force=False)
        assert "71605" in probed and "71605" in client._drm_learned_ids

        probed.clear()
        client._drm_last_scan_at = time.time() - 25 * HOUR  # let the next sweep run
        client.scan_drm(force=False)
        assert "71605" not in probed  # checked_at was refreshed by the re-check
    finally:
        client.close()


def test_learned_station_without_checked_at_is_rechecked(tmp_path: Path) -> None:
    client, probed = _client(tmp_path, {"71605": "ok", "84686": "ok", "70522": "ok"})
    try:
        _learn(client, BTN, checked_at=None)  # e.g. legacy list-only skip file
        client.scan_drm(force=False)
        assert "71605" in probed
    finally:
        client.close()


def test_max_age_zero_rechecks_every_learned_station(tmp_path: Path) -> None:
    client, probed = _client(tmp_path, {"71605": "drm", "84686": "ok", "70522": "drm"}, max_age_h=0)
    try:
        _learn(client, BTN, checked_at=time.time() - 60)
        _learn(client, FNC, checked_at=time.time() - 60)
        client.scan_drm(force=False)
        assert sorted(probed) == ["70522", "71605", "84686"]
    finally:
        client.close()


def test_forced_scan_rechecks_all_learned_regardless_of_age(tmp_path: Path) -> None:
    client, probed = _client(tmp_path, {"71605": "drm", "84686": "ok", "70522": "drm"})
    try:
        _learn(client, FNC, checked_at=time.time() - 60)
        result = client.scan_drm(force=True)
        assert "70522" in probed
        assert result["rechecked_drm"] == 1
    finally:
        client.close()
