# Architecture

## Role

`fbtv` is a **sidecar HTTP service**, not a native Emby or Jellyfin plugin. **Emby and Jellyfin** are equal consumers of:

1. An **M3U tuner** URL for channel discovery and tune URLs
2. An **XMLTV** URL for guide data

The bridge authenticates to Fubo with the subscriber’s credentials and translates Fubo’s private API into those two formats. One process can feed Emby, Jellyfin, or both — see [MEDIA_SERVERS.md](MEDIA_SERVERS.md).

```text
┌────────────────────┐   playlist.m3u / epg.xml   ┌──────────────────────────┐
│ Emby Live TV       │ ─────────────────────────► │ Fubo → Emby & Jellyfin   │
│ and/or             │ ◄───────────────────────── │ Bridge (FastAPI)         │
│ Jellyfin Live TV   │                            └────────────┬─────────────┘
└────────────────────┘                                         │
       │                                                       │ sign-in, lineup,
       │  GET /watch/{id}                                      │ schedule, stream
       └───────────────────────────────────────────────────────┤
                         302 → HLS URL                         ▼
                                                        ┌─────────────┐
                                                        │ api.fubo.tv │
                                                        └─────────────┘
```

## Components

| Module | Responsibility |
| --- | --- |
| `app/main.py` | HTTP routes, lifespan wiring, base URL detection |
| `app/config.py` | Credentials file / `FUBO_PASS_B64` / env → `Settings` (no `$` interpolation) |
| `app/set_credentials.py` | Write `config/credentials.json` from stdin |
| `app/fubo_client.py` | Device id, `PUT /signin` (client **5.40.0**), channel list, watch URL, schedule probe |
| `app/m3u.py` | EXTINF playlist generation |
| `app/epg.py` | XMLTV generation + TTL cache |
| `app/status.py` | Status snapshot + HTML/Prometheus rendering |

## Auth flow

1. Load credentials from `config/credentials.env` or `credentials.json` (file wins), else `FUBO_PASS_B64` / `FUBO_USER`+`FUBO_PASS`
2. Load or create `CONFIG_DIR/device.json` (`x-device-id`)
3. `PUT /signin` with JSON `email`/`password` and Android TV-style headers (`x-client-version` 5.40.0)
4. Cache `access_token` for about four hours
5. Send `Authorization: Bearer …` on subsequent API calls

## Channel lineup

Two discovery paths (first successful wins for a populated list):

1. **Subscriptions** — `subscriptions`, `subscriptions/products`, plus `v3/plan-manager/plans` for source metadata
2. **Plan manager fallback** — `v3/plan-manager/plans` + `user` recurly `purchased_packages`

Channels from known DRM sources/call signs are dropped before playlist generation.

## Tune path

1. Emby or Jellyfin opens `http://bridge/watch/{stationId}` from the M3U
2. Bridge calls `vapi/asset/v1?channelId=…&type=live`
3. If `drmProtected` is true → HTTP 502
4. Otherwise **302** to the HLS URL

Fubo often binds stream URLs to the **requester’s public IP**. Emby, Jellyfin, and the bridge should share the same egress (typically same host / Docker network path).

## Guide path

1. Emby and/or Jellyfin fetch `/epg.xml`
2. Bridge loads channels, then probes authenticated schedule endpoints
3. Listings are mapped to playlist `tvg-id` (= Fubo call sign)
4. Result is cached for `EPG_CACHE_SECONDS`
5. If no schedule payload is found, XMLTV still contains `<channel>` entries so mapping can proceed

## Caching

| Data | TTL | Storage |
| --- | --- | --- |
| Bearer token | ~4 hours | Process memory |
| Channel list | 30 minutes | Process memory |
| XMLTV body | `EPG_CACHE_SECONDS` (default 1h) | Process memory |
| Device id | Permanent until deleted | `CONFIG_DIR/device.json` |
| Request counters / uptime | Process lifetime | Process memory (`app/status.py` / `main`) |

## Status and metrics

Operators can read the same in-process snapshot as:

| Path | Format |
| --- | --- |
| `/` | HTML summary on the index page |
| `/status` | HTML detail table |
| `/status.json` | JSON |
| `/metrics` | Prometheus text (`fubo_bridge_*`) |

`/health` stays liveness-only. Status fields are cache-backed (playlist/EPG/watch warm them); they do not embed secrets. See [STATUS.md](STATUS.md) and [API.md](API.md).

## Design choices

- **Sidecar over native plugins** — uses built-in M3U/XMLTV on Emby and Jellyfin; simpler to deploy and debug
- **Redirect over remux (v1)** — lower CPU; requires shared egress IP
- **Call sign as `tvg-id`** — stable join key between playlist and XMLTV for auto-mapping on both servers
- **One HTTP surface for Emby and Jellyfin** — no per-server API fork; document quirks in [MEDIA_SERVERS.md](MEDIA_SERVERS.md)
- **In-process metrics** — HTML + JSON + Prometheus without a separate metrics sidecar
- **Deploy as `fbtv`** — Compose pulls `ghcr.io/cbodden/fbtv:latest` (CI on **`main`** only)
- **Credentials on the config volume** — `FUBO_PASS_B64` / `credentials.json` so `$` is not interpolated by Portainer or shells
