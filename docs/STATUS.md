# Status and metrics

Project: **fbtv** ([cbodden/fbtv](https://github.com/cbodden/fbtv)).

The bridge exposes an **in-process** runtime snapshot in three forms:

| Path | Format | Audience |
| --- | --- | --- |
| `/` | HTML (summary cards + links) | Operators in a browser |
| `/status` | HTML (full table) | Operators in a browser |
| `/status.json` | JSON | Scripts / dashboards |
| `/metrics` | Prometheus text (`0.0.4`) | Prometheus / scrapers |

`/health` remains a **liveness-only** probe (`status` + `version`). It does not report channel counts or verify Fubo credentials.

Full field reference and examples: [API.md](API.md).

## What is reported

| Area | Fields |
| --- | --- |
| Process | `version`, `uptime_seconds`, `started_at`, listen `host`/`port` |
| Fubo | `signed_in`, token age / TTL remaining, `channel_count`, channels cache age, `channels_source`, `credentials_source`, `drm_skipped_count`, `drm_learned_count` |
| EPG | `cached`, cache age, TTL, last-build `programme_count` / `channel_count` |
| Requests | OK/error counters for playlist, EPG, and watch |

Channel, DRM, and EPG fields come from **caches** warmed by `/playlist.m3u`, `/epg.xml`, or `/watch/{id}`. Opening `/status` alone does not force a Fubo refresh. After restart, fetch the playlist (or EPG) once to populate counts. `drm_learned_count` reflects stations persisted in `config/drm_skipped.json` from prior `drmProtected` tunes.

Snapshots **do not** include passwords, bearer tokens, or raw stream URLs.

## Quick checks

```bash
curl -sS http://127.0.0.1:7777/status.json | head
curl -sS http://127.0.0.1:7777/metrics | head
open http://127.0.0.1:7777/          # or browse /
open http://127.0.0.1:7777/status
```

## Prometheus notes

- Exposition format: `text/plain; version=0.0.4`
- Metric names are prefixed with `fubo_bridge_` (for example `fubo_bridge_channels`, `fubo_bridge_watch_ok_total`)
- Scrape over a trusted network only; treat like any other unauthenticated LAN metrics endpoint

## Implementation

| Module | Role |
| --- | --- |
| `app/status.py` | Snapshot builder + HTML / Prometheus renderers |
| `app/main.py` | Routes `/`, `/status`, `/status.json`, `/metrics`; request counters |
| `app/fubo_client.py` | `runtime_stats()` (token, channels, DRM skips, credentials source path — not the password) |
| `app/epg.py` | `EpgCache.runtime_stats()` |
