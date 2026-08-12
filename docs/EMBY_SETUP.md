# Emby setup guide

Emby Premiere is required for Live TV.

This bridge (**fbtv**) is not an Emby .NET plugin. Emby and Jellyfin are equal consumers of the same **M3U** + **XMLTV** feeds — see [JELLYFIN_SETUP.md](JELLYFIN_SETUP.md) and [MEDIA_SERVERS.md](MEDIA_SERVERS.md).

## Prerequisites

1. Bridge is running and reachable from the Emby Server host
2. `http://<bridge-host>:7777/health` returns `{"status":"ok"}`
3. Optional: `http://<bridge-host>:7777/status.json` shows `fubo.signed_in` / `credentials_source` / channel counts after warming `/playlist.m3u` — see [STATUS.md](STATUS.md). If sign-in fails, use `FUBO_PASS_B64` — [CONFIGURATION.md](CONFIGURATION.md).
4. `http://<bridge-host>:7777/playlist.m3u` downloads a non-empty playlist
5. Prefer **same machine or same public egress IP** for Emby and the bridge

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

## Guide data (recommended: Emby Guide Data FuboTV)

Fubo’s private schedule APIs have been unreliable (many paths 404). **Until bridge `/epg.xml` shows a non-zero `epg.programme_count` in `/status.json`, use Emby Guide Data’s FuboTV lineup as the primary guide:**

1. Under **TV Guide Data Providers**, click **+**
2. Choose **Emby Guide Data** (not XMLTV)
3. Set your ZIP / country, then select a **FuboTV** lineup when offered (scroll — US lists are long; Guide Data plugin **1.0.18+** added FuboTV)
4. Save and refresh guide data
5. Map channels by name / call sign where Emby does not auto-match

### Optional: bridge XMLTV

You may still add **XMLTV** → `http://<bridge-host>:7777/epg.xml` for call-sign identity. From **1.0.4**, the bridge prefers `/epg` (parsed as `channelWithProgramAssets`; live field logs showed **200** here while many other schedule URLs **404**), then `papi/v1/guide/epg`. Deploy via `ghcr.io/cbodden/fbtv:dev` or a local build until merged to `main`. Check after a refresh:

```bash
curl -sS http://<bridge-host>:7777/health          # version should be 1.0.6+ for paced DRM sweep
curl -sS http://<bridge-host>:7777/status.json      # epg.programme_count
curl -sS http://<bridge-host>:7777/epg.xml | grep -c '<programme'
# "Loaded N programmes" appears in container logs, not in the XML body
```

If `programme_count` stays `0`, keep Emby Guide Data as the guide source and treat bridge XMLTV as optional.

## Playback checklist

1. Prefer a clean playlist first: `POST /admin/drm-scan?force=true` on **1.0.6+** (paced; may take several minutes), then refresh M3U + guide
2. From Emby, tune a non-DRM channel (news/sports basics usually work better than premium nets)
3. If tune fails immediately, check bridge logs for DRM or HTTP errors — a `drmProtected` station is learned into `config/drm_skipped.json` and dropped from the next playlist refresh
4. Refresh the M3U tuner after DRM learns so Emby drops dead entries
5. If logs show `vapi/asset` **429**, raise `DRM_SCAN_DELAY_MS` — see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
4. If tune starts then fails, suspect **IP binding** — move bridge onto Emby’s host/network egress
5. Confirm `/watch/{id}` in a browser/VLC on the Emby host redirects to an `.m3u8` URL

## Suggested topology

```text
Same host (best for v1 redirect model)
  Emby Server  ──LAN──►  fbtv:7777  ──►  api.fubo.tv / CDN
```

Remote Emby over Tailscale/VPN with the bridge elsewhere often breaks HLS redirects because the stream URL was minted for a different IP.

## Using Emby and Jellyfin together

Point both at the same bridge URLs. Cap combined simultaneous streams to your Fubo limit. Details: [MEDIA_SERVERS.md](MEDIA_SERVERS.md).
