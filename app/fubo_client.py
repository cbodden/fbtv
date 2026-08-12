"""Authenticated Fubo API client for channels, streams, and schedule data."""

from __future__ import annotations

import json
import logging
import secrets
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable

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
        self._drm_records: dict[str, dict[str, Any]] = {}
        self._drm_playable: dict[str, dict[str, Any]] = {}
        self._drm_updated_at: float | None = None
        self._drm_last_scan_at: float | None = None
        self._drm_learned_ids: set[str] = set()
        self._load_drm_state()
        self._scan_lock = Lock()
        self._scan_running = False
        self._scan_started_at: float | None = None
        self._scan_finished_at: float | None = None
        self._scan_last_result: dict[str, Any] | None = None

    def close(self) -> None:
        self._http.close()

    def _drm_skipped_path(self) -> Path:
        return self.settings.config_dir / "drm_skipped.json"

    def _load_drm_state(self) -> None:
        path = self._drm_skipped_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Could not read %s; starting with empty DRM skip list", path)
            return

        learned: set[str] = set()
        records: dict[str, dict[str, Any]] = {}
        playable: dict[str, dict[str, Any]] = {}
        updated_at: float | None = None
        last_scan_at: float | None = None

        def _parse_ts(raw: Any) -> float | None:
            if isinstance(raw, (int, float)):
                return float(raw)
            if isinstance(raw, str) and raw.strip():
                try:
                    text = raw.strip()
                    if text.endswith("Z"):
                        text = text[:-1] + "+00:00"
                    return datetime.fromisoformat(text).timestamp()
                except ValueError:
                    return None
            return None

        if isinstance(data, list):
            learned = {str(item) for item in data if item}
        elif isinstance(data, dict):
            raw_ids = data.get("station_ids") or data.get("ids") or []
            learned = {str(item) for item in raw_ids if item}
            raw_stations = data.get("stations") or {}
            if isinstance(raw_stations, dict):
                for sid, meta in raw_stations.items():
                    if isinstance(meta, dict):
                        records[str(sid)] = dict(meta)
                        learned.add(str(sid))
            raw_playable = data.get("playable") or {}
            if isinstance(raw_playable, dict):
                for sid, meta in raw_playable.items():
                    if isinstance(meta, dict):
                        playable[str(sid)] = dict(meta)
            updated_at = _parse_ts(data.get("updated_at"))
            last_scan_at = _parse_ts(data.get("last_scan_at"))
        else:
            return

        self._drm_learned_ids = learned
        self._drm_records = records
        self._drm_playable = playable
        self._drm_updated_at = updated_at
        self._drm_last_scan_at = last_scan_at
        self._drm_skipped_ids = set(learned)
        self._drm_skipped_count = len(learned)

    def _save_drm_state(self) -> None:
        path = self._drm_skipped_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            updated = self._drm_updated_at or time.time()
            payload: dict[str, Any] = {
                "station_ids": sorted(self._drm_learned_ids),
                "updated_at": datetime.fromtimestamp(updated, tz=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "stations": {
                    sid: self._drm_records.get(sid, {"drm": True})
                    for sid in sorted(self._drm_learned_ids)
                },
                "playable": {
                    sid: meta
                    for sid, meta in sorted(self._drm_playable.items())
                    if sid not in self._drm_learned_ids
                },
            }
            if self._drm_last_scan_at:
                payload["last_scan_at"] = (
                    datetime.fromtimestamp(self._drm_last_scan_at, tz=timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                )
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not persist DRM skip list to %s: %s", path, exc)

    def mark_drm_station(
        self,
        station_id: str,
        *,
        via: str = "tune",
        call_sign: str | None = None,
        name: str | None = None,
        save: bool = True,
    ) -> None:
        """Remember a station that Fubo flagged drmProtected; drop it from the M3U cache."""
        sid = str(station_id).strip()
        if not sid:
            return
        now_iso = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        with self._lock:
            newly = sid not in self._drm_learned_ids
            self._drm_learned_ids.add(sid)
            self._drm_skipped_ids.add(sid)
            self._drm_playable.pop(sid, None)
            meta = dict(self._drm_records.get(sid) or {})
            meta.update(
                {
                    "drm": True,
                    "checked_at": now_iso,
                    "via": via,
                }
            )
            if call_sign:
                meta["call_sign"] = call_sign
            if name:
                meta["name"] = name
            self._drm_records[sid] = meta
            self._drm_updated_at = time.time()
            if self._channels_cache is not None:
                before = len(self._channels_cache)
                self._channels_cache = [ch for ch in self._channels_cache if ch.id != sid]
                if len(self._channels_cache) != before:
                    logger.info("Removed DRM station %s from channel cache", sid)
            self._drm_skipped_count = len(self._drm_skipped_ids | self._drm_learned_ids)
            if save:
                self._save_drm_state()
            if newly:
                logger.info(
                    "Learned DRM station %s via=%s (total learned=%s); excluded from future playlists",
                    sid,
                    via,
                    len(self._drm_learned_ids),
                )

    def mark_playable_station(
        self,
        station_id: str,
        *,
        via: str = "scan",
        call_sign: str | None = None,
        name: str | None = None,
        save: bool = True,
    ) -> None:
        sid = str(station_id).strip()
        if not sid:
            return
        now_iso = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        with self._lock:
            was_drm = sid in self._drm_learned_ids
            self._drm_learned_ids.discard(sid)
            self._drm_skipped_ids.discard(sid)
            self._drm_records.pop(sid, None)
            meta = {
                "drm": False,
                "checked_at": now_iso,
                "via": via,
            }
            if call_sign:
                meta["call_sign"] = call_sign
            if name:
                meta["name"] = name
            self._drm_playable[sid] = meta
            self._drm_updated_at = time.time()
            self._drm_skipped_count = len(self._drm_skipped_ids | self._drm_learned_ids)
            if save:
                self._save_drm_state()
            if was_drm:
                logger.info("Station %s reclassified as playable via=%s", sid, via)
                self._channels_cache = None

    def drm_scan_is_fresh(self) -> bool:
        max_age_h = self.settings.drm_scan_max_age_hours
        if max_age_h <= 0:
            return False
        # Only a completed full scan counts toward freshness (not tune-time learns).
        if self._drm_last_scan_at is None:
            return False
        return (time.time() - self._drm_last_scan_at) < max_age_h * 3600

    def probe_asset(self, channel_id: str) -> str:
        """Return ``drm``, ``ok``, or ``error`` for a live asset probe."""
        try:
            payload = self.api_get(
                "vapi/asset/v1",
                params={"channelId": str(channel_id), "type": "live"},
                timeout=30.0,
            )
        except FuboError as exc:
            logger.debug("DRM probe %s failed: %s", channel_id, exc)
            return "error"
        stream = payload.get("stream") or {}
        if stream.get("drmProtected") is True:
            return "drm"
        if stream.get("url"):
            return "ok"
        return "error"

    def scan_drm(
        self,
        *,
        force: bool = False,
        on_complete: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Probe lineup stations for drmProtected; persist skip/playable records.

        Skips the whole scan when the skip list is fresher than
        ``DRM_SCAN_MAX_AGE_HOURS`` unless ``force`` is true.
        """
        if not self._scan_lock.acquire(blocking=False):
            raise FuboError("DRM scan already running")

        started = time.time()
        self._scan_running = True
        self._scan_started_at = started
        result: dict[str, Any] = {
            "status": "running",
            "forced": force,
            "checked": 0,
            "drm": 0,
            "playable": 0,
            "errors": 0,
            "skipped": False,
        }
        try:
            if not force and self.drm_scan_is_fresh():
                age_h = (time.time() - (self._drm_last_scan_at or 0)) / 3600.0
                result.update(
                    {
                        "status": "skipped",
                        "skipped": True,
                        "reason": "drm_skip_list_fresh",
                        "age_hours": round(age_h, 2),
                        "max_age_hours": self.settings.drm_scan_max_age_hours,
                        "drm_learned_count": len(self._drm_learned_ids),
                    }
                )
                logger.info(
                    "DRM scan skipped (last full scan age=%.1fh < max_age=%sh)",
                    age_h,
                    self.settings.drm_scan_max_age_hours,
                )
                return result

            # Lineup without learned filter so we can re-check prior DRM ids when forced.
            channels = self._lineup_channels(include_learned_drm=force)
            if not channels and force:
                channels = self._lineup_channels(include_learned_drm=True)
            logger.info(
                "DRM scan starting (%s stations, concurrency=%s, force=%s)",
                len(channels),
                self.settings.drm_scan_concurrency,
                force,
            )

            drm_hits = 0
            playable_hits = 0
            errors = 0
            checked = 0

            def _work(ch: Channel) -> tuple[Channel, str]:
                return ch, self.probe_asset(ch.id)

            workers = max(1, self.settings.drm_scan_concurrency)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_work, ch) for ch in channels]
                for fut in as_completed(futures):
                    ch, outcome = fut.result()
                    checked += 1
                    if outcome == "drm":
                        drm_hits += 1
                        self.mark_drm_station(
                            ch.id,
                            via="scan",
                            call_sign=ch.call_sign,
                            name=ch.name,
                            save=False,
                        )
                    elif outcome == "ok":
                        playable_hits += 1
                        self.mark_playable_station(
                            ch.id,
                            via="scan",
                            call_sign=ch.call_sign,
                            name=ch.name,
                            save=False,
                        )
                    else:
                        errors += 1

            with self._lock:
                self._drm_updated_at = time.time()
                self._drm_last_scan_at = self._drm_updated_at
                self._save_drm_state()
                # Refresh channel cache so M3U drops newly learned DRM.
                self._channels_cache = None

            result.update(
                {
                    "status": "completed",
                    "checked": checked,
                    "drm": drm_hits,
                    "playable": playable_hits,
                    "errors": errors,
                    "drm_learned_count": len(self._drm_learned_ids),
                    "duration_seconds": round(time.time() - started, 1),
                }
            )
            logger.info(
                "DRM scan complete checked=%s drm=%s playable=%s errors=%s learned_total=%s (%.1fs)",
                checked,
                drm_hits,
                playable_hits,
                errors,
                len(self._drm_learned_ids),
                time.time() - started,
            )
            return result
        except Exception as exc:
            result.update({"status": "error", "error": str(exc)})
            logger.exception("DRM scan failed: %s", exc)
            raise
        finally:
            self._scan_finished_at = time.time()
            self._scan_last_result = dict(result)
            self._scan_running = False
            self._scan_lock.release()
            if on_complete is not None:
                try:
                    on_complete(result)
                except Exception:
                    logger.exception("DRM scan on_complete callback failed")

    def _lineup_channels(self, *, include_learned_drm: bool) -> list[Channel]:
        """Subscribed stations after known-package DRM filter; optional learned exclusion."""
        stations: dict[str, Channel] = {}
        errors: list[str] = []
        try:
            stations = self._channels_from_subscriptions()
        except FuboError as exc:
            errors.append(str(exc))
            logger.warning("Subscriptions channel path failed: %s", exc)
        if not stations:
            try:
                stations = self._channels_from_plan_manager()
            except FuboError as exc:
                errors.append(str(exc))
                logger.warning("Plan-manager channel path failed: %s", exc)
        if not stations:
            raise FuboError("; ".join(errors) or "No channels returned from Fubo")

        if not include_learned_drm:
            with self._lock:
                learned = set(self._drm_learned_ids)
            for sid in list(stations.keys()):
                if sid in learned:
                    del stations[sid]

        return sorted(
            stations.values(),
            key=lambda ch: (
                0 if ch.network_type == "OTA" else (1 if ch.network_type == "RSN" else 2),
                ch.name.lower(),
            ),
        )

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
            "x-client-version": "5.40.0",
            "x-device-app": "android_tv",
            "x-device-group": "tenfoot",
            "x-device-id": self._device_id,
            "x-device-model": "onn. 4K Streaming Box",
            "x-device-platform": "android_tv",
            "x-device-type": "puck",
            "x-player-version": "v1.106.0",
            "x-preferred-language": "en-US",
            "x-supported-hdrmodes-list": "hdr10,hlg",
            "x-supported-streaming-protocols": "hls,mpeg",
            "x-supported-codecs-list": "vp9,avc,hevc",
            "x-drm-scheme": "widevine",
            "x-timezone-offset": "-420",
            "user-agent": (
                "FuboTV/5.40.0 (Linux; U: ANDROID; en-us; onn. 4K Streaming Box "
                "Build/SGZ1.221127.063.A1.9885170) FuboPlayer/v1.106.0"
            ),
        }
        if authorized and self._token:
            headers["authorization"] = f"Bearer {self._token}"
        return headers

    def token(self) -> str:
        with self._lock:
            if self._token and (time.time() - self._token_at) < 4 * 60 * 60:
                return self._token

            body = json.dumps(
                {"email": self.settings.fubo_user, "password": self.settings.fubo_pass},
                ensure_ascii=False,
            ).encode("utf-8")
            response = self._http.put(
                f"{API_BASE}/signin",
                content=body,
                headers=self._headers(authorized=False),
            )
            if response.status_code != 200:
                logger.warning(
                    "Sign-in rejected (%s) user=%s pass_len=%s source=%s",
                    response.status_code,
                    self.settings.fubo_user,
                    len(self.settings.fubo_pass),
                    self.settings.credentials_source,
                )
                raise FuboError(f"Sign-in failed ({response.status_code}): {response.text}")

            payload = response.json()
            token = payload.get("access_token")
            if not token:
                raise FuboError("Sign-in response missing access_token")

            self._token = token
            self._token_at = time.time()
            logger.info("Signed in to Fubo")
            return token

    def api_get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        self.token()
        url = f"{API_BASE}/{path.lstrip('/')}"
        response = self._http.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=timeout if timeout is not None else self._http.timeout,
        )
        if response.status_code != 200:
            raise FuboError(f"GET {path} failed ({response.status_code}): {response.text[:500]}")
        return response.json()

    @staticmethod
    def _is_drm_channel(channel: dict[str, Any]) -> bool:
        if channel.get("drmProtected") is True or channel.get("drm_protected") is True:
            return True
        if channel.get("isDrm") is True or channel.get("is_drm") is True:
            return True
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
        with self._lock:
            learned = set(self._drm_learned_ids)
        self._drm_skipped_ids = set(learned)

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

        for sid in list(stations.keys()):
            if sid in learned:
                del stations[sid]
                self._drm_skipped_ids.add(sid)

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
            self._drm_skipped_count = len(self._drm_skipped_ids | self._drm_learned_ids)
            if learned:
                logger.info(
                    "Excluded %s previously learned DRM stations from lineup",
                    len(learned),
                )

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
                "credentials_source": self.settings.credentials_source,
                "drm_skipped_count": self._drm_skipped_count,
                "drm_learned_count": len(self._drm_learned_ids),
                "drm_playable_count": len(self._drm_playable),
                "drm_updated_at": (
                    datetime.fromtimestamp(self._drm_updated_at, tz=timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                    if self._drm_updated_at
                    else None
                ),
                "drm_last_scan_at": (
                    datetime.fromtimestamp(self._drm_last_scan_at, tz=timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                    if self._drm_last_scan_at
                    else None
                ),
                "drm_scan_running": self._scan_running,
                "drm_scan_started_at": (
                    datetime.fromtimestamp(self._scan_started_at, tz=timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                    if self._scan_started_at
                    else None
                ),
                "drm_scan_finished_at": (
                    datetime.fromtimestamp(self._scan_finished_at, tz=timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                    if self._scan_finished_at
                    else None
                ),
                "drm_scan_last_result": self._scan_last_result,
                "drm_scan_on_start": self.settings.drm_scan_on_start,
                "drm_scan_interval_hours": self.settings.drm_scan_interval_hours,
                "drm_scan_max_age_hours": self.settings.drm_scan_max_age_hours,
                "drm_scan_concurrency": self.settings.drm_scan_concurrency,
            }

    def watch(self, channel_id: str) -> str:
        payload = self.api_get("vapi/asset/v1", params={"channelId": channel_id, "type": "live"})
        stream = payload.get("stream") or {}
        if stream.get("drmProtected") is True:
            self.mark_drm_station(channel_id)
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
        rows = (payload or {}).get("response") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return programmes

        for ch in rows:
            if not isinstance(ch, dict):
                continue
            if ch.get("type") and ch.get("type") != "channelWithProgramAssets":
                continue
            ch_data = ch.get("data") or {}
            if not isinstance(ch_data, dict):
                continue
            channel_meta = ch_data.get("channel") or {}
            station_id = str(channel_meta.get("id") or "").strip()
            channel = channels_by_id.get(station_id) if station_id else None
            if channel is None:
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

        return programmes

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
