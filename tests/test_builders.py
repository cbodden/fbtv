"""Lightweight unit checks that do not call Fubo."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.config import _load_credentials, _strip_wrapping_quotes
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


if __name__ == "__main__":
    test_build_m3u()
    test_build_xmltv()
    test_epg_cache_stats()
    test_prometheus_snapshot()
    test_strip_wrapping_quotes()
    test_credentials_file_beats_env()
    test_credentials_json()
    print("ok")
