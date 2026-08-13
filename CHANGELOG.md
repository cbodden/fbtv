# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.8] - 2026-08-13

### Added

- `/`, `/status`, and `/status.json` warm the Fubo channel lineup; `/metrics` stays cache-only
- Docs: hygiene endpoints and multi-arch notes across README, setup guides, MEDIA_SERVERS, TROUBLESHOOTING, CONFIGURATION, SECURITY (README env table includes `ADMIN_TOKEN`)
- GitHub Actions workflow runs `tests/test_builders.py` on push/PR (`main`/`dev`)
- Multi-arch GHCR images: `linux/amd64` and `linux/arm64`
- Optional `ADMIN_TOKEN`: when set, `GET`/`POST /admin/drm-scan` require `Authorization: Bearer …` or `X-Admin-Token`
- `GET /ready` readiness probe (credentials resolvable, no live Fubo call); `/health` stays liveness-only

### Removed

- M3U `tvg-chno` (sequential 1…N). It conflicted with Emby Guide Data FuboTV channel numbers and scrambled guide↔tuner mapping; join key remains `tvg-id` = call sign
- Docs: TROUBLESHOOTING + Emby setup warn against sequential channel numbers; README guide-mismatch row

### Changed

- Image/app version **1.0.8**

## [1.0.7] - 2026-08-13

### Added

- Docs: topology sketches (README, ARCHITECTURE, Emby/Jellyfin/MEDIA_SERVERS) cover default 302 and optional `STREAM_PROXY` remux paths
- Configurable DRM allow/deny overrides via `config/drm_overrides.json` and/or `DRM_DENY_IDS` / `DRM_ALLOW_IDS` / `DRM_*_CALL_SIGNS` (deny wins; allow keeps false-positive skips in the lineup — does not decrypt DRM)
- Optional MPEG-TS remux: `STREAM_PROXY=true` makes GET `/watch/{id}` stream `video/mp2t` via ffmpeg (`-c copy`) instead of 302; `STREAM_PROXY_MAX` (default 3), `FFMPEG_PATH`; Docker image installs ffmpeg; HEAD Content-Type follows mode
- Compose on **`main`** defaults to `ghcr.io/cbodden/fbtv:latest`; the **`dev`** branch Compose should use `:dev` for pre-release
- `HEAD /watch/{id}` returns 200 (`application/vnd.apple.mpegurl` when proxy off) without calling Fubo; GET still 302s to live HLS when proxy is off
- `EPG_EMPTY_CACHE_SECONDS` (default 120): channel-only XMLTV is not held for the full `EPG_CACHE_SECONDS` hour
- `/epg` programme mapping also joins on `stationId` / `callSign` (not only `channel.id`); unmatched samples logged when 0 programmes map

### Changed

- Image/app version **1.0.7**
- Field-verified on Emby: playlist + EPG (~7600 programmes) + default 302 tune

## [1.0.6] - 2026-08-12

### Added

- Background DRM asset sweep (startup + interval + `POST /admin/drm-scan`): probe `vapi/asset`, persist DRM/playable in `config/drm_skipped.json`, clear EPG cache so M3U/XMLTV stay aligned; env `DRM_SCAN_*`
- DRM scan pacing: default concurrency **1**, `DRM_SCAN_DELAY_MS` (750), and exponential backoff on HTTP **429**
- EPG prefers live-confirmed `/epg` (`channelWithProgramAssets` parser); then `papi/v1/guide/epg`; older schedule URLs kept as fallback
- INFO-level EPG probe logging (success and empty/failed paths); `"Loaded N programmes"` is a log line, not XML content
- Emby setup recommends **Guide Data FuboTV** as the primary guide while bridge `programme_count` is `0`
- GHCR publishes on **`dev`** as `ghcr.io/cbodden/fbtv:dev` (does not move `:latest`); docs for Compose pre-release pulls
- Unit coverage for `papi` `program-cell` / `title.text`, `/epg` assets parsing, and DRM scan
- Learn `drmProtected` stations at tune time, drop them from the in-memory lineup, and persist IDs in `config/drm_skipped.json` so they stay out of `/playlist.m3u` after refresh/restart
- Lineup also treats `drmProtected` / `isDrm` flags on channel metadata as DRM (in addition to known sources/call signs)
- `FUBO_PASS_B64` and `python -m app.set_credentials` so passwords with `$` / `!` can be stored without shell/Portainer interpolation
- `pass_fp` / `pass_classes` in credential logs (SHA-256 prefix; never the password)
- `config/credentials.env` / `credentials.json` (and `FUBO_*_FILE`) so Portainer can store secrets on the volume without `$` / quote mangling; file wins over env
- Startup / 401 logs include credentials source, `pass_len`, and whether wrapping quotes were stripped (never the password)
- GitHub Actions workflow to build and push the Docker image to GHCR when `Dockerfile` / app context changes
- GitHub repository renamed to [`cbodden/fbtv`](https://github.com/cbodden/fbtv) and made public
- Docker Compose service/image and GHCR package name set to `fbtv` (was `fubo-emby` / `fubo_emby`)
- Documentation tree for public `cbodden/fbtv`, Compose/`ghcr` image `fbtv`, and GHCR pull notes
- Compose pulls `ghcr.io/cbodden/fbtv:latest` (no local build) and takes credentials from the host/stack environment (no `env_file` / `.env`)
- Portainer notes for `INVALID_USERNAME_PASSWORD` (`$` env interpolation) in `docs/TROUBLESHOOTING.md`
- `CREDITS.md` attributing community Fubo bridge prior art and third-party dependencies
- `CONTEXT.md` durable project context and `WORKING_MEMORY.md` session state
- Cursor rule `.cursor/rules/project-context.mdc` to load/maintain those files
- Expanded `README.md` into a full user guide (install, Emby & Jellyfin wiring, day-to-day use)
- Explicit **Emby and Jellyfin** support as equal first-class targets: `docs/JELLYFIN_SETUP.md`, `docs/MEDIA_SERVERS.md`; dual-server language across docs and OpenAPI
- Runtime metrics: live snapshot on `/`, HTML `/status`, JSON `/status.json`, Prometheus `/metrics`
- `docs/STATUS.md` and related docs for metrics / DRM scan admin

### Changed

- Image/app version **1.0.6**
- GitHub Actions Docker workflow triggers on **`main` and `dev`** (`:latest` still default-branch only)
- Fubo client headers aligned to current community bridge (`x-client-version` 5.40.0 / FuboPlayer 1.106.0)
- `load_dotenv(interpolate=False)` so `$` in local `.env` passwords is left alone
- Wrapping `'` / `"` around `FUBO_USER` / `FUBO_PASS` are stripped
- Docs synced for DRM pacing / 429 troubleshooting, admin scan examples, and `DRM_SCAN_*` in README

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

[Unreleased]: https://github.com/cbodden/fbtv/compare/v1.0.8...HEAD
[1.0.8]: https://github.com/cbodden/fbtv/compare/v1.0.7...v1.0.8
[1.0.7]: https://github.com/cbodden/fbtv/compare/v1.0.6...v1.0.7
[1.0.6]: https://github.com/cbodden/fbtv/compare/v1.0.0...v1.0.6
[1.0.0]: https://github.com/cbodden/fbtv/releases/tag/v1.0.0
