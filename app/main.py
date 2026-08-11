"""Fubo → Emby & Jellyfin bridge: M3U tuner + XMLTV guide endpoints."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from app import __version__
from app.config import Settings, load_settings
from app.epg import EpgCache, build_epg
from app.fubo_client import FuboClient, FuboError
from app.m3u import build_m3u

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

settings: Settings | None = None
client: FuboClient | None = None
epg_cache: EpgCache | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global settings, client, epg_cache
    settings = load_settings()
    client = FuboClient(settings)
    epg_cache = EpgCache(settings.epg_cache_seconds)
    logger.info(
        "Fubo Emby & Jellyfin bridge v%s ready on %s:%s",
        __version__,
        settings.host,
        settings.port,
    )
    try:
        yield
    finally:
        if client is not None:
            client.close()


app = FastAPI(
    title="Fubo Emby & Jellyfin Bridge",
    description="M3U + XMLTV sidecar for Emby and Jellyfin Live TV (equal first-class targets; personal Fubo account).",
    version=__version__,
    lifespan=lifespan,
)


def _require_client() -> tuple[Settings, FuboClient, EpgCache]:
    if settings is None or client is None or epg_cache is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return settings, client, epg_cache


def _base_url(request: Request) -> str:
    # Prefer proxy headers when present (Docker / reverse proxy)
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_host:
        scheme = forwarded_proto or request.url.scheme
        return f"{scheme}://{forwarded_host}"
    return str(request.base_url).rstrip("/")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> str:
    base = _base_url(request)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fubo Emby &amp; Jellyfin Bridge</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; line-height: 1.5; }}
    code, a {{ word-break: break-all; }}
    li {{ margin: 0.5rem 0; }}
  </style>
</head>
<body>
  <h1>Fubo Emby &amp; Jellyfin Bridge <small>v{__version__}</small></h1>
  <p>Point <strong>Emby</strong> and/or <strong>Jellyfin</strong> Live TV at these URLs (one bridge can feed both):</p>
  <ul>
    <li>M3U Tuner: <a href="{base}/playlist.m3u"><code>{base}/playlist.m3u</code></a></li>
    <li>XMLTV Guide: <a href="{base}/epg.xml"><code>{base}/epg.xml</code></a></li>
  </ul>
  <p>Streams resolve through <code>{base}/watch/&lt;channel_id&gt;</code>.</p>
  <p><strong>Emby:</strong> Premiere required for Live TV.<br>
     <strong>Jellyfin:</strong> Live TV included (no Premiere equivalent).</p>
</body>
</html>
"""


@app.get("/playlist.m3u")
def playlist(request: Request) -> PlainTextResponse:
    _, fubo, _ = _require_client()
    try:
        channels = fubo.channels()
    except FuboError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    body = build_m3u(channels, _base_url(request))
    return PlainTextResponse(body, media_type="audio/x-mpegurl")


@app.get("/epg.xml")
def epg() -> PlainTextResponse:
    _, fubo, cache = _require_client()
    try:
        channels = fubo.channels()
        xml = build_epg(fubo, channels, cache)
    except FuboError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return PlainTextResponse(xml, media_type="application/xml")


@app.get("/watch/{channel_id}")
def watch(channel_id: str) -> RedirectResponse:
    _, fubo, _ = _require_client()
    try:
        url = fubo.watch(channel_id)
    except FuboError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return RedirectResponse(url=url, status_code=302)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
