# Configuration

## Environment variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `FUBO_USER` | if no credentials file | — | Fubo account email |
| `FUBO_PASS` | if no credentials file | — | Fubo account password (avoid `$` here — use `FUBO_PASS_B64`) |
| `FUBO_PASS_B64` | no | — | Base64 UTF-8 password; wins over `FUBO_PASS` (safe for `$` `!` `` ` ``) |
| `FUBO_USER_FILE` / `FUBO_PASS_FILE` | no | — | Optional paths to files containing email/password (Docker secrets style) |
| `HOST` | no | `0.0.0.0` | Bind address for uvicorn |
| `PORT` | no | `7777` | Listen port (Compose maps host `PORT` → container `7777`) |
| `CONFIG_DIR` | no | `./config` | Writable directory for device id, credentials file, and learned DRM skip list |
| `EPG_CACHE_SECONDS` | no | `3600` | Seconds to reuse generated `epg.xml` when programmes were found |
| `EPG_EMPTY_CACHE_SECONDS` | no | `120` | Seconds to reuse **channel-only** XMLTV (`programme_count` 0). `0` = do not cache empty guides |
| `EPG_DAYS` | no | `2` | Desired guide window when schedule data is available |
| `DRM_SCAN_ON_START` | no | `true` | Run a background DRM asset sweep after startup (skipped if last full scan is fresh) |
| `DRM_SCAN_CONCURRENCY` | no | `1` | Parallel `vapi/asset` probes (keep low — Fubo returns **429** when pressed) |
| `DRM_SCAN_DELAY_MS` | no | `750` | Minimum gap between probes (global pace lock) |
| `DRM_SCAN_MAX_AGE_HOURS` | no | `24` | Skip non-forced scans when `last_scan_at` is newer than this (0 = always scan) |
| `DRM_SCAN_INTERVAL_HOURS` | no | `24` | Periodic rescan interval (0 = disabled) |

Credentials must come from **one** of: `config/credentials.env`, `config/credentials.json`, `FUBO_*_FILE`, `FUBO_PASS_B64`, or `FUBO_USER`/`FUBO_PASS`. A credentials file **wins** over environment variables (Portainer-safe). `FUBO_PASS_B64` wins over plain `FUBO_PASS` in the same source.

### Docker Compose

Compose does **not** use `env_file` / a project `.env`. Alphanumeric passwords may be exported:

```bash
export FUBO_USER='you@example.com'
export FUBO_PASS='your-password'
docker compose up -d
```

Prefer a credentials file (especially Portainer) — see below.

### Portainer / special characters (`$`, `!`, etc.)

Do **not** put a raw `$` password in stack env or a hand-edited `credentials.env` (shells and Portainer still eat `$…`). Use base64 or the helper:

```bash
printf '%s' 'my$ecureP@ss' | base64 -w0; echo
```

```text
# /app/config/credentials.env
FUBO_USER=you@example.com
FUBO_PASS_B64=bXkkZWN1cmVQQHNz
```

Or write JSON without interpolation:

```bash
printf '%s\n%s\n' 'you@example.com' 'my$ecureP@ss' | docker exec -i fbtv python -m app.set_credentials
```

Then restart. Logs include `pass_fp=` (SHA-256 prefix) so you can confirm the decoded password without printing it. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

### Local Python

Copy `.env.example` to `.env` and edit (loaded by python-dotenv with **`interpolate=False`**, so `$` is not expanded):

```bash
cp .env.example .env
```

## Docker Compose

Service/container name is **`fbtv`**. Image is pulled from GHCR (no local `build`):

```yaml
services:
  fbtv:
    image: ghcr.io/cbodden/fbtv:latest
    pull_policy: always
    container_name: fbtv
    environment:
      - FUBO_USER
      - FUBO_PASS
      - FUBO_PASS_B64
      # …
    volumes:
      - ./config:/app/config
```

Useful overrides:

```bash
PORT=7788 EPG_CACHE_SECONDS=7200 EPG_EMPTY_CACHE_SECONDS=120 docker compose up -d
docker compose logs -f fbtv
```

GitHub Actions publishes `ghcr.io/cbodden/fbtv` on relevant pushes to **`main`** and **`dev`** (see `.github/workflows/docker.yml`):

| Branch | Tags |
| --- | --- |
| `main` | `latest`, `main`, `sha-<commit>` |
| `dev` | `dev`, `sha-<commit>` (does **not** move `latest`) |

```yaml
# Stable (main)
image: ghcr.io/cbodden/fbtv:latest
pull_policy: always

# Pre-release from the `dev` branch
image: ghcr.io/cbodden/fbtv:dev
pull_policy: always
```

## Runtime files

| Path | Purpose |
| --- | --- |
| `.env` | Optional local-Python secrets (gitignored); **not** used by Compose |
| `config/credentials.env` | `FUBO_USER=` plus `FUBO_PASS_B64=` (preferred) or `FUBO_PASS=` |
| `config/credentials.json` | Same secrets as JSON (`python -m app.set_credentials`) |
| `config/device.json` | Stable Fubo `x-device-id` |
| `config/drm_skipped.json` | Learned/scanned DRM station ids (+ playable records, `last_scan_at`) excluded from M3U/EPG |
| `config/.gitkeep` | Keeps empty config dir in git |

Delete `config/device.json` only if you intentionally want a new device identity (may trigger extra sign-in friction). Delete `config/drm_skipped.json` only if you want previously learned DRM stations to reappear in the M3U until they fail again.

## Reverse proxy tips

If Emby or Jellyfin reaches the bridge through a reverse proxy, forward these headers so playlist URLs use a public host both servers can resolve:

- `X-Forwarded-Host`
- `X-Forwarded-Proto`

The bridge prefers those headers when building absolute `/watch/…` URLs inside `playlist.m3u`.

## Logging

The service logs at INFO by default (sign-in, channel load counts, learned DRM stations, EPG source hits). Credential logs include `source`, `pass_len`, `pass_fp` (SHA-256 prefix), `pass_classes`, and `has_dollar` — **never** the password. Avoid enabling verbose HTTP body logging in production; responses can include tokens or stream URLs.

## Status and metrics

No extra environment variables are required. When the process is running:

| Path | Purpose |
| --- | --- |
| `/` | HTML index + live snapshot |
| `/status` | HTML status table |
| `/status.json` | JSON snapshot |
| `/metrics` | Prometheus text |
| `/health` | Liveness only |

See [STATUS.md](STATUS.md).

## DRM scan

The bridge can probe each lineup station’s live asset for `drmProtected`, persist results, and keep `/playlist.m3u` + `/epg.xml` aligned (no DRM decryption).

```bash
curl -sS http://127.0.0.1:7777/admin/drm-scan
curl -sS -X POST 'http://127.0.0.1:7777/admin/drm-scan?force=true'
```

Defaults start a background sweep on boot and every 24h (one probe at a time, 750ms pacing, 429 backoff). A fresh `last_scan_at` skips non-forced runs. Tune-time DRM learns still apply immediately. If logs show many **429** responses, raise `DRM_SCAN_DELAY_MS` (e.g. `1500`) and keep `DRM_SCAN_CONCURRENCY=1`.
