"""Authenticated Fubo API client for channels, streams, and schedule data."""

from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.fubo.tv"

DRM_SOURCES = {"Disney", "Starz", "Showtime", "Max", "HBO"}
DRM_CALL_SIGNS = {
    "MXEF",
    "ESPNUHD",
    "ESPNEWS",
    "ACCDN",
    "NGWIHD",
    "HALLHDDRM",
    "HMMHDDRM",
    "HALLDRDRM",
}


@dataclass
class Channel:
    id: str
    call_sign: str
    name: str
    logo: str | None = None
    network_type: str | None = None
    groups: list[str] = field(default_factory=list)
    source: str | None = None


@dataclass
class Programme:
    channel_id: str
    title: str
    start: datetime
    stop: datetime
    description: str | None = None
    categories: list[str] = field(default_factory=list)


class FuboError(Exception):
    """Raised when the Fubo API returns an error."""


class FuboClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = Lock()
        self._token: str | None = None
        self._token_at = 0.0
        self._device_id = self._load_device_id()
        self._http = httpx.Client(timeout=30.0, follow_redirects=True)
        self._channels_cache: list[Channel] | None = None
        self._channels_cache_at = 0.0
        self._channels_source: str | None = None
        self._drm_skipped_count = 0
        self._drm_skipped_ids: set[str] = set()

    def close(self) -> None:
        self._http.close()

    def _load_device_id(self) -> str:
        path = self.settings.config_dir / "device.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                if isinstance(data, str) and data:
                    return data
                if isinstance(data, dict) and data.get("device_id"):
                    return str(data["device_id"])
            except (OSError, json.JSONDecodeError):
                pass

        device_id = secrets.token_hex(8)
        path.write_text(json.dumps({"device_id": device_id}))
        return device_id

    def _headers(self, authorized: bool = True) -> dict[str, str]:
        headers = {
            "authority": "api.fubo.tv",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "application/json",
            "origin": "https://www.fubo.tv",
            "referer": "https://www.fubo.tv/",
            "x-client-version": "4.75.0",
            "x-device-app": "android_tv",
            "x-device-group": "tenfoot",
            "x-device-id": self._device_id,
            "x-device-model": "onn. 4K Streaming Box",
            "x-device-platform": "android_tv",
            "x-device-type": "puck",
            "x-player-version": "v1.34.0",
            "x-preferred-language": "en-US",
            "x-supported-hdrmodes-list": "hdr10,hlg",
            "x-supported-streaming-protocols": "hls",
            "x-supported-codecs-list": "vp9,avc,hevc",
            "x-timezone-offset": "-420",
            "user-agent": (
                "fuboTV/4.75.0 (Linux;Android 12; onn. 4K Streaming Box "
                "Build/SGZ1.221127.063.A1.9885170) FuboPlayer/v1.34.0"
            ),
        }
        if authorized and self._token:
            headers["authorization"] = f"Bearer {self._token}"
        return headers

    def token(self) -> str:
        with self._lock:
            if self._token and (time.time() - self._token_at) < 4 * 60 * 60:
                return self._token

            response = self._http.put(
                f"{API_BASE}/signin",
                json={"email": self.settings.fubo_user, "password": self.settings.fubo_pass},
                headers=self._headers(authorized=False),
            )
            if response.status_code != 200:
                raise FuboError(f"Sign-in failed ({response.status_code}): {response.text}")

            payload = response.json()
            token = payload.get("access_token")
            if not token:
                raise FuboError("Sign-in response missing access_token")

            self._token = token
            self._token_at = time.time()
            logger.info("Signed in to Fubo")
            return token

    def api_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self.token()
        url = f"{API_BASE}/{path.lstrip('/')}"
        response = self._http.get(url, headers=self._headers(), params=params)
        if response.status_code != 200:
            raise FuboError(f"GET {path} failed ({response.status_code}): {response.text[:500]}")
        return response.json()

    @staticmethod
    def _is_drm_channel(channel: dict[str, Any]) -> bool:
        source = channel.get("source") or ""
        call_sign = channel.get("call_sign") or channel.get("callSign") or ""
        if source in DRM_SOURCES:
            return True
        if call_sign in DRM_CALL_SIGNS:
            return True
        return False

    def _add_station(
        self,
        stations: dict[str, Channel],
        *,
        station_id: Any,
        call_sign: str | None,
        name: str | None,
        logo: str | None,
        network_type: str | None,
        group: str,
        source: str | None,
        raw: dict[str, Any],
    ) -> None:
        if not station_id:
            return
        if self._is_drm_channel(raw):
            self._drm_skipped_ids.add(str(station_id))
            return

        sid = str(station_id)
        call = (call_sign or sid).strip()
        display = (name or call).replace(",", "").strip()
        if not display:
            return

        existing = stations.get(sid)
        if existing:
            if group and group not in existing.groups:
                existing.groups.append(group)
            return

        stations[sid] = Channel(
            id=sid,
            call_sign=call,
            name=display,
            logo=logo,
            network_type=network_type,
            groups=[group] if group else [],
            source=source,
        )

    def _channels_from_plan_manager(self) -> dict[str, Channel]:
        """Legacy path using plan-manager + user recurly packages."""
        plans = self.api_get("v3/plan-manager/plans")
        user = self.api_get("user")
        stations: dict[str, Channel] = {}

        plan_data = plans.get("data") or []
        user_data = user.get("data") or user
        purchased = (
            (user_data.get("recurly") or {}).get("purchased_packages")
            or ["fubotv-basic"]
        )

        for package_slug in purchased:
            matches = [
                item
                for item in plan_data
                if (item.get("default_package") or {}).get("slug") == package_slug
            ]
            for item in matches:
                default_pkg = item.get("default_package") or {}
                for ch in default_pkg.get("channels") or []:
                    meta = ch.get("meta") or {}
                    self._add_station(
                        stations,
                        station_id=ch.get("station_id") or ch.get("stationId"),
                        call_sign=ch.get("call_sign") or ch.get("callSign"),
                        name=meta.get("networkName") or meta.get("displayName") or ch.get("name"),
                        logo=meta.get("networkLogoOnWhiteUrl") or ch.get("logoOnWhite"),
                        network_type=meta.get("network_type") or ch.get("networkType"),
                        group=package_slug,
                        source=ch.get("source"),
                        raw=ch,
                    )

                for addon_key in ("add_on_packages", "expired_packages"):
                    for addon in item.get(addon_key) or []:
                        slug = addon.get("slug")
                        if not slug or slug not in purchased:
                            continue
                        for ch in addon.get("channels") or []:
                            meta = ch.get("meta") or {}
                            self._add_station(
                                stations,
                                station_id=ch.get("station_id") or ch.get("stationId"),
                                call_sign=ch.get("call_sign") or ch.get("callSign"),
                                name=meta.get("networkName")
                                or meta.get("displayName")
                                or ch.get("name"),
                                logo=meta.get("networkLogoOnWhiteUrl") or ch.get("logoOnWhite"),
                                network_type=meta.get("network_type") or ch.get("networkType"),
                                group=slug,
                                source=ch.get("source"),
                                raw=ch,
                            )

        return stations

    def _channels_from_subscriptions(self) -> dict[str, Channel]:
        """Newer path using subscriptions APIs."""
        plans = self.api_get("v3/plan-manager/plans")
        products = self.api_get("subscriptions/products", params={"tags": "subscribed", "subscribed": "true"})
        subscriptions = self.api_get("subscriptions")

        main_codes: list[str] = []
        addon_codes: list[str] = []
        if isinstance(subscriptions, list):
            for main_plan in subscriptions:
                code = main_plan.get("ratePlanCode")
                if code:
                    main_codes.append(code)
                for addon in main_plan.get("addons") or []:
                    addon_code = addon.get("ratePlanCode")
                    if addon_code:
                        addon_codes.append(addon_code)

        data_channels: list[dict[str, Any]] = []
        for product in products.get("products") or []:
            for rate_plan in product.get("ratePlans") or []:
                if rate_plan.get("code") in main_codes:
                    data_channels.append(product)
                    break

        addon_channels: list[dict[str, Any]] = []
        for product in products.get("addons") or []:
            for rate_plan in product.get("ratePlans") or []:
                if rate_plan.get("code") in addon_codes:
                    addon_channels.append(product)
                    break

        source_channels: list[dict[str, Any]] = []
        for source in plans.get("data") or []:
            default_pkg = source.get("default_package") or {}
            source_channels.extend(default_pkg.get("channels") or [])
            for addon in source.get("add_on_packages") or []:
                source_channels.extend(addon.get("channels") or [])

        source_mapping = {
            ch.get("station_id") or ch.get("stationId"): ch.get("source")
            for ch in source_channels
            if ch.get("station_id") or ch.get("stationId")
        }

        stations: dict[str, Channel] = {}
        combined = addon_channels + data_channels
        combined_codes = main_codes + addon_codes

        for code in combined_codes:
            matches = [
                item
                for item in combined
                if any(rp.get("code") == code for rp in item.get("ratePlans") or [])
            ]
            for item in matches:
                for ch in item.get("channels") or []:
                    station_id = ch.get("stationId") or ch.get("station_id")
                    if station_id in source_mapping and not ch.get("source"):
                        ch = {**ch, "source": source_mapping[station_id]}
                    self._add_station(
                        stations,
                        station_id=station_id,
                        call_sign=ch.get("callSign") or ch.get("call_sign"),
                        name=ch.get("name"),
                        logo=ch.get("logoOnWhite") or ch.get("logo"),
                        network_type=ch.get("networkType") or ch.get("network_type"),
                        group=code,
                        source=ch.get("source"),
                        raw=ch,
                    )

        return stations

    def channels(self, *, force: bool = False) -> list[Channel]:
        with self._lock:
            if (
                not force
                and self._channels_cache is not None
                and (time.time() - self._channels_cache_at) < 30 * 60
            ):
                return list(self._channels_cache)

        stations: dict[str, Channel] = {}
        errors: list[str] = []
        source_used: str | None = None
        self._drm_skipped_ids = set()

        try:
            stations = self._channels_from_subscriptions()
            source_used = "subscriptions"
            logger.info("Loaded %s channels via subscriptions API", len(stations))
        except FuboError as exc:
            errors.append(str(exc))
            logger.warning("Subscriptions channel path failed: %s", exc)

        if not stations:
            try:
                stations = self._channels_from_plan_manager()
                source_used = "plan-manager"
                logger.info("Loaded %s channels via plan-manager API", len(stations))
            except FuboError as exc:
                errors.append(str(exc))
                logger.warning("Plan-manager channel path failed: %s", exc)

        if not stations:
            raise FuboError("; ".join(errors) or "No channels returned from Fubo")

        sorted_channels = sorted(
            stations.values(),
            key=lambda ch: (
                0 if ch.network_type == "OTA" else (1 if ch.network_type == "RSN" else 2),
                ch.name.lower(),
            ),
        )

        with self._lock:
            self._channels_cache = list(sorted_channels)
            self._channels_cache_at = time.time()
            self._channels_source = source_used
            self._drm_skipped_count = len(self._drm_skipped_ids)

        return sorted_channels

    def runtime_stats(self) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            token_age: int | None = None
            token_ttl: int | None = None
            if self._token:
                token_age = max(0, int(now - self._token_at))
                token_ttl = max(0, int(4 * 60 * 60 - (now - self._token_at)))
            channels_age: int | None = None
            channel_count: int | None = None
            if self._channels_cache is not None:
                channel_count = len(self._channels_cache)
                channels_age = max(0, int(now - self._channels_cache_at))
            return {
                "signed_in": bool(self._token),
                "token_age_seconds": token_age,
                "token_ttl_remaining_seconds": token_ttl,
                "channel_count": channel_count,
                "channels_cache_age_seconds": channels_age,
                "channels_source": self._channels_source,
                "drm_skipped_count": self._drm_skipped_count,
            }

    def watch(self, channel_id: str) -> str:
        payload = self.api_get("vapi/asset/v1", params={"channelId": channel_id, "type": "live"})
        stream = payload.get("stream") or {}
        if stream.get("drmProtected") is True:
            raise FuboError("Stream is DRM protected")
        url = stream.get("url")
        if not url:
            raise FuboError("Stream response missing URL")
        return url

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
                node.get("title")
                or node.get("name")
                or (node.get("airing") or {}).get("title")
                or (node.get("program") or {}).get("title")
            )
            start = (
                self._parse_dt(node.get("startTime") or node.get("start") or node.get("startsAt"))
                or self._parse_dt((node.get("airing") or {}).get("startTime"))
            )
            stop = (
                self._parse_dt(node.get("endTime") or node.get("stop") or node.get("endsAt"))
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

        Tries several authenticated Fubo endpoints. Returns an empty list when
        schedule data is unavailable so callers can still emit channel-only XMLTV.
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

        candidates: list[tuple[str, dict[str, Any] | None]] = [
            (
                "epg",
                {
                    "startTime": start_iso,
                    "endTime": end_iso,
                },
            ),
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

        programmes: list[Programme] = []

        for path, params in candidates:
            try:
                payload = self.api_get(path, params=params)
            except FuboError as exc:
                logger.debug("EPG endpoint %s unavailable: %s", path, exc)
                continue

            found = self._programmes_from_payload(payload, channels_by_id, channels_by_call)
            if found:
                logger.info("Loaded %s programmes from %s", len(found), path)
                programmes.extend(found)
                break

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
                        logger.debug("EPG endpoint %s unavailable: %s", path, exc)
                        continue
                    found = self._programmes_from_payload(
                        payload, channels_by_id, channels_by_call
                    )
                    if found:
                        logger.info("Loaded %s programmes from %s", len(found), path)
                        programmes.extend(found)

        # De-dupe by channel + start + title
        unique: dict[tuple[str, str, str], Programme] = {}
        for prog in programmes:
            key = (prog.channel_id, prog.start.isoformat(), prog.title)
            unique[key] = prog

        return sorted(unique.values(), key=lambda p: (p.channel_id, p.start))
