"""Manual DRM allow/deny overrides (on top of scan / heuristics)."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _split_csv(raw: str | None) -> set[str]:
    if not raw or not str(raw).strip():
        return set()
    return {part.strip() for part in str(raw).split(",") if part.strip()}


def _as_str_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return _split_csv(value)
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip() for item in value if str(item).strip()}
    return set()


@dataclass(frozen=True)
class DrmOverrides:
    deny_ids: frozenset[str] = frozenset()
    allow_ids: frozenset[str] = frozenset()
    deny_call_signs: frozenset[str] = frozenset()
    allow_call_signs: frozenset[str] = frozenset()
    source: str = "none"

    def is_empty(self) -> bool:
        return not (
            self.deny_ids
            or self.allow_ids
            or self.deny_call_signs
            or self.allow_call_signs
        )

    def is_denied(self, *, station_id: str, call_sign: str | None = None) -> bool:
        sid = str(station_id).strip()
        if sid and sid in self.deny_ids:
            return True
        call = (call_sign or "").strip()
        return bool(call and call in self.deny_call_signs)

    def is_allowed(self, *, station_id: str, call_sign: str | None = None) -> bool:
        sid = str(station_id).strip()
        if sid and sid in self.allow_ids:
            return True
        call = (call_sign or "").strip()
        return bool(call and call in self.allow_call_signs)

    def runtime_stats(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "deny_ids": len(self.deny_ids),
            "allow_ids": len(self.allow_ids),
            "deny_call_signs": len(self.deny_call_signs),
            "allow_call_signs": len(self.allow_call_signs),
        }


def load_drm_overrides(config_dir: Path) -> DrmOverrides:
    """Load overrides from config/drm_overrides.json and/or DRM_* env (union)."""
    deny_ids: set[str] = set()
    allow_ids: set[str] = set()
    deny_calls: set[str] = set()
    allow_calls: set[str] = set()
    sources: list[str] = []

    path = config_dir / "drm_overrides.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read %s: %s", path, exc)
        else:
            if isinstance(data, dict):
                deny_ids |= _as_str_set(
                    data.get("deny_station_ids") or data.get("deny_ids")
                )
                allow_ids |= _as_str_set(
                    data.get("allow_station_ids") or data.get("allow_ids")
                )
                deny_calls |= _as_str_set(
                    data.get("deny_call_signs") or data.get("deny_callSigns")
                )
                allow_calls |= _as_str_set(
                    data.get("allow_call_signs") or data.get("allow_callSigns")
                )
                sources.append(str(path))
            else:
                logger.warning("%s must be a JSON object; ignoring", path)

    env_deny = _split_csv(os.environ.get("DRM_DENY_IDS"))
    env_allow = _split_csv(os.environ.get("DRM_ALLOW_IDS"))
    env_deny_cs = _split_csv(os.environ.get("DRM_DENY_CALL_SIGNS"))
    env_allow_cs = _split_csv(os.environ.get("DRM_ALLOW_CALL_SIGNS"))
    if env_deny or env_allow or env_deny_cs or env_allow_cs:
        deny_ids |= env_deny
        allow_ids |= env_allow
        deny_calls |= env_deny_cs
        allow_calls |= env_allow_cs
        sources.append("environment")

    # Deny wins over allow when both match the same id/call sign.
    allow_ids -= deny_ids
    allow_calls -= deny_calls

    source = "+".join(sources) if sources else "none"
    overrides = DrmOverrides(
        deny_ids=frozenset(deny_ids),
        allow_ids=frozenset(allow_ids),
        deny_call_signs=frozenset(deny_calls),
        allow_call_signs=frozenset(allow_calls),
        source=source,
    )
    if not overrides.is_empty():
        logger.info(
            "DRM overrides source=%s deny_ids=%s allow_ids=%s deny_call_signs=%s allow_call_signs=%s",
            overrides.source,
            len(overrides.deny_ids),
            len(overrides.allow_ids),
            len(overrides.deny_call_signs),
            len(overrides.allow_call_signs),
        )
    return overrides
