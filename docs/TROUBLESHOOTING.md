# Troubleshooting

## Service will not start

**Symptom:** process exits immediately mentioning `FUBO_USER` / `FUBO_PASS`.

**Fix:** create `.env` from `.env.example` and set both values. Compose must load that file (default `env_file: .env`). Service name is `fbtv` (`docker compose logs -f fbtv`).

---

## Empty playlist or HTTP 502 on `/playlist.m3u`

| Check | Action |
| --- | --- |
| Credentials | Sign in on fubo.tv in a browser with the same email/password |
| Region / plan | Confirm the account still has live TV packages |
| Logs | Look for `Sign-in failed` or channel path warnings |
| API drift | Fubo may have changed endpoints; update `app/fubo_client.py` |
| Status | `curl -sS http://127.0.0.1:7777/status.json` — look at `fubo.signed_in` / errors after a playlist attempt |

---

## Channels import but will not play (Emby or Jellyfin)

1. Confirm the channel is not DRM-filtered (premium movie nets often are)
2. On the **Emby or Jellyfin host**, open the watch URL from the M3U in VLC
3. If VLC works on that host but not through the media server, review Live TV transcoder / network settings
4. If VLC fails with the redirected CDN URL, you likely hit **IP binding**:
   - Run the bridge on the same machine as Emby/Jellyfin, or
   - Ensure they use the same public egress (no split VPN)
5. Check `/status.json` → `requests.watch_error` climbing vs `watch_ok`

v1 uses HTTP 302 redirects only (no local remux).

---

## Guide has channels but no programmes

Expected when Fubo schedule endpoints are unavailable or changed. The bridge still emits `<channel>` rows for mapping.

Workarounds:

- Retry later / lower `EPG_CACHE_SECONDS` after a code/API fix
- **Emby:** use Emby Guide Data’s Fubo lineup and map manually
- **Jellyfin:** use Schedules Direct **or** another XMLTV source (not both with bridge XMLTV at once) and map under **Live TV → Channels**
- Increase logging and inspect which EPG paths return data (`Loaded N programmes from …`)
- Confirm via status: `epg.programme_count` may be `0` while `epg.cached` is true

---

## Using status to diagnose

Before digging through logs, check the in-process snapshot:

```bash
curl -sS http://127.0.0.1:7777/status.json
curl -sS http://127.0.0.1:7777/metrics | head
```

| Observation | Likely meaning |
| --- | --- |
| `fubo.signed_in` false and `channel_count` null | No successful Fubo call since start — fix credentials / hit playlist |
| `channel_count` set, `drm_skipped_count` high | Expected for DRM packages; those channels stay out of the M3U |
| `epg.programme_count` is 0 but `epg.cached` true | Channel-only XMLTV (schedule probe empty) |
| `watch_error` climbing | DRM rejects, missing URLs, or Fubo API errors on tune |
| Status routes return 404 | Process predates metrics — restart uvicorn / Compose |

Guide: [STATUS.md](STATUS.md).

---

## Emby or Jellyfin cannot reach the bridge

- From that host: `curl -sS http://<bridge>:7777/health` (or `/status.json`)
- If Emby or Jellyfin is in Docker and the bridge is on the host, use `host.docker.internal` or the host LAN IP — not `localhost` inside the container
- Check firewall / published ports (`7777:7777` or your `PORT`)

---

## Playlist URLs point at `localhost` but Emby/Jellyfin is elsewhere

Emby and Jellyfin must fetch watch URLs as written in the M3U. Generate the playlist using a hostname they can resolve:

- Browse/fetch `playlist.m3u` via `http://<lan-ip>:7777/playlist.m3u`, or
- Put a reverse proxy in front and set `X-Forwarded-Host` / `X-Forwarded-Proto`

---

## Emby and Jellyfin both tuned / stream limits

Each server has its own “simultaneous streams” setting. Cap them so the **sum** stays within your Fubo plan. Shared egress still applies to every host that tunes. See [MEDIA_SERVERS.md](MEDIA_SERVERS.md).

---

## Device / sign-in loops

Delete `config/device.json` only as a last resort, then restart so a new device id is created. Prefer fixing credentials first.

---

## Useful curl checks

```bash
curl -sS http://127.0.0.1:7777/health
curl -sS http://127.0.0.1:7777/status.json
curl -sS http://127.0.0.1:7777/metrics | head
curl -sS http://127.0.0.1:7777/playlist.m3u | head
curl -sS http://127.0.0.1:7777/epg.xml | head
curl -sSI http://127.0.0.1:7777/watch/<stationId>
```
