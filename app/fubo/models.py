"""Shared Fubo models and constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

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
