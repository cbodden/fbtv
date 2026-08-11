# Configuration

## Environment variables

Copy `.env.example` to `.env` and edit:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `FUBO_USER` | yes | — | Fubo account email |
| `FUBO_PASS` | yes | — | Fubo account password |
| `HOST` | no | `0.0.0.0` | Bind address for uvicorn |
| `PORT` | no | `7777` | Listen port (Compose maps host `PORT` → container `7777`) |
| `CONFIG_DIR` | no | `./config` | Writable directory for device id |
| `EPG_CACHE_SECONDS` | no | `3600` | Seconds to reuse generated `epg.xml` |
| `EPG_DAYS` | no | `2` | Desired guide window when schedule data is available |

The process **refuses to start** if `FUBO_USER` or `FUBO_PASS` is missing.

## Docker Compose

Project short name / Compose **service**, **container**, and local **image** are all **`fbtv`**.

`docker-compose.yml` builds (or can pull) that image, passes credentials from `.env`, and mounts `./config`:

```yaml
services:
  fbtv:
    build: .
    image: fbtv
    container_name: fbtv
    volumes:
      - ./config:/app/config
    env_file:
      - .env
```

Useful overrides:

```bash
PORT=7788 EPG_CACHE_SECONDS=7200 docker compose up -d
docker compose logs -f fbtv
```

### Pre-built image (GHCR)

GitHub Actions publishes `ghcr.io/cbodden/fbtv` on relevant pushes to `main` (see `.github/workflows/docker.yml`):

```bash
docker pull ghcr.io/cbodden/fbtv:latest
```

Tags: `latest` (default branch) and `sha-<commit>`.

## Runtime files

| Path | Purpose |
| --- | --- |
| `.env` | Local secrets (not committed) |
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
