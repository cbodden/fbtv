"""Authenticated Fubo API client (facade over DRM / lineup / schedule mixins)."""

from __future__ import annotations

import json
import logging
import secrets
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any

import httpx

from app.config import Settings
from app.drm_overrides import load_drm_overrides
from app.fubo.drm import DrmMixin
from app.fubo.lineup import LineupMixin
from app.fubo.models import API_BASE, Channel, FuboError
from app.fubo.schedule import ScheduleMixin

logger = logging.getLogger(__name__)


class FuboClient(DrmMixin, LineupMixin, ScheduleMixin):
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
        self._drm_overrides = load_drm_overrides(settings.config_dir)
        self._scan_lock = Lock()
        self._scan_running = False
        self._scan_started_at: float | None = None
        self._scan_finished_at: float | None = None
        self._scan_last_result: dict[str, Any] | None = None

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
                "drm_overrides": self._drm_overrides.runtime_stats(),
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
                "drm_scan_delay_ms": self.settings.drm_scan_delay_ms,
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

