"""Lightweight unit checks that do not call Fubo."""

from datetime import datetime, timezone

from app.epg import build_xmltv
from app.fubo_client import Channel, Programme
from app.m3u import build_m3u


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


if __name__ == "__main__":
    test_build_m3u()
    test_build_xmltv()
    print("ok")
