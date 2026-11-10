"""Overlapping listings on one channel resolve to a single timeline (newest wins).

Cases mirror live /epg data seen 2026-11-10: AMTEVE (stale "Programa pagado"
placeholders under the real shows), FUBOCRM (same episodes re-published a few
seconds off), SECPLUS (concurrent events).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from app.fubo.models import Programme
from app.fubo.schedule import MIN_TRIMMED_PROGRAMME, resolve_overlaps
from tests.test_client_errors import _client
from tests.test_epg_chunked import FIXTURE, WCBS

T0 = datetime(2026, 11, 10, 16, tzinfo=timezone.utc)


def _p(ch: str, title: str, start: str, stop: str, rev: int) -> Programme:
    def at(hms: str) -> datetime:
        h, m, *s = (int(x) for x in hms.split(":"))
        return T0.replace(hour=h, minute=m, second=s[0] if s else 0)

    return Programme(channel_id=ch, title=title, start=at(start), stop=at(stop), revision=rev)


def _timeline(progs: list[Programme]) -> list[tuple[str, str, str]]:
    return [(p.title, f"{p.start:%H:%M:%S}", f"{p.stop:%H:%M:%S}") for p in progs]


def test_stale_placeholders_lose_to_newer_schedule() -> None:
    progs = [
        _p("AMTEVE", "America Noticias 8 Pm", "16:00", "17:00", 286843352),
        _p("AMTEVE", "Programa pagado", "16:30", "17:00", 284499601),
        _p("AMTEVE", "Programa pagado", "17:00", "17:30", 284499598),
        _p("AMTEVE", "Imperio", "17:00", "18:00", 286843353),
        _p("AMTEVE", "America Noticias 6pm", "19:00", "20:00", 286290510),
        _p("AMTEVE", "America Noticias 8 Pm", "19:00", "20:00", 286843355),
    ]
    assert _timeline(resolve_overlaps(progs)) == [
        ("America Noticias 8 Pm", "16:00:00", "17:00:00"),
        ("Imperio", "17:00:00", "18:00:00"),
        ("America Noticias 8 Pm", "19:00:00", "20:00:00"),
    ]


def test_republished_episodes_seconds_apart_collapse_to_newest() -> None:
    progs = [
        _p("FUBOCRM", "Sign Here", "16:34:00", "17:04:00", 285534944),
        _p("FUBOCRM", "Sign Here", "16:34:42", "17:04:49", 285487397),
        _p("FUBOCRM", "Paintball", "17:04:00", "17:35:00", 285534256),
        _p("FUBOCRM", "Paintball", "17:04:49", "17:35:01", 285487398),
    ]
    assert _timeline(resolve_overlaps(progs)) == [
        ("Sign Here", "16:34:00", "17:04:00"),
        ("Paintball", "17:04:00", "17:35:00"),
    ]


def test_older_listing_trimmed_around_newer_or_dropped_if_too_short() -> None:
    progs = [
        _p("SECPLUS", "Auburn vs Furman", "17:00:01", "19:00", 285374704),
        _p("SECPLUS", "Missouri Football Press Conference", "18:00", "19:00", 285378389),
        _p("SECPLUS", "South Carolina Football Press Conference", "18:00", "19:00", 285378390),
        # Older and covered by a newer listing except for 4 minutes: dropped.
        _p("SECPLUS", "Pregame", "19:56", "20:30", 1),
        _p("SECPLUS", "Late Game", "20:00", "21:00", 2),
    ]
    assert _timeline(resolve_overlaps(progs)) == [
        ("Auburn vs Furman", "17:00:01", "18:00:00"),
        ("South Carolina Football Press Conference", "18:00:00", "19:00:00"),
        ("Late Game", "20:00:00", "21:00:00"),
    ]
    assert timedelta(minutes=4) < MIN_TRIMMED_PROGRAMME


def test_trim_keeps_longest_free_stretch_when_newer_lands_in_middle() -> None:
    progs = [
        _p("CH", "Movie", "16:00", "19:00", 1),
        _p("CH", "Breaking News", "16:30", "17:00", 2),
    ]
    assert _timeline(resolve_overlaps(progs)) == [
        ("Breaking News", "16:30:00", "17:00:00"),
        ("Movie", "17:00:00", "19:00:00"),
    ]


def test_clean_schedules_untouched_and_channels_independent() -> None:
    progs = [
        _p("B", "Two", "17:00", "18:00", 0),
        _p("A", "One", "16:00", "17:00", 0),
        _p("A", "Two", "17:00", "18:00", 0),
        _p("B", "One", "16:00", "17:00", 0),
        _p("A", "One", "16:00", "17:00", 0),  # exact repeat (e.g. two chunks)
    ]
    out = resolve_overlaps(progs)
    assert [(p.channel_id, p.title) for p in out] == [
        ("A", "One"), ("A", "Two"), ("B", "One"), ("B", "Two"),
    ]
    assert len(out) == 4


def test_epg_parser_records_asset_revision(tmp_path: Path) -> None:
    client = _client(tmp_path, lambda _r: httpx.Response(404), token="tok")
    try:
        (prog,) = client._programmes_from_epg_assets(FIXTURE, {WCBS.id: WCBS})
    finally:
        client.close()
    assert prog.revision == 284549026  # LIVE_284549026
