"""Runtime status / metrics snapshots for HTML, JSON, and Prometheus."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from html import escape
from typing import Any


@dataclass
class RequestCounters:
    watch_ok: int = 0
    watch_error: int = 0
    playlist_ok: int = 0
    playlist_error: int = 0
    epg_ok: int = 0
    epg_error: int = 0


@dataclass
class RuntimeState:
    started_at: float = field(default_factory=time.time)
    counters: RequestCounters = field(default_factory=RequestCounters)


def build_snapshot(
    *,
    version: str,
    runtime: RuntimeState,
    fubo_stats: dict[str, Any],
    epg_stats: dict[str, Any],
    host: str,
    port: int,
    stream_proxy_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = time.time()
    uptime = max(0, int(now - runtime.started_at))
    proxy = stream_proxy_stats or {
        "enabled": False,
        "max": 0,
        "active": 0,
        "ffmpeg_path": "ffmpeg",
    }
    return {
        "status": "ok",
        "version": version,
        "uptime_seconds": uptime,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(runtime.started_at)),
        "listen": {"host": host, "port": port},
        "fubo": fubo_stats,
        "epg": epg_stats,
        "stream_proxy": proxy,
        "requests": {
            "watch_ok": runtime.counters.watch_ok,
            "watch_error": runtime.counters.watch_error,
            "playlist_ok": runtime.counters.playlist_ok,
            "playlist_error": runtime.counters.playlist_error,
            "epg_ok": runtime.counters.epg_ok,
            "epg_error": runtime.counters.epg_error,
        },
    }


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    return escape(str(value))


def render_index_html(base: str, version: str, snapshot: dict[str, Any]) -> str:
    fubo = snapshot.get("fubo") or {}
    epg = snapshot.get("epg") or {}
    req = snapshot.get("requests") or {}
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fubo Emby &amp; Jellyfin Bridge</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; line-height: 1.5; max-width: 52rem; }}
    code, a {{ word-break: break-all; }}
    li {{ margin: 0.5rem 0; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr)); gap: 0.75rem; margin: 1.25rem 0; }}
    .stat {{ border: 1px solid #ddd; padding: 0.75rem 1rem; border-radius: 6px; }}
    .stat strong {{ display: block; font-size: 1.25rem; }}
    .muted {{ color: #555; font-size: 0.9rem; }}
    nav a {{ margin-right: 1rem; }}
  </style>
</head>
<body>
  <h1>Fubo Emby &amp; Jellyfin Bridge <small>v{escape(version)}</small></h1>
  <p>Point <strong>Emby</strong> and/or <strong>Jellyfin</strong> Live TV at these URLs (one bridge can feed both):</p>
  <ul>
    <li>M3U Tuner: <a href="{escape(base)}/playlist.m3u"><code>{escape(base)}/playlist.m3u</code></a></li>
    <li>XMLTV Guide: <a href="{escape(base)}/epg.xml"><code>{escape(base)}/epg.xml</code></a></li>
  </ul>
  <p>Streams resolve through <code>{escape(base)}/watch/&lt;channel_id&gt;</code>.</p>
  <p><strong>Emby:</strong> Premiere required for Live TV.<br>
     <strong>Jellyfin:</strong> Live TV included (no Premiere equivalent).</p>

  <h2>Live snapshot</h2>
  <p class="muted">From in-process caches (warmed by playlist/EPG/watch). Details: <a href="{escape(base)}/status">/status</a></p>
  <div class="stats">
    <div class="stat"><span class="muted">Channels</span><strong>{_fmt(fubo.get("channel_count"))}</strong></div>
    <div class="stat"><span class="muted">Signed in</span><strong>{"yes" if fubo.get("signed_in") else "no"}</strong></div>
    <div class="stat"><span class="muted">DRM skipped</span><strong>{_fmt(fubo.get("drm_skipped_count"))}</strong></div>
    <div class="stat"><span class="muted">DRM learned</span><strong>{_fmt(fubo.get("drm_learned_count"))}</strong></div>
    <div class="stat"><span class="muted">DRM scan</span><strong>{"running" if fubo.get("drm_scan_running") else "idle"}</strong></div>
    <div class="stat"><span class="muted">EPG programmes</span><strong>{_fmt(epg.get("programme_count"))}</strong></div>
    <div class="stat"><span class="muted">Uptime</span><strong>{_fmt(snapshot.get("uptime_seconds"))}s</strong></div>
    <div class="stat"><span class="muted">Watch OK / err</span><strong>{_fmt(req.get("watch_ok"))} / {_fmt(req.get("watch_error"))}</strong></div>
    <div class="stat"><span class="muted">Stream proxy</span><strong>{"on" if (snapshot.get("stream_proxy") or {}).get("enabled") else "off"}</strong></div>
  </div>
  <nav>
    <a href="{escape(base)}/status">Status (HTML)</a>
    <a href="{escape(base)}/status.json">Status (JSON)</a>
    <a href="{escape(base)}/metrics">Prometheus metrics</a>
    <a href="{escape(base)}/health">Health</a>
    <a href="{escape(base)}/docs">OpenAPI</a>
  </nav>
</body>
</html>
"""


def render_status_html(base: str, snapshot: dict[str, Any]) -> str:
    fubo = snapshot.get("fubo") or {}
    epg = snapshot.get("epg") or {}
    req = snapshot.get("requests") or {}
    listen = snapshot.get("listen") or {}
    proxy = snapshot.get("stream_proxy") or {}
    rows = [
        ("Version", snapshot.get("version")),
        ("Uptime (seconds)", snapshot.get("uptime_seconds")),
        ("Started at (UTC)", snapshot.get("started_at")),
        ("Listen", f"{listen.get('host')}:{listen.get('port')}"),
        ("Fubo signed in", "yes" if fubo.get("signed_in") else "no"),
        ("Credentials source", fubo.get("credentials_source")),
        ("Token age (seconds)", fubo.get("token_age_seconds")),
        ("Token TTL remaining (seconds)", fubo.get("token_ttl_remaining_seconds")),
        ("Channel count", fubo.get("channel_count")),
        ("Channels cache age (seconds)", fubo.get("channels_cache_age_seconds")),
        ("Channels source", fubo.get("channels_source")),
        ("DRM skipped (unique)", fubo.get("drm_skipped_count")),
        ("DRM learned", fubo.get("drm_learned_count")),
        ("DRM playable (scanned)", fubo.get("drm_playable_count")),
        ("DRM last full scan", fubo.get("drm_last_scan_at")),
        ("DRM scan running", "yes" if fubo.get("drm_scan_running") else "no"),
        ("Stream proxy enabled", "yes" if proxy.get("enabled") else "no"),
        ("Stream proxy active / max", f"{proxy.get('active')} / {proxy.get('max')}"),
        ("ffmpeg path", proxy.get("ffmpeg_path")),
        ("EPG cached", "yes" if epg.get("cached") else "no"),
        ("EPG cache age (seconds)", epg.get("age_seconds")),
        ("EPG TTL (seconds)", epg.get("ttl_seconds")),
        ("EPG programmes (last build)", epg.get("programme_count")),
        ("EPG channels (last build)", epg.get("channel_count")),
        ("Playlist OK / error", f"{req.get('playlist_ok')} / {req.get('playlist_error')}"),
        ("EPG OK / error", f"{req.get('epg_ok')} / {req.get('epg_error')}"),
        ("Watch OK / error", f"{req.get('watch_ok')} / {req.get('watch_error')}"),
    ]
    body_rows = "".join(
        f"<tr><th>{escape(str(label))}</th><td>{_fmt(value)}</td></tr>" for label, value in rows
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bridge status</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; line-height: 1.5; max-width: 52rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #ddd; vertical-align: top; }}
    th {{ width: 40%; color: #333; }}
    nav a {{ margin-right: 1rem; }}
    .muted {{ color: #555; }}
  </style>
</head>
<body>
  <h1>Bridge status</h1>
  <p class="muted">In-process runtime snapshot. Does not verify Fubo credentials beyond current token/cache state.</p>
  <table>
    {body_rows}
  </table>
  <p>
    <nav>
      <a href="{escape(base)}/">Home</a>
      <a href="{escape(base)}/status.json">JSON</a>
      <a href="{escape(base)}/metrics">Prometheus</a>
      <a href="{escape(base)}/health">Health</a>
    </nav>
  </p>
</body>
</html>
"""


def render_prometheus(snapshot: dict[str, Any]) -> str:
    fubo = snapshot.get("fubo") or {}
    epg = snapshot.get("epg") or {}
    req = snapshot.get("requests") or {}
    proxy = snapshot.get("stream_proxy") or {}
    version = str(snapshot.get("version") or "unknown").replace("\\", "\\\\").replace('"', '\\"')
    lines = [
        "# HELP fubo_bridge_up Bridge process is up.",
        "# TYPE fubo_bridge_up gauge",
        "fubo_bridge_up 1",
        "# HELP fubo_bridge_info Bridge version info.",
        "# TYPE fubo_bridge_info gauge",
        f'fubo_bridge_info{{version="{version}"}} 1',
        "# HELP fubo_bridge_uptime_seconds Seconds since process start.",
        "# TYPE fubo_bridge_uptime_seconds gauge",
        f"fubo_bridge_uptime_seconds {int(snapshot.get('uptime_seconds') or 0)}",
        "# HELP fubo_bridge_signed_in Whether a Fubo bearer token is cached.",
        "# TYPE fubo_bridge_signed_in gauge",
        f"fubo_bridge_signed_in {1 if fubo.get('signed_in') else 0}",
        "# HELP fubo_bridge_channels Cached non-DRM channel count.",
        "# TYPE fubo_bridge_channels gauge",
        f"fubo_bridge_channels {int(fubo.get('channel_count') or 0)}",
        "# HELP fubo_bridge_drm_skipped Unique DRM stations skipped (lineup heuristics + learned).",
        "# TYPE fubo_bridge_drm_skipped gauge",
        f"fubo_bridge_drm_skipped {int(fubo.get('drm_skipped_count') or 0)}",
        "# HELP fubo_bridge_drm_learned Unique DRM stations learned at tune time.",
        "# TYPE fubo_bridge_drm_learned gauge",
        f"fubo_bridge_drm_learned {int(fubo.get('drm_learned_count') or 0)}",
        "# HELP fubo_bridge_stream_proxy_enabled Whether MPEG-TS remux is enabled.",
        "# TYPE fubo_bridge_stream_proxy_enabled gauge",
        f"fubo_bridge_stream_proxy_enabled {1 if proxy.get('enabled') else 0}",
        "# HELP fubo_bridge_stream_proxy_active Active ffmpeg remux processes.",
        "# TYPE fubo_bridge_stream_proxy_active gauge",
        f"fubo_bridge_stream_proxy_active {int(proxy.get('active') or 0)}",
        "# HELP fubo_bridge_stream_proxy_max Max concurrent ffmpeg remux processes.",
        "# TYPE fubo_bridge_stream_proxy_max gauge",
        f"fubo_bridge_stream_proxy_max {int(proxy.get('max') or 0)}",
        "# HELP fubo_bridge_epg_cached Whether a warm XMLTV body is cached.",
        "# TYPE fubo_bridge_epg_cached gauge",
        f"fubo_bridge_epg_cached {1 if epg.get('cached') else 0}",
        "# HELP fubo_bridge_epg_programmes Programme rows from last EPG build.",
        "# TYPE fubo_bridge_epg_programmes gauge",
        f"fubo_bridge_epg_programmes {int(epg.get('programme_count') or 0)}",
        "# HELP fubo_bridge_watch_ok_total Successful /watch redirects or remux starts.",
        "# TYPE fubo_bridge_watch_ok_total counter",
        f"fubo_bridge_watch_ok_total {int(req.get('watch_ok') or 0)}",
        "# HELP fubo_bridge_watch_error_total Failed /watch attempts.",
        "# TYPE fubo_bridge_watch_error_total counter",
        f"fubo_bridge_watch_error_total {int(req.get('watch_error') or 0)}",
        "# HELP fubo_bridge_playlist_ok_total Successful playlist builds.",
        "# TYPE fubo_bridge_playlist_ok_total counter",
        f"fubo_bridge_playlist_ok_total {int(req.get('playlist_ok') or 0)}",
        "# HELP fubo_bridge_playlist_error_total Failed playlist builds.",
        "# TYPE fubo_bridge_playlist_error_total counter",
        f"fubo_bridge_playlist_error_total {int(req.get('playlist_error') or 0)}",
        "# HELP fubo_bridge_epg_ok_total Successful EPG builds/serves.",
        "# TYPE fubo_bridge_epg_ok_total counter",
        f"fubo_bridge_epg_ok_total {int(req.get('epg_ok') or 0)}",
        "# HELP fubo_bridge_epg_error_total Failed EPG builds.",
        "# TYPE fubo_bridge_epg_error_total counter",
        f"fubo_bridge_epg_error_total {int(req.get('epg_error') or 0)}",
        "",
    ]
    return "\n".join(lines)
