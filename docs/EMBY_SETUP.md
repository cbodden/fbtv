# Emby setup guide

Emby Premiere is required for Live TV.

This bridge is not an Emby .NET plugin. Emby and Jellyfin are equal consumers of the same **M3U** + **XMLTV** feeds — see [JELLYFIN_SETUP.md](JELLYFIN_SETUP.md) and [MEDIA_SERVERS.md](MEDIA_SERVERS.md).

## Prerequisites

1. Bridge is running and reachable from the Emby Server host
2. `http://<bridge-host>:7777/health` returns `{"status":"ok"}`
3. `http://<bridge-host>:7777/playlist.m3u` downloads a non-empty playlist
4. Prefer **same machine or same public egress IP** for Emby and the bridge

## Add the M3U tuner

1. Open **Emby Dashboard → Live TV**
2. Under **Tuner Devices**, click **+**
3. Select **M3U Tuner**
4. Set:
   - **File or URL**: `http://<bridge-host>:7777/playlist.m3u`
   - A clear name (e.g. `Fubo`)
   - Simultaneous stream limit matching your Fubo plan
5. Save and allow Emby to import channels

### Playlist fields Emby uses

| M3U attribute | Meaning |
| --- | --- |
| `tvg-id` | Joins to XMLTV `channel id` (Fubo call sign) |
| `tvg-name` / display name | Channel label |
| `tvg-logo` | Channel artwork when present |
| `group-title` | Package / plan grouping (imported as tags) |
| URL line | `http://<bridge>/watch/<stationId>` |

## Add XMLTV guide data

1. Under **TV Guide Data Providers**, click **+**
2. Select **XMLTV**
3. URL: `http://<bridge-host>:7777/epg.xml`
4. Choose a refresh interval (daily is typical; bridge caches EPG for `EPG_CACHE_SECONDS`)
5. Save and refresh guide data

## Channel mapping

When `tvg-id` matches XMLTV channel ids, Emby often maps automatically.

If listings are sparse (schedule API unavailable):

1. Keep the bridge XMLTV for channel identity, **or**
2. Add Emby Guide Data and select a **FuboTV** lineup (when offered for your ZIP), then map channels manually by name/call sign

## Playback checklist

1. From Emby, tune a non-DRM channel (news/sports basics usually work better than premium nets)
2. If tune fails immediately, check bridge logs for DRM or HTTP errors
3. If tune starts then fails, suspect **IP binding** — move bridge onto Emby’s host/network egress
4. Confirm `/watch/{id}` in a browser/VLC on the Emby host redirects to an `.m3u8` URL

## Suggested topology

```text
Same host (best for v1 redirect model)
  Emby Server  ──LAN──►  fubo-emby:7777  ──►  api.fubo.tv / CDN
```

Remote Emby over Tailscale/VPN with the bridge elsewhere often breaks HLS redirects because the stream URL was minted for a different IP.

## Using Emby and Jellyfin together

Point both at the same bridge URLs. Cap combined simultaneous streams to your Fubo limit. Details: [MEDIA_SERVERS.md](MEDIA_SERVERS.md).
