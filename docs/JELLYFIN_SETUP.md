# Jellyfin setup guide

Jellyfin Live TV is included with the server (no Premiere-style license). Official overview: [Jellyfin Live TV setup](https://jellyfin.org/docs/general/server/live-tv/setup-guide/).

This bridge (**fbtv**) is not a Jellyfin plugin. Jellyfin and Emby are equal consumers of the same **M3U** + **XMLTV** feeds. See [MEDIA_SERVERS.md](MEDIA_SERVERS.md) for comparison and dual-server notes.

## Prerequisites

1. Bridge is running and reachable from the **Jellyfin Server** host
2. `http://<bridge-host>:7777/health` returns `{"status":"ok"}`
3. Optional: `http://<bridge-host>:7777/status.json` shows `fubo.signed_in` / `credentials_source` / channel counts after warming `/playlist.m3u` — see [STATUS.md](STATUS.md). If sign-in fails, use `FUBO_PASS_B64` — [CONFIGURATION.md](CONFIGURATION.md).
4. `http://<bridge-host>:7777/playlist.m3u` downloads a non-empty playlist
5. Prefer **same machine or same public egress IP** for Jellyfin and the bridge

Use a hostname/IP Jellyfin can resolve (LAN IP or `host.docker.internal` if Jellyfin is in Docker and the bridge is on the host). Do not put `localhost` in the M3U unless Jellyfin and the bridge share that loopback.

## Add the M3U tuner

1. Open the Jellyfin **Dashboard** (admin gear)
2. Go to **Live TV**
3. Next to **Tuner Devices**, click **+**
4. Set **Tuner Type** to **M3U Tuner**
5. Set:
   - **File or URL:** `http://<bridge-host>:7777/playlist.m3u`
   - A clear name (e.g. `Fubo`)
   - **Simultaneous stream limit** matching your Fubo plan (or lower if Emby also uses this bridge)
6. Save and allow Jellyfin to import channels

### Playlist fields Jellyfin uses

| M3U attribute | Meaning |
| --- | --- |
| `tvg-id` | Joins to XMLTV `channel id` (Fubo call sign) |
| `tvg-name` / display name | Channel label |
| `tvg-logo` | Artwork when present |
| `group-title` | Package / plan grouping |
| URL line | `http://<bridge>/watch/<stationId>` |

Optional: some IPTV setups set a custom **User Agent** on the M3U tuner. This bridge does not require that for Fubo; leave the default unless you are debugging fetch failures.

## Add XMLTV guide data

1. Under **TV Guide Data Providers**, click **+**
2. Select **XMLTV** (not Schedules Direct, unless you intentionally skip the bridge EPG)
3. URL: `http://<bridge-host>:7777/epg.xml`
4. Save, then refresh guide data (Dashboard scheduled tasks / Live TV refresh, depending on version)

**Note:** Jellyfin typically allows **either** Schedules Direct **or** XMLTV as the guide provider, not both at once. Prefer the bridge XMLTV for `tvg-id` alignment; switch only if you need a denser third-party guide and will map channels manually.

## Channel mapping

When `tvg-id` matches XMLTV channel ids, Jellyfin often maps automatically.

If programmes are missing or channels are unmatched:

1. Keep the bridge XMLTV for identity (`tvg-id` = call sign)
2. Open **Dashboard → Live TV → Channels**, edit a channel, and set the EPG channel manually when auto-match fails
3. Or use Schedules Direct / another XMLTV source and map by name/call sign (you will not keep bridge XMLTV active at the same time)

## Playback checklist

1. Prefer a clean playlist first: `POST /admin/drm-scan?force=true` on bridge **1.0.6+** (paced for Fubo **429**), then refresh the M3U tuner + guide
2. From Jellyfin, tune a non-DRM channel (news/basic sports usually fare better than premium movie nets)
3. If tune fails immediately → check bridge logs for DRM or HTTP errors — a `drmProtected` station is learned into `config/drm_skipped.json` and dropped from the next playlist refresh
4. Refresh the M3U tuner after DRM learns so Jellyfin drops dead entries
5. If tune starts then fails → suspect **IP binding**; co-locate bridge and Jellyfin egress
6. On the Jellyfin host, open a `/watch/<id>` URL from the M3U in VLC (**GET**, not HEAD) and confirm it redirects to an `.m3u8`
7. Scan 429s → raise `DRM_SCAN_DELAY_MS`; see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) / [CONFIGURATION.md](CONFIGURATION.md#drm-scan)

## Suggested topology

```text
Same host (best for v1 redirect model)
  Jellyfin Server  ──LAN──►  fbtv:7777  ──►  api.fubo.tv / CDN
```

Remote Jellyfin over Tailscale/VPN with the bridge elsewhere often breaks HLS redirects because the stream URL was minted for a different IP.

## Using Jellyfin and Emby together

Point both at the same bridge URLs. Cap combined simultaneous streams to your Fubo limit. Details: [MEDIA_SERVERS.md](MEDIA_SERVERS.md).
