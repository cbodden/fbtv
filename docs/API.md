# HTTP API reference

Project: [`cbodden/fbtv`](https://github.com/cbodden/fbtv). Base URL examples assume `http://192.168.1.10:7777`.

Operator-oriented status/metrics overview: [STATUS.md](STATUS.md).

Interactive OpenAPI docs are also available when the server is running:

- Swagger UI: `/docs`
- OpenAPI JSON: `/openapi.json`

## `GET /`

HTML index with Emby/Jellyfin copy-paste URLs plus a live snapshot (channel count, sign-in, DRM skips, EPG programmes, uptime, watch counters) and links to status/metrics.

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
  "version": "1.0.0",
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
    "drm_skipped_count": 12
  },
  "epg": {
    "cached": true,
    "age_seconds": 10,
    "ttl_seconds": 3600,
    "programme_count": 0,
    "channel_count": 198
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

Channel / DRM / EPG fields reflect **cached** state (warmed by `/playlist.m3u`, `/epg.xml`, or `/watch/{id}`). They do not force a Fubo refresh.

## `GET /metrics`

Prometheus text exposition of key gauges/counters from the same snapshot.

**Response:** `200 text/plain; version=0.0.4`

## `GET /health`

Liveness probe. Does not verify Fubo credentials.

**Response:** `200 application/json`

```json
{"status": "ok", "version": "1.0.0"}
```

## `GET /playlist.m3u`

Builds an M3U of non-DRM subscribed channels.

**Response:** `200 audio/x-mpegurl`

```text
#EXTM3U

#EXTINF:-1 tvg-id="ESPN" tvg-name="ESPN" channel-id="12345" tvg-logo="https://..." group-title="fubotv-basic",ESPN
http://192.168.1.10:7777/watch/12345
```

**Errors**

| Status | When |
| --- | --- |
| `502` | Fubo auth or channel fetch failed |
| `503` | Service not initialized |

Absolute stream URLs use the request host, or `X-Forwarded-Host` / `X-Forwarded-Proto` when present.

## `GET /epg.xml`

Returns XMLTV. Channel ids equal playlist `tvg-id` values (call signs). Programme elements appear when a schedule endpoint returns usable data; otherwise only channels are listed.

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

Cached for `EPG_CACHE_SECONDS` after a successful build.

**Errors**

| Status | When |
| --- | --- |
| `502` | Fubo channel fetch failed |
| `503` | Service not initialized |

## `GET /watch/{channel_id}`

Resolves a live stream for the Fubo station id and redirects.

**Parameters**

| Name | In | Description |
| --- | --- | --- |
| `channel_id` | path | Fubo station id from `channel-id` / watch URL in the M3U |

**Response:** `302` with `Location` set to an HLS URL

**Errors**

| Status | When |
| --- | --- |
| `502` | DRM protected, missing URL, or Fubo API error |
| `503` | Service not initialized |

Emby, Jellyfin, or VLC must then fetch the redirected URL. That fetch typically must originate from an IP Fubo accepts for the minted stream.
