# Emby and Jellyfin

**Emby and Jellyfin are equal first-class targets.** One bridge instance serves both. There is no Emby-only or Jellyfin-only mode: both consume the same M3U tuner URL, XMLTV guide URL, and `/watch/{id}` HLS redirects.

| Topic | Emby | Jellyfin |
| --- | --- | --- |
| Live TV license | **Premiere** required | Included (no Premiere equivalent) |
| Tuner type | M3U Tuner | M3U Tuner |
| Guide type | XMLTV (and/or Emby Guide Data) | XMLTV (or Schedules Direct — not both at once) |
| Setup guide | [EMBY_SETUP.md](EMBY_SETUP.md) | [JELLYFIN_SETUP.md](JELLYFIN_SETUP.md) |
| Playlist join key | `tvg-id` = Fubo call sign | `tvg-id` = Fubo call sign |
| Shared egress with bridge | Required for v1 302 HLS | Required for v1 302 HLS |
| DRM packages | Skipped / 502 | Skipped / 502 |

## Shared URLs

Replace `<bridge-host>` and port as needed (`PORT`, default `7777`):

| Feed | URL |
| --- | --- |
| M3U tuner | `http://<bridge-host>:7777/playlist.m3u` |
| XMLTV guide | `http://<bridge-host>:7777/epg.xml` |
| Watch (in playlist) | `http://<bridge-host>:7777/watch/<stationId>` |
| Copy-paste index + snapshot | `http://<bridge-host>:7777/` |
| Status (HTML) | `http://<bridge-host>:7777/status` |
| Status (JSON) | `http://<bridge-host>:7777/status.json` |
| Prometheus metrics | `http://<bridge-host>:7777/metrics` |
| Health (liveness) | `http://<bridge-host>:7777/health` |

Status / metrics details: [STATUS.md](STATUS.md).

## Running Emby and Jellyfin against one bridge

Supported. Each server imports channels independently.

- Cap **simultaneous streams** on each tuner so the **combined** concurrency stays within your Fubo plan.
- Prefer the **same public egress IP** for the bridge and **every** server that will tune (or put remux on the roadmap if that is impossible).
- Fetch the playlist via a hostname each server can resolve; avoid baking `localhost` into the M3U unless that loopback is shared.

## Quirks that differ

| Quirk | Emby | Jellyfin |
| --- | --- | --- |
| Sparse Fubo EPG fallback | Emby Guide Data **FuboTV** lineup + manual map | Schedules Direct or third-party XMLTV + manual map; cannot combine Schedules Direct and XMLTV |
| Channel → guide mapping UI | Live TV guide provider mapping | **Dashboard → Live TV → Channels** (edit EPG channel when auto-match fails) |
| Docker reachability | LAN IP or `host.docker.internal` from the Emby container to a host-side bridge | LAN IP or `host.docker.internal` from the Jellyfin container to a host-side bridge |
| Optional M3U User-Agent | Rarely needed for this bridge | Rarely needed for this bridge (streams are Fubo CDN after 302) |

## Naming

| Kind | Current name |
| --- | --- |
| GitHub repo | [`cbodden/fbtv`](https://github.com/cbodden/fbtv) (public) |
| Compose service / container | `fbtv` (pulls GHCR; host env for `FUBO_*`) |
| GHCR image | `ghcr.io/cbodden/fbtv` |
| XMLTV `generator-info-name` | `fbtv` |

Older labels (`fubo-emby`, `fubo_emby`, `fubotv_emby`, `fubotv-emby`) are historical only. Product copy treats **Emby and Jellyfin** equally; Live TV feeds stay shared. Operator endpoints (`/status`, `/metrics`, etc.) are documented in [STATUS.md](STATUS.md).
