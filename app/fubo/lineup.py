"""Channel lineup discovery (subscriptions + plan-manager)."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.fubo.models import Channel, DRM_CALL_SIGNS, DRM_SOURCES, FuboError

logger = logging.getLogger(__name__)


class LineupMixin:
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

        sid = str(station_id)
        call = (call_sign or sid).strip()
        if self._drm_overrides.is_denied(station_id=sid, call_sign=call):
            self._drm_skipped_ids.add(sid)
            return
        if self._is_drm_channel(raw) and not self._drm_overrides.is_allowed(
            station_id=sid, call_sign=call
        ):
            self._drm_skipped_ids.add(sid)
            return

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
            ch = stations[sid]
            if self._drm_overrides.is_denied(station_id=sid, call_sign=ch.call_sign):
                del stations[sid]
                self._drm_skipped_ids.add(sid)
                continue
            if sid in learned and not self._drm_overrides.is_allowed(
                station_id=sid, call_sign=ch.call_sign
            ):
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
            if not self._drm_overrides.is_empty():
                logger.info(
                    "DRM overrides active source=%s deny=%s/%s allow=%s/%s",
                    self._drm_overrides.source,
                    len(self._drm_overrides.deny_ids),
                    len(self._drm_overrides.deny_call_signs),
                    len(self._drm_overrides.allow_ids),
                    len(self._drm_overrides.allow_call_signs),
                )

        return sorted_channels
