"""/epg is fetched in time chunks (memory) and parsed against a real response shape."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from app.fubo.models import Channel
from app.fubo.schedule import EPG_CHUNK_HOURS
from tests.test_client_errors import _client

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "epg_assets_wcbs.json").read_text())
WCBS = Channel(id="16689", call_sign="WCBS", name="CBS")


def _parse_window(request: httpx.Request) -> tuple[datetime, datetime]:
    def ts(name: str) -> datetime:
        return datetime.fromisoformat(request.url.params[name].replace("Z", "+00:00"))

    return ts("startTime"), ts("endTime")


def _payload_at(start: datetime, title: str = "Let's Make a Deal") -> dict:
    """The real fixture row, moved to ``start`` (one hour long)."""
    payload = copy.deepcopy(FIXTURE)
    item = payload["response"][0]["data"]["programsWithAssets"][0]
    item["program"]["title"] = title
    rights = item["assets"][0]["accessRights"]
    rights["startTime"] = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    rights["endTime"] = (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return payload


def test_real_epg_fixture_maps_to_lineup(tmp_path: Path) -> None:
    client = _client(tmp_path, lambda _r: httpx.Response(404), token="tok")
    try:
        found = client._programmes_from_epg_assets(FIXTURE, {WCBS.id: WCBS})
    finally:
        client.close()
    assert len(found) == 1
    prog = found[0]
    assert (prog.channel_id, prog.title) == ("WCBS", "Let's Make a Deal")
    assert prog.start == datetime(2026, 11, 10, 15, tzinfo=timezone.utc)
    assert prog.stop == datetime(2026, 11, 10, 16, tzinfo=timezone.utc)


def test_epg_requested_in_bounded_chunks(tmp_path: Path) -> None:
    windows: list[tuple[datetime, datetime]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path != "/epg":
            return httpx.Response(404)
        s, e = _parse_window(request)
        windows.append((s, e))
        return httpx.Response(200, json=_payload_at(s, title=f"Show {len(windows)}"))

    start = datetime(2026, 11, 10, 14, tzinfo=timezone.utc)
    end = start + timedelta(hours=49)
    client = _client(tmp_path, handler, token="tok")
    try:
        found = client._fetch_epg_assets_programmes(start, end, {WCBS.id: WCBS})
    finally:
        client.close()

    # Contiguous, non-overlapping windows covering the full range, none over the cap.
    assert windows[0][0] == start and windows[-1][1] == end
    assert all(a[1] == b[0] for a, b in zip(windows, windows[1:]))
    assert all(e - s <= timedelta(hours=EPG_CHUNK_HOURS) for s, e in windows)
    assert len(windows) == 9  # 49h / 6h
    assert len(found) == 9


def test_failed_chunk_falls_back_then_skips(tmp_path: Path) -> None:
    """Enriched call fails → plain /epg for that chunk; a fully failed chunk is skipped."""
    start = datetime(2026, 11, 10, 0, tzinfo=timezone.utc)
    calls: list[tuple[datetime, bool]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        s, _ = _parse_window(request)
        enriched = "enrichments" in request.url.params
        calls.append((s, enriched))
        chunk = int((s - start) / timedelta(hours=EPG_CHUNK_HOURS))
        if chunk == 0 and enriched:
            return httpx.Response(500, text="enrichment down")
        if chunk == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json=_payload_at(s))

    client = _client(tmp_path, handler, token="tok")
    try:
        found = client._fetch_epg_assets_programmes(
            start, start + timedelta(hours=18), {WCBS.id: WCBS}
        )
    finally:
        client.close()

    assert [p.start for p in found] == [start, start + timedelta(hours=12)]
    assert (start, False) in calls  # plain fallback used for chunk 0


def test_schedule_dedupes_programme_spanning_chunks(tmp_path: Path) -> None:
    """A show straddling a chunk boundary is returned by both chunks but listed once."""
    boundary_show = datetime(2026, 11, 10, 5, 30, tzinfo=timezone.utc)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path != "/epg":
            return httpx.Response(404)
        return httpx.Response(200, json=_payload_at(boundary_show))

    client = _client(tmp_path, handler, token="tok")
    try:
        found = client.schedule([WCBS], days=1)
    finally:
        client.close()

    assert len(found) == 1
    assert found[0].start == boundary_show
