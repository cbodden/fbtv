# Configuration

## Environment variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `FUBO_USER` | if no credentials file | — | Fubo account email |
| `FUBO_PASS` | if no credentials file | — | Fubo account password |
| `FUBO_USER_FILE` / `FUBO_PASS_FILE` | no | — | Optional paths to files containing email/password (Docker secrets style) |
| `HOST` | no | `0.0.0.0` | Bind address for uvicorn |
| `PORT` | no | `7777` | Listen port (Compose maps host `PORT` → container `7777`) |
| `CONFIG_DIR` | no | `./config` | Writable directory for device id + optional credentials file |
| `EPG_CACHE_SECONDS` | no | `3600` | Seconds to reuse generated `epg.xml` |
| `EPG_DAYS` | no | `2` | Desired guide window when schedule data is available |

Credentials must come from **one** of: `config/credentials.env`, `config/credentials.json`, `FUBO_*_FILE`, or `FUBO_USER`/`FUBO_PASS`. A credentials file **wins** over environment variables (Portainer-safe).

### Docker Compose

Pass variables in the **host environment** (Compose does **not** use `env_file` / a project `.env`):

```bash
export FUBO_USER='you@example.com'
export FUBO_PASS='your-password'
docker compose up -d
```

### Portainer

Prefer a file on the config volume (no `$` interpolation, no quotes):

```text
# /app/config/credentials.env
FUBO_USER=you@example.com
FUBO_PASS=your-actual-password
```

Then restart. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

### Local Python

Copy `.env.example` to `.env` and edit (loaded by python-dotenv):

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
      # …
    volumes:
      - ./config:/app/config
```

Useful overrides:

```bash
PORT=7788 EPG_CACHE_SECONDS=7200 docker compose up -d
docker compose logs -f fbtv
```

GitHub Actions publishes `ghcr.io/cbodden/fbtv` on relevant pushes to `main` (see `.github/workflows/docker.yml`). Tags: `latest`, `sha-<commit>`.

## Runtime files

| Path | Purpose |
| --- | --- |
| `.env` | Optional local-Python secrets (gitignored); **not** used by Compose |
| `config/credentials.env` | Preferred Portainer/Compose secrets (`FUBO_USER=` / `FUBO_PASS=`; no quotes) |
| `config/credentials.json` | Same secrets as JSON |
| `config/device.json` | Stable Fubo `x-device-id` |
| `config/.gitkeep` | Keeps empty config dir in git |

Delete `config/device.json` only if you intentionally want a new device identity (may trigger extra sign-in friction).

## Reverse proxy tips

If Emby or Jellyfin reaches the bridge through a reverse proxy, forward these headers so playlist URLs use a public host both servers can resolve:

- `X-Forwarded-Host`
- `X-Forwarded-Proto`

The bridge prefers those headers when building absolute `/watch/…` URLs inside `playlist.m3u`.

## Logging

The service logs at INFO by default (sign-in, channel load counts, EPG source hits). Avoid enabling verbose HTTP body logging in production; responses can include tokens or stream URLs.

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
