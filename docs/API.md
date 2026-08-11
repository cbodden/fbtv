# HTTP API reference

Base URL examples assume `http://192.168.1.10:7777`.

Interactive OpenAPI docs are also available when the server is running:

- Swagger UI: `/docs`
- OpenAPI JSON: `/openapi.json`

## `GET /`

HTML index listing playlist and EPG URLs for Emby and/or Jellyfin copy/paste.

**Response:** `200 text/html`

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
<tv generator-info-name="fubotv-emby">
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
