# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- GitHub Actions workflow to build and push the Docker image to GHCR when `Dockerfile` / app context changes on `main`
- GitHub repository renamed to [`cbodden/fbtv`](https://github.com/cbodden/fbtv) and made public
- `CREDITS.md` attributing community Fubo bridge prior art and third-party dependencies
- `CONTEXT.md` durable project context and `WORKING_MEMORY.md` session state
- Cursor rule `.cursor/rules/project-context.mdc` to load/maintain those files
- Expanded `README.md` into a full user guide (install, Emby & Jellyfin wiring, day-to-day use)
- Explicit **Emby and Jellyfin** support as equal first-class targets: `docs/JELLYFIN_SETUP.md`, `docs/MEDIA_SERVERS.md`; README / Architecture / Troubleshooting / Configuration / API / landing page / OpenAPI title rebalanced for dual-server language
- Runtime metrics: live snapshot on `/`, HTML `/status`, JSON `/status.json`, Prometheus `/metrics` (channel/DRM/EPG/request counters from in-process caches)
- `docs/STATUS.md` plus README / Architecture / Troubleshooting / Configuration / Media servers / Emby & Jellyfin setup / Security / Contributing updates for metrics

### Planned

- Optional MPEG-TS remux / stream proxy for clients that do not share egress IP with the bridge
- Richer EPG once stable Fubo schedule endpoints are confirmed in the field
- Configurable DRM allow/deny lists

## [1.0.0] - 2026-08-06

### Added

- FastAPI HTTP service exposing Emby-ready Live TV feeds
- Authenticated Fubo sign-in with persistent device id (`config/device.json`) and ~4 hour bearer token cache
- Channel lineup discovery via subscriptions APIs, with plan-manager fallback
- `GET /playlist.m3u` — M3U playlist with `tvg-id`, logos, groups, and local `/watch/{id}` stream URLs
- `GET /epg.xml` — XMLTV guide matched to playlist call signs, with in-memory TTL cache
- `GET /watch/{id}` — resolve live HLS URL and 302 redirect (same-egress IP model)
- `GET /` — HTML index with copy-paste Emby URLs
- `GET /health` — liveness check
- DRM filtering for known protected sources/call signs (Disney, Starz, Showtime, Max/HBO, and related)
- Docker image and `docker-compose.yml` with `.env` configuration
- Environment settings: `FUBO_USER`, `FUBO_PASS`, `HOST`, `PORT`, `CONFIG_DIR`, `EPG_CACHE_SECONDS`, `EPG_DAYS`
- Unit tests for M3U and XMLTV builders
- Project documentation under `docs/`

[Unreleased]: https://github.com/cbodden/fbtv/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/cbodden/fbtv/releases/tag/v1.0.0
