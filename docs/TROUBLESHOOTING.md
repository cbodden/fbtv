# Troubleshooting

## Service will not start

**Symptom:** process exits immediately mentioning `FUBO_USER` / `FUBO_PASS`.

**Fix:** create `.env` from `.env.example` and set both values. Compose must load that file (default `env_file: .env`).

---

## Empty playlist or HTTP 502 on `/playlist.m3u`

| Check | Action |
| --- | --- |
| Credentials | Sign in on fubo.tv in a browser with the same email/password |
| Region / plan | Confirm the account still has live TV packages |
| Logs | Look for `Sign-in failed` or channel path warnings |
| API drift | Fubo may have changed endpoints; update `app/fubo_client.py` |

---

## Channels import in Emby but will not play

1. Confirm the channel is not DRM-filtered (premium movie nets often are)
2. On the **Emby host**, open the watch URL from the M3U in VLC
3. If VLC works on the Emby host but not through Emby, review Emby Live TV transcoder / network settings
4. If VLC fails with the redirected CDN URL, you likely hit **IP binding**:
   - Run bridge and Emby on the same machine, or
   - Ensure both use the same public egress (no split VPN)

v1 uses HTTP 302 redirects only (no local remux).

---

## Guide has channels but no programmes

Expected when Fubo schedule endpoints are unavailable or changed. The bridge still emits `<channel>` rows for mapping.

Workarounds:

- Retry later / lower `EPG_CACHE_SECONDS` after a code/API fix
- Use Emby Guide Data’s Fubo lineup and map manually
- Increase logging and inspect which EPG paths return data (`Loaded N programmes from …`)

---

## Emby cannot reach the bridge

- From the Emby host: `curl -sS http://<bridge>:7777/health`
- If Emby is in Docker and the bridge is on the host, use `host.docker.internal` or the host LAN IP — not `localhost` inside the Emby container
- Check firewall / published ports (`7777:7777`)

---

## Playlist URLs point at `localhost` but Emby is elsewhere

Emby must fetch watch URLs as written in the M3U. Generate the playlist using the hostname Emby can resolve:

- Browse/fetch `playlist.m3u` via `http://<lan-ip>:7777/playlist.m3u`, or
- Put a reverse proxy in front and set `X-Forwarded-Host` / `X-Forwarded-Proto`

---

## Device / sign-in loops

Delete `config/device.json` only as a last resort, then restart so a new device id is created. Prefer fixing credentials first.

---

## Useful curl checks

```bash
curl -sS http://127.0.0.1:7777/health
curl -sS http://127.0.0.1:7777/playlist.m3u | head
curl -sS http://127.0.0.1:7777/epg.xml | head
curl -sSI http://127.0.0.1:7777/watch/<stationId>
```
