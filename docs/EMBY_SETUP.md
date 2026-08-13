# Emby setup guide

Emby Premiere is required for Live TV.

This bridge (**fbtv**) is not an Emby .NET plugin. Emby and Jellyfin are equal consumers of the same **M3U** + **XMLTV** feeds — see [JELLYFIN_SETUP.md](JELLYFIN_SETUP.md) and [MEDIA_SERVERS.md](MEDIA_SERVERS.md).

## Prerequisites

1. Bridge is running and reachable from the Emby Server host
2. `http://<bridge-host>:7777/health` returns `{"status":"ok"}`; `/ready` returns `{"status":"ready"}` when credentials are configured
3. Optional: `http://<bridge-host>:7777/status.json` shows `fubo.signed_in` / `credentials_source` / channel counts (status endpoints warm the lineup) — see [STATUS.md](STATUS.md). If sign-in fails, use `FUBO_PASS_B64` — [CONFIGURATION.md](CONFIGURATION.md).
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
5. Map channels by name / call sign where Emby does not auto-match. Do **not** expect sequential M3U channel numbers — the bridge omits `tvg-chno` so Guide Data FuboTV numbers are not overridden.

### Optional: bridge XMLTV

You may still add **XMLTV** → `http://<bridge-host>:7777/epg.xml` for call-sign identity. From **1.0.4**, the bridge prefers `/epg` (parsed as `channelWithProgramAssets`; live field logs showed **200** here while many other schedule URLs **404**), then `papi/v1/guide/epg`. Prefer `ghcr.io/cbodden/fbtv:latest` (**1.0.9+**) or `:dev` for pre-release. Check after a refresh:

```bash
curl -sS http://<bridge-host>:7777/health          # 1.0.9+ fubo package / pytest era; 1.0.8+ hygiene / ready / admin token
curl -sS http://<bridge-host>:7777/status.json      # epg.programme_count
curl -sS http://<bridge-host>:7777/epg.xml | grep -c '<programme'
# "Loaded N programmes" appears in container logs, not in the XML body
```

If `programme_count` stays `0`, keep Emby Guide Data as the guide source and treat bridge XMLTV as optional. Empty (channel-only) XMLTV is cached only for `EPG_EMPTY_CACHE_SECONDS` (default 120), not the full hour — see [CONFIGURATION.md](CONFIGURATION.md).

## Playback checklist

1. Prefer a clean playlist first: `POST /admin/drm-scan?force=true` on **1.0.6+** (paced; may take several minutes; send `Authorization: Bearer …` or `X-Admin-Token` if `ADMIN_TOKEN` is set), then refresh M3U + guide
2. From Emby, tune a non-DRM channel (news/sports basics usually work better than premium nets)
3. If tune fails immediately, check bridge logs for DRM or HTTP errors — a `drmProtected` station is learned into `config/drm_skipped.json` and dropped from the next playlist refresh
4. Refresh the M3U tuner after DRM learns so Emby drops dead entries. To keep a false-positive skip in the playlist, add an **allow** override ([CONFIGURATION.md](CONFIGURATION.md#drm-allow--deny-overrides)); real DRM still cannot play.
5. If logs show `vapi/asset` **429**, raise `DRM_SCAN_DELAY_MS` — see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
6. If tune starts then fails, suspect **IP binding** — move bridge onto Emby’s host/network egress, **or** set `STREAM_PROXY=true` (MPEG-TS remux; see [CONFIGURATION.md](CONFIGURATION.md))
7. Confirm `/watch/{id}` in a browser/VLC on the Emby host (**GET**): default mode redirects to an `.m3u8`; with `STREAM_PROXY=true` expect a `video/mp2t` stream. `HEAD` / `curl -I` is a 200 probe and does not mint a stream.

## Suggested topology

```text
Same host / same egress (best for default 302 redirect)
  Emby Server  ──LAN──►  fbtv:7777  ──302──►  Fubo CDN
                         │
                         └── api.fubo.tv (auth / lineup / asset)

Split egress (optional remux)
  Emby elsewhere  ──►  fbtv:7777 (STREAM_PROXY=true)  ──►  Fubo CDN
```

Remote Emby over Tailscale/VPN with the bridge elsewhere often breaks **302** HLS redirects because the stream URL was minted for a different IP — use shared egress or `STREAM_PROXY`.

## Using Emby and Jellyfin together

Point both at the same bridge URLs. Cap combined simultaneous streams to your Fubo limit. Details: [MEDIA_SERVERS.md](MEDIA_SERVERS.md).
