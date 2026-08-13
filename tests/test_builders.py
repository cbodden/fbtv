"""Lightweight unit checks that do not call Fubo."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings, _load_credentials, _strip_wrapping_quotes, password_fingerprint
from app.epg import EpgCache, build_xmltv
from app.fubo_client import Channel, Programme
from app.m3u import build_m3u
from app.status import RuntimeState, build_snapshot, render_prometheus


def _settings(config_dir: Path) -> Settings:
    return Settings(
        fubo_user="u@example.com",
        fubo_pass="secret",
        host="0.0.0.0",
        port=7777,
        config_dir=config_dir,
        epg_cache_seconds=3600,
        epg_empty_cache_seconds=120,
        epg_days=2,
        credentials_source="test",
        drm_scan_on_start=False,
        drm_scan_concurrency=1,
        drm_scan_delay_ms=0,
        drm_scan_max_age_hours=24,
        drm_scan_interval_hours=0,
        stream_proxy=False,
        stream_proxy_max=3,
        ffmpeg_path="ffmpeg",
        admin_token="",
    )


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
    assert "tvg-chno" not in m3u
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
    assert stats["ttl_seconds"] == 60


def test_epg_empty_cache_uses_short_ttl() -> None:
    cache = EpgCache(ttl_seconds=3600, empty_ttl_seconds=0)
    cache.set("<tv/>", programme_count=0, channel_count=2)
    stats = cache.runtime_stats()
    assert stats["programme_count"] == 0
    assert stats["ttl_seconds"] == 0
    assert stats["cached"] is False
    assert cache.get() is None

    cache.set("<tv/>", programme_count=4, channel_count=2)
    stats = cache.runtime_stats()
    assert stats["ttl_seconds"] == 3600
    assert stats["cached"] is True
    assert cache.get() == "<tv/>"


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

    from app.fubo_client import FuboClient

    config_dir = tmp_path if tmp_path is not None else Path(
        __import__("tempfile").mkdtemp()
    )
    settings = _settings(config_dir)
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


def test_papi_program_cell_parsing() -> None:
    from app.fubo_client import FuboClient

    settings = _settings(Path(__import__("tempfile").mkdtemp()))
    client = FuboClient(settings)
    try:
        channels = [Channel(id="12345", call_sign="ESPN", name="ESPN")]
        components = [
            {
                "type": "channel-cell",
                "id": "12345",
                "components": [
                    {
                        "type": "program-cell",
                        "start_time": "2026-08-12T18:00:00.000Z",
                        "end_time": "2026-08-12T19:00:00.000Z",
                        "title": {"text": "SportsCenter"},
                        "subtitle": {"text": "Highlights"},
                    }
                ],
            }
        ]
        rich = {
            ("12345", "2026-08-12T18:00:00.000Z"): {
                "description": "Nightly sports news",
                "genres": ["Sports"],
                "normalizedGenres": ["Sports"],
            }
        }
        found = client._programmes_from_papi_components(
            components, {ch.id: ch for ch in channels}, rich_lookup=rich
        )
        assert len(found) == 1
        assert found[0].channel_id == "ESPN"
        assert found[0].title == "SportsCenter"
        assert found[0].description == "Nightly sports news"
        assert "Sports" in found[0].categories
    finally:
        client.close()


def test_epg_assets_parsing() -> None:
    from app.fubo_client import FuboClient

    settings = _settings(Path(__import__("tempfile").mkdtemp()))
    client = FuboClient(settings)
    try:
        channels = [Channel(id="16689", call_sign="ESPN", name="ESPN")]
        payload = {
            "response": [
                {
                    "type": "channelWithProgramAssets",
                    "data": {
                        "channel": {"id": 16689},
                        "programsWithAssets": [
                            {
                                "program": {
                                    "title": "SportsCenter",
                                    "shortDescription": "Highlights",
                                    "genres": [{"name": "Sports"}],
                                },
                                "assets": [
                                    {
                                        "accessRights": {
                                            "startTime": "2026-08-12T18:00:00.000Z",
                                            "endTime": "2026-08-12T19:00:00.000Z",
                                        }
                                    }
                                ],
                            }
                        ],
                    },
                }
            ]
        }
        found = client._programmes_from_epg_assets(
            payload, {ch.id: ch for ch in channels}
        )
        assert len(found) == 1
        assert found[0].channel_id == "ESPN"
        assert found[0].title == "SportsCenter"
        assert found[0].description == "Highlights"
        assert "Sports" in found[0].categories
    finally:
        client.close()


def test_epg_assets_match_station_id_and_call_sign() -> None:
    from app.fubo_client import FuboClient

    settings = _settings(Path(__import__("tempfile").mkdtemp()))
    client = FuboClient(settings)
    try:
        channels = [Channel(id="16689", call_sign="ESPN", name="ESPN")]
        program_block = {
            "program": {
                "title": "SportsCenter",
                "shortDescription": "Highlights",
                "genres": [{"name": "Sports"}],
            },
            "assets": [
                {
                    "accessRights": {
                        "startTime": "2026-08-12T18:00:00.000Z",
                        "endTime": "2026-08-12T19:00:00.000Z",
                    }
                }
            ],
        }
        by_station = {
            "response": [
                {
                    "type": "channelWithProgramAssets",
                    "data": {
                        "channel": {"stationId": 16689},
                        "programsWithAssets": [program_block],
                    },
                }
            ]
        }
        by_call = {
            "response": [
                {
                    "type": "channelWithProgramAssets",
                    "data": {
                        "channel": {"callSign": "ESPN"},
                        "programsWithAssets": [program_block],
                    },
                }
            ]
        }
        lookup = {ch.id: ch for ch in channels}
        station_found = client._programmes_from_epg_assets(by_station, lookup)
        call_found = client._programmes_from_epg_assets(by_call, lookup)
        assert len(station_found) == 1 and station_found[0].channel_id == "ESPN"
        assert len(call_found) == 1 and call_found[0].channel_id == "ESPN"
    finally:
        client.close()


def test_watch_head_does_not_tune() -> None:
    from unittest.mock import MagicMock

    from starlette.requests import Request

    from app import main as mainmod

    fake = MagicMock()
    mainmod.settings = _settings(Path(__import__("tempfile").mkdtemp()))
    mainmod.client = fake
    mainmod.epg_cache = EpgCache(ttl_seconds=60)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "HEAD",
        "scheme": "http",
        "path": "/watch/123",
        "raw_path": b"/watch/123",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    response = mainmod.watch("123", Request(scope))
    fake.watch.assert_not_called()
    assert response.status_code == 200
    assert response.media_type == "application/vnd.apple.mpegurl"


def test_watch_redirect_when_proxy_off() -> None:
    from unittest.mock import MagicMock

    from fastapi.responses import RedirectResponse
    from starlette.requests import Request

    from app import main as mainmod

    fake = MagicMock()
    fake.watch.return_value = "https://cdn.example/live.m3u8"
    mainmod.settings = _settings(Path(__import__("tempfile").mkdtemp()))
    mainmod.client = fake
    mainmod.epg_cache = EpgCache(ttl_seconds=60)
    mainmod.stream_proxy = None
    mainmod.runtime = RuntimeState()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/watch/123",
        "raw_path": b"/watch/123",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    response = mainmod.watch("123", Request(scope))
    assert isinstance(response, RedirectResponse)
    assert response.status_code == 302
    assert response.headers["location"] == "https://cdn.example/live.m3u8"
    assert mainmod.runtime.counters.watch_ok == 1


def test_watch_proxy_streams_mpegts() -> None:
    from unittest.mock import MagicMock

    from fastapi.responses import StreamingResponse
    from starlette.requests import Request

    from app import main as mainmod
    from app.stream_proxy import StreamProxy

    fake = MagicMock()
    fake.watch.return_value = "https://cdn.example/live.m3u8"
    cfg = _settings(Path(__import__("tempfile").mkdtemp()))
    # frozen dataclass — rebuild with proxy on
    from dataclasses import replace

    cfg = replace(cfg, stream_proxy=True, stream_proxy_max=2)
    proxy = StreamProxy(ffmpeg_path="ffmpeg", max_streams=2)
    proxy.iter_mpegts = lambda url: iter([b"tsdata", b"more"])  # type: ignore[method-assign]

    mainmod.settings = cfg
    mainmod.client = fake
    mainmod.epg_cache = EpgCache(ttl_seconds=60)
    mainmod.stream_proxy = proxy
    mainmod.runtime = RuntimeState()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/watch/123",
        "raw_path": b"/watch/123",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    response = mainmod.watch("123", Request(scope))
    assert isinstance(response, StreamingResponse)
    assert response.media_type == "video/mp2t"
    assert mainmod.runtime.counters.watch_ok == 1

    head_scope = {**scope, "method": "HEAD"}
    head = mainmod.watch("123", Request(head_scope))
    fake.watch.assert_called_once()
    assert head.status_code == 200
    assert head.media_type == "video/mp2t"


def test_watch_proxy_at_capacity() -> None:
    from unittest.mock import MagicMock

    from fastapi import HTTPException
    from starlette.requests import Request

    from app import main as mainmod
    from app.stream_proxy import StreamProxy
    from dataclasses import replace

    fake = MagicMock()
    fake.watch.return_value = "https://cdn.example/live.m3u8"
    cfg = replace(
        _settings(Path(__import__("tempfile").mkdtemp())),
        stream_proxy=True,
        stream_proxy_max=1,
    )
    proxy = StreamProxy(ffmpeg_path="ffmpeg", max_streams=1)
    proxy._active = 1  # noqa: SLF001 — force full

    mainmod.settings = cfg
    mainmod.client = fake
    mainmod.epg_cache = EpgCache(ttl_seconds=60)
    mainmod.stream_proxy = proxy
    mainmod.runtime = RuntimeState()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/watch/123",
        "raw_path": b"/watch/123",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    try:
        mainmod.watch("123", Request(scope))
        raise AssertionError("expected HTTPException")
    except HTTPException as exc:
        assert exc.status_code == 503
    assert mainmod.runtime.counters.watch_error == 1


def test_stream_proxy_busy_raises() -> None:
    from app.stream_proxy import StreamProxy, StreamProxyBusy

    proxy = StreamProxy(ffmpeg_path="ffmpeg", max_streams=1)
    proxy._active = 1  # noqa: SLF001
    try:
        list(proxy.iter_mpegts("https://example/x.m3u8"))
        raise AssertionError("expected StreamProxyBusy")
    except StreamProxyBusy:
        pass
    assert proxy.runtime_stats()["active"] == 1


def test_drm_overrides_file_and_deny_wins() -> None:
    import tempfile

    from app.drm_overrides import load_drm_overrides

    config_dir = Path(tempfile.mkdtemp())
    (config_dir / "drm_overrides.json").write_text(
        json.dumps(
            {
                "deny_station_ids": ["1", "2"],
                "allow_station_ids": ["2", "3"],
                "deny_call_signs": ["BAD"],
                "allow_call_signs": ["BAD", "GOOD"],
            }
        ),
        encoding="utf-8",
    )
    overrides = load_drm_overrides(config_dir)
    assert overrides.is_denied(station_id="1")
    assert overrides.is_denied(station_id="2")  # deny wins
    assert not overrides.is_allowed(station_id="2")
    assert overrides.is_allowed(station_id="3")
    assert overrides.is_denied(station_id="9", call_sign="BAD")
    assert not overrides.is_allowed(station_id="9", call_sign="BAD")
    assert overrides.is_allowed(station_id="9", call_sign="GOOD")


def test_drm_allow_keeps_learned_station_in_lineup() -> None:
    from app.fubo_client import FuboClient
    from app.drm_overrides import DrmOverrides

    config_dir = Path(__import__("tempfile").mkdtemp())
    settings = _settings(config_dir)
    client = FuboClient(settings)
    try:
        client._drm_overrides = DrmOverrides(  # noqa: SLF001
            allow_ids=frozenset({"99"}),
            source="test",
        )
        client._drm_learned_ids.add("99")
        client._drm_learned_ids.add("88")
        keep = Channel(id="99", call_sign="KEEP", name="Keep")
        drop = Channel(id="88", call_sign="DROP", name="Drop")
        ok = Channel(id="1", call_sign="OK", name="Ok")

        def fake_subs() -> dict[str, Channel]:
            return {"99": keep, "88": drop, "1": ok}

        client._channels_from_subscriptions = fake_subs  # type: ignore[method-assign]
        channels = client.channels(force=True)
        ids = {ch.id for ch in channels}
        assert "99" in ids
        assert "1" in ids
        assert "88" not in ids

        client.mark_drm_station("99", via="test")
        assert "99" not in client._drm_learned_ids
    finally:
        client.close()


def test_drm_deny_drops_station() -> None:
    from app.fubo_client import FuboClient
    from app.drm_overrides import DrmOverrides

    config_dir = Path(__import__("tempfile").mkdtemp())
    client = FuboClient(_settings(config_dir))
    try:
        client._drm_overrides = DrmOverrides(  # noqa: SLF001
            deny_ids=frozenset({"7"}),
            deny_call_signs=frozenset({"NOPE"}),
            source="test",
        )
        stations: dict = {}
        client._add_station(
            stations,
            station_id="7",
            call_sign="X",
            name="Denied Id",
            logo=None,
            network_type=None,
            group="basic",
            source=None,
            raw={},
        )
        client._add_station(
            stations,
            station_id="8",
            call_sign="NOPE",
            name="Denied Call",
            logo=None,
            network_type=None,
            group="basic",
            source=None,
            raw={},
        )
        client._add_station(
            stations,
            station_id="9",
            call_sign="YES",
            name="Ok",
            logo=None,
            network_type=None,
            group="basic",
            source=None,
            raw={},
        )
        assert "7" not in stations and "8" not in stations
        assert "9" in stations
    finally:
        client.close()


def test_drm_scan_persists_and_skips_when_fresh() -> None:
    from app.fubo_client import FuboClient

    config_dir = Path(__import__("tempfile").mkdtemp())
    settings = _settings(config_dir)
    client = FuboClient(settings)
    try:
        playable = Channel(id="1", call_sign="OK", name="Playable")
        drm_ch = Channel(id="20360", call_sign="DRMCH", name="DRM Channel")

        def fake_lineup(*, include_learned_drm: bool) -> list[Channel]:
            return [playable, drm_ch]

        client._lineup_channels = fake_lineup  # type: ignore[method-assign]
        client.probe_asset = (  # type: ignore[method-assign]
            lambda channel_id: "drm" if str(channel_id) == "20360" else "ok"
        )

        result = client.scan_drm(force=True)
        assert result["status"] == "completed"
        assert result["drm"] == 1
        assert result["playable"] == 1
        assert "20360" in client._drm_learned_ids
        assert "1" in client._drm_playable
        skip_file = config_dir / "drm_skipped.json"
        payload = json.loads(skip_file.read_text(encoding="utf-8"))
        assert "20360" in payload["station_ids"]
        assert payload.get("last_scan_at")

        skipped = client.scan_drm(force=False)
        assert skipped["status"] == "skipped"
        assert skipped["skipped"] is True
    finally:
        client.close()


def test_status_warms_channels() -> None:
    from unittest.mock import MagicMock

    from app import main as mainmod

    fake = MagicMock()
    fake.channels.return_value = []
    fake.runtime_stats.return_value = {"channel_count": 0, "signed_in": False}
    mainmod.settings = _settings(Path(__import__("tempfile").mkdtemp()))
    mainmod.client = fake
    mainmod.epg_cache = EpgCache(ttl_seconds=60)
    mainmod.stream_proxy = None
    mainmod.runtime = RuntimeState()

    mainmod.status_json()
    fake.channels.assert_called_once()

    fake.channels.reset_mock()
    mainmod.metrics()
    fake.channels.assert_not_called()


def test_admin_token_gate() -> None:
    from dataclasses import replace
    from unittest.mock import MagicMock

    from fastapi import HTTPException

    from app import main as mainmod

    fake = MagicMock()
    fake._scan_running = False
    fake.runtime_stats.return_value = {
        "drm_scan_running": False,
        "drm_scan_started_at": None,
        "drm_scan_finished_at": None,
        "drm_scan_last_result": None,
        "drm_learned_count": 0,
        "drm_playable_count": 0,
        "drm_updated_at": None,
        "drm_scan_on_start": False,
        "drm_scan_interval_hours": 0,
        "drm_scan_max_age_hours": 24,
        "drm_scan_concurrency": 1,
        "drm_scan_delay_ms": 0,
    }
    cfg = replace(_settings(Path(__import__("tempfile").mkdtemp())), admin_token="")
    mainmod.settings = cfg
    mainmod.client = fake
    mainmod.epg_cache = EpgCache(ttl_seconds=60)

    # Open when ADMIN_TOKEN empty
    assert mainmod.drm_scan_status()["running"] is False

    mainmod.settings = replace(cfg, admin_token="s3cret")
    try:
        mainmod.drm_scan_status()
        raise AssertionError("expected 401")
    except HTTPException as exc:
        assert exc.status_code == 401

    assert mainmod.drm_scan_status(authorization="Bearer s3cret")["running"] is False
    assert mainmod.drm_scan_status(x_admin_token="s3cret")["running"] is False

    try:
        mainmod.drm_scan_start(force=True)
        raise AssertionError("expected 401")
    except HTTPException as exc:
        assert exc.status_code == 401

    started = mainmod.drm_scan_start(force=True, x_admin_token="s3cret")
    assert started["status"] == "started"


def test_ready_and_health() -> None:
    import os

    from app import main as mainmod
    from app.config import credentials_are_configured
    from fastapi.responses import JSONResponse

    tmp = Path(__import__("tempfile").mkdtemp())
    (tmp / "credentials.env").write_text(
        "FUBO_USER=u@example.com\nFUBO_PASS=secret\n",
        encoding="utf-8",
    )
    assert credentials_are_configured(tmp) is True

    empty = Path(__import__("tempfile").mkdtemp())
    env_keys = (
        "FUBO_USER",
        "FUBO_PASS",
        "FUBO_PASS_B64",
        "FUBO_USER_FILE",
        "FUBO_PASS_FILE",
    )
    saved = {k: os.environ.pop(k, None) for k in env_keys}
    try:
        assert credentials_are_configured(empty) is False
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value

    mainmod.settings = None
    not_ready = mainmod.ready()
    assert isinstance(not_ready, JSONResponse)
    assert not_ready.status_code == 503

    mainmod.settings = _settings(tmp)
    ready = mainmod.ready()
    assert isinstance(ready, JSONResponse)
    assert ready.status_code == 200
    import json as _json

    assert _json.loads(ready.body) == {
        "status": "ready",
        "version": mainmod.__version__,
    }
    assert mainmod.health()["status"] == "ok"
