# Documentation index

Public repository: [`cbodden/fbtv`](https://github.com/cbodden/fbtv) · Docker image: `fbtv` / `ghcr.io/cbodden/fbtv`

| Document | Contents |
| --- | --- |
| [../README.md](../README.md) | **Primary guide:** what it does, install (Compose + GHCR), Emby & Jellyfin setup, status/metrics, day-to-day use |
| [../CHANGELOG.md](../CHANGELOG.md) | Version history |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, data flow, caching, metrics, DRM scan |
| [CONFIGURATION.md](CONFIGURATION.md) | Env vars, `FUBO_PASS_B64`, `EPG_EMPTY_CACHE_SECONDS`, `DRM_SCAN_*`, Compose GHCR `:latest` / `:dev`, Portainer credentials file |
| [MEDIA_SERVERS.md](MEDIA_SERVERS.md) | Emby & Jellyfin as equal targets; one bridge for both; naming |
| [EMBY_SETUP.md](EMBY_SETUP.md) | Emby Live TV wiring |
| [JELLYFIN_SETUP.md](JELLYFIN_SETUP.md) | Jellyfin Live TV wiring |
| [STATUS.md](STATUS.md) | Status / metrics (`/`, `/status`, `/status.json`, `/metrics`, `/admin/drm-scan`) |
| [API.md](API.md) | HTTP endpoints and example payloads (incl. DRM scan admin) |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common failures, status diagnostics, curl checks |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Dev setup and contribution guidelines |
| [../SECURITY.md](../SECURITY.md) | Credentials and threat model |
| [../CREDITS.md](../CREDITS.md) | Attribution for prior art and dependencies |
| [../CONTEXT.md](../CONTEXT.md) | Durable project context for humans/agents |
| [../WORKING_MEMORY.md](../WORKING_MEMORY.md) | Current focus, blockers, next actions |

## Version

Current release: **1.0.6** on `main` / `:latest` (see `CHANGELOG.md`). Pre-release: `:dev`.
