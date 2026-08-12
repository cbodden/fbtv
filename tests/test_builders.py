"""Lightweight unit checks that do not call Fubo."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.config import _load_credentials, _strip_wrapping_quotes, password_fingerprint
from app.epg import EpgCache, build_xmltv
from app.fubo_client import Channel, Programme
from app.m3u import build_m3u
from app.status import RuntimeState, build_snapshot, render_prometheus


def test_build_m3u() -> None:
    channels = [
        Channel(
            id="123",
            call_sign="ESPN",
            name="ESPN",
            logo="https://example.com/espn.png",
            groups=["fubotv-basic"],
        )
    ]
    m3u = build_m3u(channels, "http://localhost:7777")
    assert "#EXTM3U" in m3u
    assert 'tvg-id="ESPN"' in m3u
    assert "http://localhost:7777/watch/123" in m3u


def test_build_xmltv() -> None:
    channels = [Channel(id="123", call_sign="ESPN", name="ESPN")]
    programmes = [
        Programme(
            channel_id="ESPN",
            title="SportsCenter",
            start=datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc),
            stop=datetime(2026, 8, 6, 13, 0, tzinfo=timezone.utc),
            description="Highlights",
            categories=["Sports"],
        )
    ]
    xml = build_xmltv(channels, programmes)
    assert 'channel id="ESPN"' in xml
    assert "<title" in xml and "SportsCenter" in xml
    assert "20260806120000 +0000" in xml


def test_epg_cache_stats() -> None:
    cache = EpgCache(ttl_seconds=60)
    assert cache.runtime_stats()["cached"] is False
    cache.set("<tv/>", programme_count=3, channel_count=2)
    stats = cache.runtime_stats()
    assert stats["cached"] is True
    assert stats["programme_count"] == 3
    assert stats["channel_count"] == 2


def test_prometheus_snapshot() -> None:
    runtime = RuntimeState()
    runtime.counters.watch_ok = 2
    snap = build_snapshot(
        version="1.0.0",
        runtime=runtime,
        fubo_stats={
            "signed_in": True,
            "channel_count": 10,
            "drm_skipped_count": 4,
            "token_age_seconds": 1,
            "token_ttl_remaining_seconds": 100,
            "channels_cache_age_seconds": 1,
            "channels_source": "subscriptions",
        },
        epg_stats={
            "cached": True,
            "age_seconds": 5,
            "ttl_seconds": 3600,
            "programme_count": 7,
            "channel_count": 10,
        },
        host="0.0.0.0",
        port=7777,
    )
    text = render_prometheus(snap)
    assert "fubo_bridge_up 1" in text
    assert "fubo_bridge_channels 10" in text
    assert "fubo_bridge_watch_ok_total 2" in text
    assert 'fubo_bridge_info{version="1.0.0"} 1' in text


def test_strip_wrapping_quotes() -> None:
    assert _strip_wrapping_quotes("'ab$cd'") == ("ab$cd", True)
    assert _strip_wrapping_quotes('"ab$cd"') == ("ab$cd", True)
    assert _strip_wrapping_quotes("ab$cd") == ("ab$cd", False)


def test_credentials_file_beats_env(tmp_path: Path | None = None) -> None:
    config_dir = tmp_path if tmp_path is not None else Path(
        __import__("tempfile").mkdtemp()
    )
    (config_dir / "credentials.env").write_text(
        "FUBO_USER=you@example.com\nFUBO_PASS=ab$cd!ef\n",
        encoding="utf-8",
    )
    old_user, old_pass = os.environ.get("FUBO_USER"), os.environ.get("FUBO_PASS")
    os.environ["FUBO_USER"] = "wrong@example.com"
    os.environ["FUBO_PASS"] = "wrong"
    try:
        user, password, source, _ = _load_credentials(config_dir)
    finally:
        if old_user is None:
            os.environ.pop("FUBO_USER", None)
        else:
            os.environ["FUBO_USER"] = old_user
        if old_pass is None:
            os.environ.pop("FUBO_PASS", None)
        else:
            os.environ["FUBO_PASS"] = old_pass
    assert user == "you@example.com"
    assert password == "ab$cd!ef"
    assert source.endswith("credentials.env")


def test_credentials_json(tmp_path: Path | None = None) -> None:
    config_dir = tmp_path if tmp_path is not None else Path(
        __import__("tempfile").mkdtemp()
    )
    (config_dir / "credentials.json").write_text(
        json.dumps({"FUBO_USER": "a@b.com", "FUBO_PASS": "p$ass"}),
        encoding="utf-8",
    )
    user, password, source, _ = _load_credentials(config_dir)
    assert user == "a@b.com"
    assert password == "p$ass"
    assert source.endswith("credentials.json")


def test_credentials_pass_b64(tmp_path: Path | None = None) -> None:
    import base64

    config_dir = tmp_path if tmp_path is not None else Path(
        __import__("tempfile").mkdtemp()
    )
    secret = "ab$cd!ef"
    (config_dir / "credentials.env").write_text(
        "FUBO_USER=you@example.com\n"
        f"FUBO_PASS_B64={base64.b64encode(secret.encode()).decode()}\n",
        encoding="utf-8",
    )
    user, password, source, _ = _load_credentials(config_dir)
    assert user == "you@example.com"
    assert password == secret
    assert source.endswith("credentials.env")
    fp, classes = password_fingerprint(secret)
    assert len(fp) == 12
    assert "S" in classes


def test_mark_drm_station_removes_from_cache_and_persists(
    tmp_path: Path | None = None,
) -> None:
    import time

    from app.config import Settings
    from app.fubo_client import FuboClient

    config_dir = tmp_path if tmp_path is not None else Path(
        __import__("tempfile").mkdtemp()
    )
    settings = Settings(
        fubo_user="u@example.com",
        fubo_pass="secret",
        host="0.0.0.0",
        port=7777,
        config_dir=config_dir,
        epg_cache_seconds=3600,
        epg_days=2,
        credentials_source="test",
    )
    client = FuboClient(settings)
    try:
        client._channels_cache = [
            Channel(id="20360", call_sign="DRMCH", name="DRM Channel"),
            Channel(id="1", call_sign="OK", name="Playable"),
        ]
        client._channels_cache_at = time.time()
        client.mark_drm_station("20360")
        assert [ch.id for ch in client._channels_cache or []] == ["1"]
        assert "20360" in client._drm_learned_ids
        stats = client.runtime_stats()
        assert stats["drm_learned_count"] == 1
        assert stats["channel_count"] == 1
        skip_file = config_dir / "drm_skipped.json"
        assert skip_file.is_file()
        payload = json.loads(skip_file.read_text(encoding="utf-8"))
        assert "20360" in payload["station_ids"]

        # Restart client: learned IDs reload from disk.
        client2 = FuboClient(settings)
        try:
            assert "20360" in client2._drm_learned_ids
        finally:
            client2.close()
    finally:
        client.close()


def test_is_drm_channel_flags() -> None:
    from app.fubo_client import FuboClient

    assert FuboClient._is_drm_channel({"drmProtected": True, "callSign": "FOO"})
    assert FuboClient._is_drm_channel({"source": "Disney", "callSign": "FOO"})
    assert not FuboClient._is_drm_channel({"callSign": "ESPN", "source": "other"})


if __name__ == "__main__":
    test_build_m3u()
    test_build_xmltv()
    test_epg_cache_stats()
    test_prometheus_snapshot()
    test_strip_wrapping_quotes()
    test_credentials_file_beats_env()
    test_credentials_json()
    test_credentials_pass_b64()
    test_mark_drm_station_removes_from_cache_and_persists()
    test_is_drm_channel_flags()
    print("ok")
