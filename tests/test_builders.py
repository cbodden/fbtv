"""Lightweight unit checks that do not call Fubo."""

from datetime import datetime, timezone

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


if __name__ == "__main__":
    test_build_m3u()
    test_build_xmltv()
    test_epg_cache_stats()
    test_prometheus_snapshot()
    print("ok")
