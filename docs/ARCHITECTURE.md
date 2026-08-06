# Architecture

## Role

`fubotv-emby` is a **sidecar HTTP service**, not an Emby plugin. Emby Server consumes:

1. An **M3U tuner** URL for channel discovery and tune URLs
2. An **XMLTV** URL for guide data

The bridge authenticates to Fubo with the subscriber’s credentials and translates Fubo’s private API into those two formats.

```text
┌─────────────┐     playlist.m3u / epg.xml     ┌──────────────────┐
│ Emby Server │ ─────────────────────────────► │ Fubo Emby Bridge │
│  Live TV    │ ◄───────────────────────────── │   (FastAPI)      │
└─────────────┘     M3U rows + XMLTV           └────────┬─────────┘
       │                                                │
       │  GET /watch/{id}                               │ sign-in, lineup,
       └────────────────────────────────────────────────┤ schedule, stream
                         302 → HLS URL                  ▼
                                                 ┌─────────────┐
                                                 │ api.fubo.tv │
                                                 └─────────────┘
```

## Components

| Module | Responsibility |
| --- | --- |
| `app/main.py` | HTTP routes, lifespan wiring, base URL detection |
| `app/config.py` | Environment → `Settings` |
| `app/fubo_client.py` | Device id, auth, channel list, watch URL, schedule probe |
| `app/m3u.py` | EXTINF playlist generation |
| `app/epg.py` | XMLTV generation + TTL cache |

## Auth flow

1. Load or create `CONFIG_DIR/device.json` (`x-device-id`)
2. `PUT /signin` with email/password and Android TV-style client headers
3. Cache `access_token` for about four hours
4. Send `Authorization: Bearer …` on subsequent API calls

## Channel lineup

Two discovery paths (first successful wins for a populated list):

1. **Subscriptions** — `subscriptions`, `subscriptions/products`, plus `v3/plan-manager/plans` for source metadata
2. **Plan manager fallback** — `v3/plan-manager/plans` + `user` recurly `purchased_packages`

Channels from known DRM sources/call signs are dropped before playlist generation.

## Tune path

1. Emby opens `http://bridge/watch/{stationId}` from the M3U
2. Bridge calls `vapi/asset/v1?channelId=…&type=live`
3. If `drmProtected` is true → HTTP 502
4. Otherwise **302** to the HLS URL

Fubo often binds stream URLs to the **requester’s public IP**. Emby and the bridge should share the same egress (typically same host / Docker network path).

## Guide path

1. Emby fetches `/epg.xml`
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

## Design choices

- **Sidecar over Emby plugin** — uses built-in M3U/XMLTV; simpler to deploy and debug
- **Redirect over remux (v1)** — lower CPU; requires shared egress IP
- **Call sign as `tvg-id`** — stable join key between playlist and XMLTV for Emby auto-mapping
