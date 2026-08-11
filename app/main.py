"""Fubo → Emby & Jellyfin bridge: M3U tuner + XMLTV guide endpoints."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from app import __version__
from app.config import Settings, load_settings
from app.epg import EpgCache, build_epg
from app.fubo_client import FuboClient, FuboError
from app.m3u import build_m3u
from app.status import (
    RuntimeState,
    build_snapshot,
    render_index_html,
    render_prometheus,
    render_status_html,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

settings: Settings | None = None
client: FuboClient | None = None
epg_cache: EpgCache | None = None
runtime = RuntimeState()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global settings, client, epg_cache, runtime
    settings = load_settings()
    client = FuboClient(settings)
    epg_cache = EpgCache(settings.epg_cache_seconds)
    runtime = RuntimeState()
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


def _snapshot() -> dict[str, Any]:
    cfg, fubo, cache = _require_client()
    return build_snapshot(
        version=__version__,
        runtime=runtime,
        fubo_stats=fubo.runtime_stats(),
        epg_stats=cache.runtime_stats(),
        host=cfg.host,
        port=cfg.port,
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> str:
    base = _base_url(request)
    try:
        snap = _snapshot()
    except HTTPException:
        snap = {
            "uptime_seconds": 0,
            "fubo": {},
            "epg": {},
            "requests": {},
        }
    return render_index_html(base, __version__, snap)


@app.get("/status", response_class=HTMLResponse)
def status_page(request: Request) -> str:
    return render_status_html(_base_url(request), _snapshot())


@app.get("/status.json")
def status_json() -> dict[str, Any]:
    return _snapshot()


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    body = render_prometheus(_snapshot())
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/playlist.m3u")
def playlist(request: Request) -> PlainTextResponse:
    _, fubo, _ = _require_client()
    try:
        channels = fubo.channels()
        body = build_m3u(channels, _base_url(request))
    except FuboError as exc:
        runtime.counters.playlist_error += 1
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    runtime.counters.playlist_ok += 1
    return PlainTextResponse(body, media_type="audio/x-mpegurl")


@app.get("/epg.xml")
def epg() -> PlainTextResponse:
    _, fubo, cache = _require_client()
    try:
        channels = fubo.channels()
        xml = build_epg(fubo, channels, cache)
    except FuboError as exc:
        runtime.counters.epg_error += 1
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    runtime.counters.epg_ok += 1
    return PlainTextResponse(xml, media_type="application/xml")


@app.get("/watch/{channel_id}")
def watch(channel_id: str) -> RedirectResponse:
    _, fubo, _ = _require_client()
    try:
        url = fubo.watch(channel_id)
    except FuboError as exc:
        runtime.counters.watch_error += 1
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    runtime.counters.watch_ok += 1
    return RedirectResponse(url=url, status_code=302)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
