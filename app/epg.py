"""XMLTV EPG builder for Emby."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from threading import Lock
from xml.dom import minidom

from app.fubo_client import Channel, FuboClient, Programme


class EpgCache:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._lock = Lock()
        self._xml: str | None = None
        self._built_at = 0.0

    def get(self) -> str | None:
        with self._lock:
            if self._xml and (time.time() - self._built_at) < self.ttl_seconds:
                return self._xml
            return None

    def set(self, xml: str) -> None:
        with self._lock:
            self._xml = xml
            self._built_at = time.time()

    def clear(self) -> None:
        with self._lock:
            self._xml = None
            self._built_at = 0.0


def build_xmltv(channels: list[Channel], programmes: list[Programme]) -> str:
    root = ET.Element(
        "tv",
        {
            "generator-info-name": "fubotv-emby",
            "generator-info-url": "https://github.com/local/fubotv-emby",
        },
    )

    for channel in channels:
        ch_el = ET.SubElement(root, "channel", {"id": channel.call_sign})
        display = ET.SubElement(ch_el, "display-name")
        display.text = channel.name
        if channel.logo:
            ET.SubElement(ch_el, "icon", {"src": channel.logo})

    for programme in programmes:
        prog_el = ET.SubElement(
            root,
            "programme",
            {
                "start": _xmltv_time(programme.start),
                "stop": _xmltv_time(programme.stop),
                "channel": programme.channel_id,
            },
        )
        title = ET.SubElement(prog_el, "title", {"lang": "en"})
        title.text = programme.title
        if programme.description:
            desc = ET.SubElement(prog_el, "desc", {"lang": "en"})
            desc.text = programme.description
        for category in programme.categories:
            cat = ET.SubElement(prog_el, "category", {"lang": "en"})
            cat.text = category

    rough = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(rough)
    return parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def build_epg(client: FuboClient, channels: list[Channel], cache: EpgCache) -> str:
    cached = cache.get()
    if cached is not None:
        return cached

    programmes = client.schedule(channels)
    xml = build_xmltv(channels, programmes)
    cache.set(xml)
    return xml


def _xmltv_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y%m%d%H%M%S +0000")
