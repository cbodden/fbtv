"""EPG / schedule fetch and programme parsing."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.fubo.models import Channel, FuboError, Programme

logger = logging.getLogger(__name__)


class ScheduleMixin:
    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            ts = float(value)
            if ts > 1_000_000_000_000:
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            if text.isdigit():
                return FuboClient._parse_dt(int(text))
            try:
                if text.endswith("Z"):
                    text = text[:-1] + "+00:00"
                return datetime.fromisoformat(text).astimezone(timezone.utc)
            except ValueError:
                return None
        return None

    @staticmethod
    def _text_field(value: Any) -> str | None:
        """Normalize Fubo title/name fields (plain string or ``{"text": "..."}``)."""
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            return text or None
        if isinstance(value, dict):
            nested = value.get("text") or value.get("value") or value.get("name")
            if isinstance(nested, str):
                text = nested.strip()
                return text or None
        return None

    def _programmes_from_papi_components(
        self,
        components: list[Any],
        channels_by_id: dict[str, Channel],
        rich_lookup: dict[tuple[str, str], dict[str, Any]] | None = None,
    ) -> list[Programme]:
        """Parse ``channel-cell`` / ``program-cell`` payloads from ``papi/v1/guide/epg``."""
        programmes: list[Programme] = []
        rich_lookup = rich_lookup or {}

        for channel_cell in components:
            if not isinstance(channel_cell, dict):
                continue
            if channel_cell.get("type") and channel_cell.get("type") != "channel-cell":
                continue

            station_id = str(channel_cell.get("id") or "").strip()
            channel = channels_by_id.get(station_id) if station_id else None
            if channel is None:
                continue

            for prog in channel_cell.get("components") or []:
                if not isinstance(prog, dict):
                    continue
                if prog.get("type") and prog.get("type") != "program-cell":
                    continue

                start_raw = prog.get("start_time") or prog.get("startTime")
                stop_raw = prog.get("end_time") or prog.get("endTime")
                start = self._parse_dt(start_raw)
                stop = self._parse_dt(stop_raw)
                if not start or not stop:
                    continue

                title = (
                    self._text_field(prog.get("title"))
                    or self._text_field(prog.get("name"))
                    or self._text_field(prog.get("subtitle"))
                )
                rich = rich_lookup.get((station_id, str(start_raw))) if start_raw else None
                if rich and not title:
                    title = self._text_field(rich.get("title"))
                if not title:
                    continue

                desc = (
                    prog.get("description")
                    or (rich or {}).get("description")
                    or self._text_field(prog.get("subtitle"))
                )
                categories: list[str] = []
                for value in (
                    prog.get("normalizedGenres")
                    or prog.get("genres")
                    or (rich or {}).get("normalizedGenres")
                    or (rich or {}).get("genres")
                    or []
                ):
                    if isinstance(value, dict):
                        name = value.get("name") or value.get("value")
                        if name:
                            categories.append(str(name))
                    elif value:
                        categories.append(str(value))

                programmes.append(
                    Programme(
                        channel_id=channel.call_sign,
                        title=title,
                        start=start,
                        stop=stop,
                        description=str(desc) if desc else None,
                        categories=categories,
                    )
                )

        return programmes

    def _fetch_papi_guide_components(
        self,
        start: datetime,
        end: datetime,
        *,
        chunk_hours: int = 6,
    ) -> list[dict[str, Any]]:
        """Fetch and merge ``papi/v1/guide/epg`` channel-cells across time chunks."""
        channels_by_id: dict[str, dict[str, Any]] = {}
        current = start.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        end_utc = end.astimezone(timezone.utc)
        any_ok = False

        while current < end_utc:
            chunk_end = min(current + timedelta(hours=chunk_hours), end_utc)
            start_str = current.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            end_str = chunk_end.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            try:
                payload = self.api_get(
                    "papi/v1/guide/epg",
                    params={"start_time": start_str, "end_time": end_str},
                    timeout=120.0,
                )
            except FuboError as exc:
                logger.info(
                    "EPG endpoint papi/v1/guide/epg unavailable (%s → %s): %s",
                    start_str,
                    end_str,
                    exc,
                )
                current = chunk_end
                continue

            any_ok = True
            epg_data = (payload or {}).get("content", {}).get("epg", {})
            if isinstance(epg_data, list):
                chunk_channels = epg_data
            elif isinstance(epg_data, dict):
                if epg_data.get("type") == "channel-cell":
                    chunk_channels = [epg_data]
                else:
                    chunk_channels = epg_data.get("components") or epg_data.get("channels") or []
                    if not isinstance(chunk_channels, list):
                        chunk_channels = []
            else:
                chunk_channels = []

            for ch in chunk_channels:
                if not isinstance(ch, dict):
                    continue
                if ch.get("type") and ch.get("type") != "channel-cell":
                    continue
                ch_id = str(ch.get("id") or "").strip()
                if not ch_id:
                    continue
                if ch_id not in channels_by_id:
                    channels_by_id[ch_id] = ch
                else:
                    existing = channels_by_id[ch_id].setdefault("components", [])
                    if not isinstance(existing, list):
                        existing = []
                        channels_by_id[ch_id]["components"] = existing
                    for prog in ch.get("components") or []:
                        existing.append(prog)

            current = chunk_end

        if not any_ok:
            return []
        return list(channels_by_id.values())

    def _programmes_from_epg_assets(
        self,
        payload: Any,
        channels_by_id: dict[str, Channel],
    ) -> list[Programme]:
        """Parse ``/epg`` ``channelWithProgramAssets`` payloads (live-confirmed 200 OK)."""
        programmes: list[Programme] = []
        unmatched_ids: list[str] = []
        incomplete = 0
        rows = (payload or {}).get("response") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return programmes

        channels_by_call = {ch.call_sign: ch for ch in channels_by_id.values()}

        for ch in rows:
            if not isinstance(ch, dict):
                continue
            if ch.get("type") and ch.get("type") != "channelWithProgramAssets":
                continue
            ch_data = ch.get("data") or {}
            if not isinstance(ch_data, dict):
                continue
            channel_meta = ch_data.get("channel") or {}
            if not isinstance(channel_meta, dict):
                channel_meta = {}
            channel = self._match_epg_channel(
                channel_meta, channels_by_id, channels_by_call
            )
            if channel is None:
                unmatched_ids.append(
                    str(
                        channel_meta.get("id")
                        or channel_meta.get("stationId")
                        or channel_meta.get("station_id")
                        or channel_meta.get("callSign")
                        or channel_meta.get("call_sign")
                        or "?"
                    )
                )
                continue

            for item in ch_data.get("programsWithAssets") or []:
                if not isinstance(item, dict):
                    continue
                program = item.get("program") or {}
                if not isinstance(program, dict):
                    program = {}
                assets = item.get("assets") or []
                asset = assets[0] if assets and isinstance(assets[0], dict) else {}
                access = asset.get("accessRights") or {}
                if not isinstance(access, dict):
                    access = {}

                start = self._parse_dt(
                    access.get("startTime")
                    or asset.get("startTime")
                    or item.get("startTime")
                    or program.get("startTime")
                )
                stop = self._parse_dt(
                    access.get("endTime")
                    or asset.get("endTime")
                    or item.get("endTime")
                    or program.get("endTime")
                )
                if start and not stop:
                    duration = (
                        access.get("durationInSeconds")
                        or access.get("durationSeconds")
                        or access.get("duration")
                        or asset.get("durationInSeconds")
                        or asset.get("durationSeconds")
                        or asset.get("duration")
                        or program.get("durationInSeconds")
                        or program.get("duration")
                    )
                    if isinstance(duration, (int, float)) and duration > 0:
                        # Fubo sometimes reports ms for large values.
                        seconds = float(duration)
                        if seconds > 24 * 60 * 60:
                            seconds = seconds / 1000.0
                        stop = start + timedelta(seconds=seconds)

                title = (
                    self._text_field(program.get("title"))
                    or self._text_field(program.get("name"))
                    or self._text_field(program.get("shortName"))
                    or self._text_field(asset.get("title"))
                    or self._text_field(item.get("title"))
                )
                if not (title and start and stop):
                    incomplete += 1
                    continue

                desc = (
                    program.get("longDescription")
                    or program.get("shortDescription")
                    or program.get("description")
                )
                categories: list[str] = []
                for g in program.get("genres") or []:
                    if isinstance(g, dict) and g.get("name"):
                        categories.append(str(g["name"]))
                    elif g:
                        categories.append(str(g))
                for t in (program.get("tagsV2") or {}).get("normalized_genre") or []:
                    if isinstance(t, dict) and t.get("value"):
                        categories.append(str(t["value"]))

                programmes.append(
                    Programme(
                        channel_id=channel.call_sign,
                        title=title,
                        start=start,
                        stop=stop,
                        description=str(desc) if desc else None,
                        categories=categories,
                    )
                )

        if rows and not programmes:
            sample = ", ".join(unmatched_ids[:8]) or "(none)"
            logger.info(
                "EPG /epg mapped 0 programmes (rows=%s unmatched_channels=%s "
                "incomplete_items=%s sample_unmatched=%s)",
                len(rows),
                len(unmatched_ids),
                incomplete,
                sample,
            )
        return programmes

    def _match_epg_channel(
        self,
        meta: dict[str, Any],
        channels_by_id: dict[str, Channel],
        channels_by_call: dict[str, Channel],
    ) -> Channel | None:
        """Join an ``/epg`` channel object to the lineup by station id or call sign."""
        for key in ("id", "stationId", "station_id", "channelId", "channel_id"):
            value = meta.get(key)
            if value is None:
                continue
            sid = str(value).strip()
            if sid and sid in channels_by_id:
                return channels_by_id[sid]
        for key in ("callSign", "call_sign", "stationCallSign"):
            value = meta.get(key)
            if value and str(value) in channels_by_call:
                return channels_by_call[str(value)]
        return None

    def _fetch_epg_assets_programmes(
        self,
        start: datetime,
        end: datetime,
        channels_by_id: dict[str, Channel],
    ) -> list[Programme]:
        """Fetch listings from ``/epg`` (optionally enriched). Known live 200 path."""
        start_str = start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        end_str = end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        attempts: list[tuple[str, dict[str, Any]]] = [
            (
                "epg?enrichments=follow",
                {
                    "startTime": start_str,
                    "endTime": end_str,
                    "enrichments": "follow",
                },
            ),
            (
                "epg",
                {
                    "startTime": start_str,
                    "endTime": end_str,
                },
            ),
        ]
        for label, params in attempts:
            try:
                payload = self.api_get("epg", params=params, timeout=120.0)
            except FuboError as exc:
                logger.info("EPG endpoint %s unavailable: %s", label, exc)
                continue
            found = self._programmes_from_epg_assets(payload, channels_by_id)
            if found:
                logger.info("Loaded %s programmes from %s", len(found), label)
                return found
            response_len = len((payload or {}).get("response") or []) if isinstance(payload, dict) else 0
            logger.info(
                "EPG endpoint %s responded (response rows=%s) but mapped 0 programmes",
                label,
                response_len,
            )
        return []

    def _fetch_epg_enrichment(
        self,
        start: datetime,
        end: datetime,
    ) -> dict[tuple[str, str], dict[str, Any]]:
        """Optional descriptions/genres from ``/epg?enrichments=follow`` keyed by station+start."""
        rich_lookup: dict[tuple[str, str], dict[str, Any]] = {}
        current = start.astimezone(timezone.utc)
        end_utc = end.astimezone(timezone.utc)

        while current < end_utc:
            chunk_end = min(current + timedelta(hours=24), end_utc)
            start_str = current.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            end_str = chunk_end.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            try:
                payload = self.api_get(
                    "epg",
                    params={
                        "startTime": start_str,
                        "endTime": end_str,
                        "enrichments": "follow",
                    },
                    timeout=120.0,
                )
            except FuboError as exc:
                logger.debug("EPG enrichment /epg unavailable: %s", exc)
                current = chunk_end
                continue

            for ch in (payload or {}).get("response") or []:
                if not isinstance(ch, dict) or ch.get("type") != "channelWithProgramAssets":
                    continue
                ch_data = ch.get("data") or {}
                channel = ch_data.get("channel") or {}
                ch_id = str(channel.get("id") or "").strip()
                if not ch_id:
                    continue
                for item in ch_data.get("programsWithAssets") or []:
                    if not isinstance(item, dict):
                        continue
                    program = item.get("program") or {}
                    assets = item.get("assets") or []
                    if not assets:
                        continue
                    access = (assets[0] or {}).get("accessRights") or {}
                    start_time = access.get("startTime")
                    if not start_time:
                        continue
                    genres = [
                        str(g["name"])
                        for g in program.get("genres") or []
                        if isinstance(g, dict) and g.get("name")
                    ]
                    normalized = [
                        str(t["value"])
                        for t in (program.get("tagsV2") or {}).get("normalized_genre") or []
                        if isinstance(t, dict) and t.get("value")
                    ]
                    rich_lookup[(ch_id, str(start_time))] = {
                        "title": self._text_field(program.get("title"))
                        or self._text_field(program.get("name")),
                        "description": program.get("longDescription")
                        or program.get("shortDescription")
                        or "",
                        "genres": genres,
                        "normalizedGenres": normalized,
                    }

            current = chunk_end

        return rich_lookup

    def _programmes_from_payload(
        self,
        payload: Any,
        channels_by_id: dict[str, Channel],
        channels_by_call: dict[str, Channel],
    ) -> list[Programme]:
        programmes: list[Programme] = []

        def resolve_channel(item: dict[str, Any]) -> Channel | None:
            for key in ("stationId", "station_id", "channelId", "channel_id", "id", "networkId"):
                value = item.get(key)
                if value is None:
                    continue
                sid = str(value)
                if sid in channels_by_id:
                    return channels_by_id[sid]
            for key in ("callSign", "call_sign", "stationCallSign"):
                value = item.get(key)
                if value and str(value) in channels_by_call:
                    return channels_by_call[str(value)]
            nested = item.get("station") or item.get("network") or item.get("channel") or {}
            if isinstance(nested, dict):
                return resolve_channel(nested)
            return None

        def walk(node: Any) -> None:
            if isinstance(node, list):
                for item in node:
                    walk(item)
                return
            if not isinstance(node, dict):
                return

            title = (
                self._text_field(node.get("title"))
                or self._text_field(node.get("name"))
                or self._text_field((node.get("airing") or {}).get("title"))
                or self._text_field((node.get("program") or {}).get("title"))
            )
            start = (
                self._parse_dt(
                    node.get("startTime")
                    or node.get("start_time")
                    or node.get("start")
                    or node.get("startsAt")
                )
                or self._parse_dt((node.get("airing") or {}).get("startTime"))
            )
            stop = (
                self._parse_dt(
                    node.get("endTime")
                    or node.get("end_time")
                    or node.get("stop")
                    or node.get("endsAt")
                )
                or self._parse_dt((node.get("airing") or {}).get("endTime"))
            )

            if title and start and stop:
                channel = resolve_channel(node)
                if channel:
                    desc = (
                        node.get("description")
                        or node.get("shortDescription")
                        or (node.get("program") or {}).get("description")
                    )
                    categories: list[str] = []
                    for key in ("genres", "categories", "category"):
                        value = node.get(key)
                        if isinstance(value, list):
                            categories.extend(str(v) for v in value)
                        elif isinstance(value, str) and value:
                            categories.append(value)
                    programmes.append(
                        Programme(
                            channel_id=channel.call_sign,
                            title=str(title),
                            start=start,
                            stop=stop,
                            description=str(desc) if desc else None,
                            categories=categories,
                        )
                    )

            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value)

        walk(payload)
        return programmes

    def schedule(self, channels: list[Channel], days: int | None = None) -> list[Programme]:
        """Fetch guide listings and map them onto known channels.

        Prefers live-confirmed ``/epg`` (``channelWithProgramAssets``), then
        ``papi/v1/guide/epg``, then older bulk/sample paths. Returns an empty
        list when schedule data is unavailable so callers can still emit
        channel-only XMLTV.
        """
        days = days if days is not None else self.settings.epg_days
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=1)
        end = now + timedelta(days=days)
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        start_iso = start.isoformat().replace("+00:00", "Z")
        end_iso = end.isoformat().replace("+00:00", "Z")

        channels_by_id = {ch.id: ch for ch in channels}
        channels_by_call = {ch.call_sign: ch for ch in channels}

        programmes: list[Programme] = []
        source: str | None = None

        logger.info(
            "EPG schedule probe starting (%s channels, %s day(s))",
            len(channels),
            days,
        )

        # Field note (2026-08-12): plain /epg returns 200; older paths 404. Parse
        # channelWithProgramAssets explicitly — the generic walker maps 0 rows.
        found = self._fetch_epg_assets_programmes(start, end, channels_by_id)
        if found:
            programmes.extend(found)
            source = "epg"

        if not programmes:
            papi_components = self._fetch_papi_guide_components(start, end)
            if papi_components:
                rich = self._fetch_epg_enrichment(start, end)
                found = self._programmes_from_papi_components(
                    papi_components, channels_by_id, rich_lookup=rich
                )
                if found:
                    logger.info(
                        "Loaded %s programmes from papi/v1/guide/epg (%s channel-cells, %s enriched keys)",
                        len(found),
                        len(papi_components),
                        len(rich),
                    )
                    programmes.extend(found)
                    source = "papi/v1/guide/epg"
                else:
                    logger.info(
                        "EPG papi/v1/guide/epg returned %s channel-cells but 0 programmes mapped to lineup",
                        len(papi_components),
                    )
            else:
                logger.info(
                    "EPG papi/v1/guide/epg returned no channel-cells (all chunks failed or empty)"
                )

        if not programmes:
            candidates: list[tuple[str, dict[str, Any] | None]] = [
                (
                    "v3/epg",
                    {
                        "startTime": start_iso,
                        "endTime": end_iso,
                    },
                ),
                (
                    "tvguide",
                    {
                        "startTime": start_ms,
                        "endTime": end_ms,
                    },
                ),
                (
                    "v3/kgraph/v3/epg",
                    {
                        "startTime": start_iso,
                        "endTime": end_iso,
                    },
                ),
                (
                    "epg/v1/listings",
                    {
                        "startTime": start_iso,
                        "endTime": end_iso,
                    },
                ),
            ]

            for path, params in candidates:
                try:
                    payload = self.api_get(path, params=params, timeout=60.0)
                except FuboError as exc:
                    logger.info("EPG endpoint %s unavailable: %s", path, exc)
                    continue

                found = self._programmes_from_payload(
                    payload, channels_by_id, channels_by_call
                )
                if found:
                    logger.info("Loaded %s programmes from %s", len(found), path)
                    programmes.extend(found)
                    source = path
                    break
                logger.info("EPG endpoint %s responded but mapped 0 programmes", path)

        # Fall back to a small sample of per-network schedules when bulk EPG is unavailable.
        if not programmes:
            for station_id in [ch.id for ch in channels[:5]]:
                for path in (
                    f"v3/kgraph/v3/networks/{station_id}/schedule",
                    f"epg/stations/{station_id}",
                ):
                    try:
                        payload = self.api_get(
                            path,
                            params={"startTime": start_iso, "endTime": end_iso},
                        )
                    except FuboError as exc:
                        logger.info("EPG endpoint %s unavailable: %s", path, exc)
                        continue
                    found = self._programmes_from_payload(
                        payload, channels_by_id, channels_by_call
                    )
                    if found:
                        logger.info("Loaded %s programmes from %s", len(found), path)
                        programmes.extend(found)
                        source = path

        # De-dupe by channel + start + title
        unique: dict[tuple[str, str, str], Programme] = {}
        for prog in programmes:
            key = (prog.channel_id, prog.start.isoformat(), prog.title)
            unique[key] = prog

        result = sorted(unique.values(), key=lambda p: (p.channel_id, p.start))
        if result:
            logger.info(
                "EPG schedule complete: %s programmes (source=%s)",
                len(result),
                source or "unknown",
            )
        else:
            logger.warning(
                "EPG schedule complete: 0 programmes — XMLTV will be channel-only; "
                "use Emby Guide Data FuboTV / Jellyfin Schedules Direct until a probe succeeds"
            )
        return result
