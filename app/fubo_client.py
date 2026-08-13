"""Authenticated Fubo API client for channels, streams, and schedule data.

Implementation lives under ``app.fubo``; this module re-exports the public API
for stable imports (``from app.fubo_client import FuboClient``, etc.).
"""

from app.fubo import (
    API_BASE,
    DRM_CALL_SIGNS,
    DRM_SOURCES,
    Channel,
    FuboClient,
    FuboError,
    Programme,
)

__all__ = [
    "API_BASE",
    "Channel",
    "DRM_CALL_SIGNS",
    "DRM_SOURCES",
    "FuboClient",
    "FuboError",
    "Programme",
]
