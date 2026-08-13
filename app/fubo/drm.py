"""DRM skip list, asset probe, and background sweep."""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from app.fubo.models import Channel, FuboError

logger = logging.getLogger(__name__)


class DrmMixin:
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
        if self._drm_overrides.is_allowed(station_id=sid, call_sign=call_sign):
            with self._lock:
                was = sid in self._drm_learned_ids
                self._drm_learned_ids.discard(sid)
                self._drm_skipped_ids.discard(sid)
                self._drm_skipped_count = len(self._drm_skipped_ids | self._drm_learned_ids)
                if was and save:
                    self._save_drm_state()
            logger.info(
                "Station %s is DRM-allowlisted; not adding to skip list (via=%s)",
                sid,
                via,
            )
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
        """Return ``drm``, ``ok``, ``rate_limited``, or ``error`` for a live asset probe."""
        backoff_s = (1.0, 2.0, 5.0, 10.0, 20.0)
        last_exc: FuboError | None = None
        for attempt in range(len(backoff_s) + 1):
            try:
                payload = self.api_get(
                    "vapi/asset/v1",
                    params={"channelId": str(channel_id), "type": "live"},
                    timeout=30.0,
                )
            except FuboError as exc:
                last_exc = exc
                msg = str(exc)
                if "429" in msg and attempt < len(backoff_s):
                    wait = backoff_s[attempt]
                    logger.warning(
                        "DRM probe %s rate-limited (429); backing off %.0fs (attempt %s/%s)",
                        channel_id,
                        wait,
                        attempt + 1,
                        len(backoff_s),
                    )
                    time.sleep(wait)
                    continue
                logger.debug("DRM probe %s failed: %s", channel_id, exc)
                if "429" in msg:
                    return "rate_limited"
                return "error"
            stream = payload.get("stream") or {}
            if stream.get("drmProtected") is True:
                return "drm"
            if stream.get("url"):
                return "ok"
            return "error"
        if last_exc and "429" in str(last_exc):
            return "rate_limited"
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
            "rate_limited": 0,
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
            delay_s = max(0.0, self.settings.drm_scan_delay_ms / 1000.0)
            logger.info(
                "DRM scan starting (%s stations, concurrency=%s, delay_ms=%s, force=%s)",
                len(channels),
                self.settings.drm_scan_concurrency,
                self.settings.drm_scan_delay_ms,
                force,
            )

            drm_hits = 0
            playable_hits = 0
            errors = 0
            rate_limited = 0
            checked = 0
            pace_lock = Lock()
            last_probe_at = 0.0

            def _work(ch: Channel) -> tuple[Channel, str]:
                nonlocal last_probe_at
                with pace_lock:
                    if delay_s > 0 and last_probe_at > 0:
                        wait = delay_s - (time.time() - last_probe_at)
                        if wait > 0:
                            time.sleep(wait)
                    outcome = self.probe_asset(ch.id)
                    last_probe_at = time.time()
                return ch, outcome

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
                    elif outcome == "rate_limited":
                        rate_limited += 1
                    else:
                        errors += 1
                    if checked % 25 == 0 or checked == len(channels):
                        logger.info(
                            "DRM scan progress %s/%s drm=%s playable=%s rate_limited=%s errors=%s",
                            checked,
                            len(channels),
                            drm_hits,
                            playable_hits,
                            rate_limited,
                            errors,
                        )

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
                    "rate_limited": rate_limited,
                    "drm_learned_count": len(self._drm_learned_ids),
                    "duration_seconds": round(time.time() - started, 1),
                }
            )
            logger.info(
                "DRM scan complete checked=%s drm=%s playable=%s rate_limited=%s errors=%s learned_total=%s (%.1fs)",
                checked,
                drm_hits,
                playable_hits,
                rate_limited,
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
