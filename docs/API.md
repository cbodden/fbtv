# HTTP API reference

Project: [`cbodden/fbtv`](https://github.com/cbodden/fbtv). Base URL examples assume `http://192.168.1.10:7777`.

Operator-oriented status/metrics overview: [STATUS.md](STATUS.md).

Interactive OpenAPI docs are also available when the server is running:

- Swagger UI: `/docs`
- OpenAPI JSON: `/openapi.json`

## `GET /`

HTML index with Emby/Jellyfin copy-paste URLs plus a live snapshot (channel count, sign-in, DRM skips / learned, EPG programmes, uptime, watch counters) and links to status/metrics.

**Response:** `200 text/html`

## `GET /status`

Human-readable HTML status page for the same in-process snapshot.

**Response:** `200 text/html`

## `GET /status.json`

Machine-readable JSON status (same payload as the HTML page).

**Response:** `200 application/json`

```json
{
  "status": "ok",
  "version": "1.0.9",
  "uptime_seconds": 120,
  "started_at": "2026-08-11T19:00:00Z",
  "listen": {"host": "0.0.0.0", "port": 7777},
  "fubo": {
    "signed_in": true,
    "token_age_seconds": 30,
    "token_ttl_remaining_seconds": 14370,
    "channel_count": 198,
    "channels_cache_age_seconds": 20,
    "channels_source": "subscriptions",
    "credentials_source": "/app/config/credentials.env",
    "drm_skipped_count": 12,
    "drm_learned_count": 3,
    "drm_playable_count": 180,
    "drm_overrides": {
      "source": "none",
      "deny_ids": 0,
      "allow_ids": 0,
      "deny_call_signs": 0,
      "allow_call_signs": 0
    },
    "drm_last_scan_at": "2026-08-12T22:00:00Z",
    "drm_scan_running": false
  },
  "epg": {
    "cached": true,
    "age_seconds": 10,
    "ttl_seconds": 3600,
    "programme_count": 0,
    "channel_count": 198
  },
  "stream_proxy": {
    "enabled": false,
    "max": 3,
    "active": 0,
    "ffmpeg_path": "ffmpeg"
  },
  "requests": {
    "watch_ok": 3,
    "watch_error": 0,
    "playlist_ok": 2,
    "playlist_error": 0,
    "epg_ok": 1,
    "epg_error": 0
  }
}
```

Channel / DRM fields on `/`, `/status`, and `/status.json` warm the channel lineup when needed. `/metrics` is cache-only. EPG programme counts still need `/epg.xml` (or a prior build).

## `GET /metrics`

Prometheus text exposition of key gauges/counters from the same snapshot.

**Response:** `200 text/plain; version=0.0.4`

## `GET /admin/drm-scan`

DRM sweep status (running flag, last result, learned/playable counts, settings). From **1.0.6**, settings include `delay_ms`; last result may include `rate_limited`.

When `ADMIN_TOKEN` is set, send `Authorization: Bearer <token>` or `X-Admin-Token: <token>` (otherwise open). Missing/wrong token → **401**.

**Response:** `200 application/json`

```json
{
  "running": false,
  "started_at": null,
  "finished_at": "2026-08-12T22:10:00Z",
  "last_result": {
    "status": "completed",
    "checked": 200,
    "drm": 12,
    "playable": 180,
    "errors": 3,
    "rate_limited": 5,
    "drm_learned_count": 12,
    "duration_seconds": 180.0
  },
  "drm_learned_count": 12,
  "drm_playable_count": 180,
  "drm_updated_at": "2026-08-12T22:10:00Z",
  "settings": {
    "on_start": true,
    "interval_hours": 24,
    "max_age_hours": 24,
    "concurrency": 1,
    "delay_ms": 750
  }
}
```

## `POST /admin/drm-scan`

Start a background DRM asset sweep. Query `force=true` to ignore `DRM_SCAN_MAX_AGE_HOURS` freshness and re-check previously learned stations. Probes are paced (`DRM_SCAN_DELAY_MS`) with **429** backoff so Fubo is not flooded. Same optional `ADMIN_TOKEN` auth as GET.

**Response:** `200 application/json` with `{"status":"started",...}`

**Errors:** `401` if `ADMIN_TOKEN` is set and missing/wrong; `409` if a scan is already running; `503` if not initialized.

## `GET /health`

Liveness probe. Does not verify Fubo credentials.

**Response:** `200 application/json`

```json
{"status": "ok", "version": "1.0.9"}
```

## `GET /ready`

Readiness probe: returns **200** when Fubo credentials can be resolved from the configured sources (file / env). Does **not** call Fubo. Use for orchestrator readiness; keep `/health` for liveness.

**Response:** `200 application/json`

```json
{"status": "ready", "version": "1.0.9"}
```

**Errors:** `503` with `{"status":"not_ready","reason":"missing_credentials"}` or `not_initialized`.

## `GET /playlist.m3u`

Builds an M3U of non-DRM subscribed channels (known DRM packages plus stations learned or scanned as `drmProtected`).

**Response:** `200 audio/x-mpegurl`

```text
#EXTM3U

#EXTINF:-1 tvg-id="ESPN" tvg-name="ESPN" channel-id="12345" tvg-logo="https://..." group-title="fubotv-basic",ESPN
http://192.168.1.10:7777/watch/12345
```

`tvg-id` is the Fubo call sign (XMLTV join key). Sequential `tvg-chno` is **not** emitted — it conflicted with Emby Guide Data FuboTV channel numbers.

**Errors**

| Status | When |
| --- | --- |
| `502` | Fubo auth or channel fetch failed |
| `503` | Service not initialized |

Absolute stream URLs use the request host, or `X-Forwarded-Host` / `X-Forwarded-Proto` when present.

## `GET /epg.xml`

Returns XMLTV. Channel ids equal playlist `tvg-id` values (call signs). Programme elements appear when a schedule endpoint returns usable data (from **1.0.4+**, primarily `/epg` with a `channelWithProgramAssets` parser, then `papi/v1/guide/epg`); otherwise only channels are listed.

**Response:** `200 application/xml`

```xml
<?xml version="1.0" ?>
<tv generator-info-name="fbtv">
  <channel id="ESPN">
    <display-name>ESPN</display-name>
  </channel>
  <programme start="20260806120000 +0000" stop="20260806130000 +0000" channel="ESPN">
    <title lang="en">SportsCenter</title>
  </programme>
</tv>
```

Cached for `EPG_CACHE_SECONDS` when programmes were mapped; empty (channel-only) builds use `EPG_EMPTY_CACHE_SECONDS` (default 120).

**Errors**

| Status | When |
| --- | --- |
| `502` | Fubo channel fetch failed |
| `503` | Service not initialized |

## `GET` / `HEAD /watch/{channel_id}`

**GET** resolves a live stream for the Fubo station id.

- Default (`STREAM_PROXY=false`): **302** to an HLS URL.
- With `STREAM_PROXY=true`: **200** streaming body, `Content-Type: video/mp2t` (ffmpeg remux). Caps at `STREAM_PROXY_MAX` concurrent remuxes.

**HEAD** is a probe only: **200** and **no** Fubo `vapi/asset` call (does not mint a stream or count as `watch_ok`). Content-Type is `application/vnd.apple.mpegurl` in redirect mode, or `video/mp2t` when the stream proxy is enabled.

**Parameters**

| Name | In | Description |
| --- | --- | --- |
| `channel_id` | path | Fubo station id from `channel-id` / watch URL in the M3U |

**GET response (redirect mode):** `302` with `Location` set to an HLS URL

**GET response (proxy mode):** `200` `video/mp2t` MPEG-TS stream

**HEAD response:** `200` empty body; Content-Type matches mode

**Errors (GET)**

| Status | When |
| --- | --- |
| `502` | DRM protected (station is learned and dropped from later playlists), missing URL, Fubo API error, or ffmpeg remux failure |
| `503` | Service not initialized, or stream proxy at `STREAM_PROXY_MAX` capacity |

In redirect mode, Emby/Jellyfin/VLC must fetch the redirected URL from an IP Fubo accepts. In proxy mode the bridge pulls the CDN. `curl -I` / HEAD must not be used to judge CDN playback.
