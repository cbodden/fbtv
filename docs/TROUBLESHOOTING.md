# Troubleshooting

## Service will not start

**Symptom:** process exits immediately mentioning `FUBO_USER` / `FUBO_PASS`.

**Fix:** provide credentials via `config/credentials.env` (`FUBO_USER` + `FUBO_PASS_B64` preferred), `config/credentials.json`, or export `FUBO_USER` / `FUBO_PASS` / `FUBO_PASS_B64`. Compose does not load a project `.env`. For local Python, create `.env` from `.env.example` (interpolation is off). Service name is `fbtv` (`docker compose logs -f fbtv`).

---

## Sign-in 401 `INVALID_USERNAME_PASSWORD` (especially Portainer)

Fubo rejected the email/password the container sent. The bridge is up; auth failed at `PUT https://api.fubo.tv/signin`.

**Do not wrap the password in quotes** in Portainer. Quotes become part of the value (`'secret'` ≠ `secret`). `$$` in the Portainer UI is also unreliable.

### Portainer — use a credentials file (recommended)

Compose never interpolates files on the `config` volume. Image **1.0.2+** prefers **base64** so `$` cannot be eaten:

```bash
printf '%s' 'my$ecureP@ss' | base64 -w0; echo
```

```text
# /app/config/credentials.env
FUBO_USER=you@example.com
FUBO_PASS_B64=<paste-base64-here>
```

Or:

```bash
printf '%s\n%s\n' 'you@example.com' 'my$ecureP@ss' | docker exec -i fbtv python -m app.set_credentials
```

Restart once. Confirm `pass_len` and `pass_fp` in the logs:

```bash
python3 -c "import hashlib; p=r'my$ecureP@ss'; print(len(p), hashlib.sha256(p.encode()).hexdigest()[:12])"
```

If `pass_fp` matches but Fubo still returns 401, the unofficial API is rejecting that password (reset on fubo.tv and try again once).

### Other checks

| Check | Action |
| --- | --- |
| Browser login | Same email/password on [fubo.tv](https://www.fubo.tv/) |
| `pass_fp` mismatch | The file/env password is not the one you think; regenerate `FUBO_PASS_B64` with `printf '%s' '…' \| base64 -w0` |
| Account lockout | Many 401s can block the account; reset password / wait / contact Fubo |
| VPN | Sign-in from a normal residential egress; Fubo often blocks datacenter/VPN IPs |
| Image still old / missing EPG fix | GHCR `:latest` is **`main`** only; for pre-release use `image: ghcr.io/cbodden/fbtv:dev` + `pull_policy: always`, then `docker compose pull` |

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
2. If `/watch/{id}` returns `"Stream is DRM protected"`, the bridge learns that station id (`config/drm_skipped.json`) and drops it from the next `/playlist.m3u` — refresh the M3U tuner in Emby/Jellyfin to clear the dead entry
3. On the **Emby or Jellyfin host**, open the watch URL from the M3U in VLC
4. If VLC works on that host but not through the media server, review Live TV transcoder / network settings
5. If VLC fails with the redirected CDN URL, you likely hit **IP binding**:
   - Run the bridge on the same machine as Emby/Jellyfin, or
   - Ensure they use the same public egress (no split VPN)
6. Check `/status.json` → `requests.watch_error` climbing vs `watch_ok`

v1 uses HTTP 302 redirects only (no local remux).

---

## Guide has channels but no programmes

Expected when Fubo schedule endpoints are unavailable or changed. The bridge still emits `<channel>` rows for mapping. From **1.0.4** the primary probe is `/epg` (parsed as `channelWithProgramAssets`); `papi/v1/guide/epg` and older paths remain as fallback. Field logs showed `/epg` **200** while many other URLs **404** — older builds mapped zero programmes from that 200 because the JSON shape was not parsed.

Workarounds:

- **Emby (recommended while programmes are empty):** Emby Guide Data **FuboTV** lineup + manual map — see [EMBY_SETUP.md](EMBY_SETUP.md)
- **Jellyfin:** use Schedules Direct **or** another XMLTV source (not both with bridge XMLTV at once) and map under **Live TV → Channels**
- After deploying 1.0.4+ (`:dev` or a local build), refresh `/epg.xml` and check logs for `Loaded N programmes from epg` / `EPG schedule complete`
- Lower `EPG_CACHE_SECONDS` temporarily after an API fix so a stale empty body is not reused
- Confirm via status: `epg.programme_count` may be `0` while `epg.cached` is true
- Remember: `"Loaded N programmes"` appears in **container logs**, not inside the XML body

---

## Using status to diagnose

Before digging through logs, check the in-process snapshot:

```bash
curl -sS http://127.0.0.1:7777/status.json
curl -sS http://127.0.0.1:7777/metrics | head
```

| Observation | Likely meaning |
| --- | --- |
| `fubo.signed_in` false and `channel_count` null | No successful Fubo call since start — check `credentials_source`, `pass_fp` in logs, then hit playlist |
| `channel_count` set, `drm_skipped_count` / `drm_learned_count` high | Expected for DRM packages; those channels stay out of the M3U after learn/refresh |
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
