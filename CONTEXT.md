# Project context

Durable facts for humans and agents working on this repo. For ephemeral session state, see [WORKING_MEMORY.md](WORKING_MEMORY.md). Update this file when architecture or product decisions change.

**Synced from:** `docs/` + root docs on 2026-08-11 (Compose pull-from-GHCR + host-env credentials).

## What this is

- **Name:** Fubo → Emby & Jellyfin Bridge — short name **`fbtv`**
- **GitHub:** https://github.com/cbodden/fbtv (public)
- **Docker:** Compose service/container `fbtv` pulls `ghcr.io/cbodden/fbtv:latest` (`pull_policy: always`); credentials via host env (no `env_file` / `.env`); CI: `.github/workflows/docker.yml`
- **Workspace:** `/home/cbodden/git/mine/fubo_emby` (local folder may still use the old path; also referenced historically as `/Users/cesarbodden/git/work/fubo_emby`, `/Users/cesarbodden/ai/fubotv_emby`)
- **Historical names:** `fubo_emby`, `fubo-emby`, `fubotv_emby`, `fubotv-emby` (docs only)
- **Version:** 1.0.2 (`app/__version__`; see `CHANGELOG.md`)
- **Kind:** Python FastAPI **sidecar**, not a native Emby or Jellyfin plugin
- **Purpose:** Authenticate with a personal Fubo account; serve **Emby and Jellyfin** Live TV (equal first-class targets) via:
  - `GET /playlist.m3u` → M3U Tuner
  - `GET /epg.xml` → XMLTV guide
  - `GET /watch/{id}` → 302 to live HLS
  - `GET /` → HTML index with copy-paste URLs + live snapshot
  - `GET /status` → HTML status table
  - `GET /status.json` → JSON status snapshot
  - `GET /metrics` → Prometheus metrics
  - `GET /health` → `{"status":"ok","version":"…"}` (liveness only; does not verify Fubo credentials)
  - `GET /docs` / `/openapi.json` → FastAPI OpenAPI UI

**Emby:** Premiere required for Live TV. **Jellyfin:** Live TV included. One bridge instance can feed either or both — see `docs/MEDIA_SERVERS.md`. Operator metrics: `docs/STATUS.md`.

## Origin / session summary

Built from an empty workspace (2026-08-06) after the user chose:

1. Media-server integration via **sidecar** (not a native plugin)
2. **Python** as the language
3. Outputs both servers expect: **playlist.m3u** + **epg.xml** (initially framed for Emby; Jellyfin uses the same formats)

Implementation patterns for Fubo auth/lineup/watch were informed by community vlc-bridge projects (see `CREDITS.md`).

**2026-08-11:** Documented Emby and Jellyfin as equal first-class consumers; rebalanced README and docs away from Emby-only framing. HTTP API unchanged.

**Status:** v1 implementation and documentation complete. Live Fubo + Emby/Jellyfin smoke test not yet run.

## Non-goals (v1)

- Native Emby `ITunerHost` or Jellyfin Live TV plugins
- DRM decryption / playback of Disney, Starz, Showtime, Max/HBO, etc.
- MPEG-TS remux via streamlink/ffmpeg (planned under Unreleased)
- Public redistribution of streams or credentials
- Gracenote / Schedules Direct as a first-class guide path (Emby Guide Data / Jellyfin Schedules Direct may be used separately)

## Stack

| Layer | Choice |
| --- | --- |
| Language | Python 3.11+ (dev venv used 3.14 locally) |
| HTTP | FastAPI + Uvicorn |
| Fubo HTTP | httpx |
| Config | python-dotenv / env vars |
| Deploy | Docker Compose pulls `ghcr.io/cbodden/fbtv:latest` (host env for secrets); CI builds GHCR via `.github/workflows/docker.yml` |

## Key paths

```text
app/main.py                 # routes, lifespan, base URL detection
app/fubo_client.py          # auth, channels, watch, schedule probe
app/m3u.py                  # playlist builder
app/epg.py                  # XMLTV + TTL cache
app/status.py               # status snapshot + HTML/Prometheus helpers
app/config.py               # Settings
app/__init__.py             # __version__
docs/                       # full documentation (source for this file)
docs/MEDIA_SERVERS.md       # Emby & Jellyfin equal targets
docs/EMBY_SETUP.md
docs/JELLYFIN_SETUP.md
docs/STATUS.md              # status / metrics operator guide
CREDITS.md                  # attribution (required when borrowing patterns)
CONTEXT.md                  # this file
WORKING_MEMORY.md           # session / next actions
.cursor/rules/project-context.mdc
tests/test_builders.py
Dockerfile
docker-compose.yml
.github/workflows/docker.yml   # build + push ghcr.io/cbodden/fbtv
.env.example
```

## HTTP surface (from `docs/API.md`)

| Path | Behavior |
| --- | --- |
| `/` | HTML index; copy-paste playlist/EPG URLs + live snapshot; links to status/metrics |
| `/status` | Human HTML status page (in-process caches/counters) |
| `/status.json` | JSON status (same snapshot) |
| `/metrics` | Prometheus text metrics |
| `/playlist.m3u` | Subscribed non-DRM channels; stream URLs → `/watch/{stationId}`; absolute URLs from request host or `X-Forwarded-*` |
| `/epg.xml` | XMLTV; `channel id` = call sign; cached `EPG_CACHE_SECONDS`; programmes when schedule probe succeeds |
| `/watch/{id}` | Resolve live URL; reject DRM; **302** to HLS |
| `/health` | Liveness + version |
| `/docs` | FastAPI OpenAPI UI |

**Typical errors:** `502` Fubo/auth/DRM/missing URL; `503` service not initialized.

### M3U attributes (Emby and Jellyfin)

| Attribute | Meaning |
| --- | --- |
| `tvg-id` | Joins to XMLTV `channel id` (Fubo call sign) |
| `tvg-name` / display name | Channel label |
| `tvg-logo` | Artwork when present |
| `group-title` | Package / plan grouping |
| URL line | `http://<bridge>/watch/<stationId>` |

## Architecture (from `docs/ARCHITECTURE.md`)

```text
┌────────────────────┐   playlist.m3u / epg.xml   ┌──────────────────────────┐
│ Emby Live TV       │ ─────────────────────────► │ Fubo → Emby & Jellyfin   │
│ and/or             │ ◄───────────────────────── │ Bridge (FastAPI)         │
│ Jellyfin Live TV   │                            └────────────┬─────────────┘
└────────────────────┘                                         │
       │                                                       │
       │  GET /watch/{id}                                      │
       └───────────────────────────────────────────────────────┤
                         302 → HLS URL                         ▼
                                                        ┌─────────────┐
                                                        │ api.fubo.tv │
                                                        └─────────────┘
```

### Auth

1. Load or create `CONFIG_DIR/device.json` (`x-device-id`)
2. `PUT /signin` with email/password and Android TV-style client headers
3. Cache `access_token` ~4 hours in process memory
4. `Authorization: Bearer …` on subsequent calls

### Channel lineup

First successful populated list wins:

1. **Subscriptions** — `subscriptions`, `subscriptions/products`, plus `v3/plan-manager/plans` for source metadata
2. **Plan manager fallback** — `v3/plan-manager/plans` + `user` recurly `purchased_packages`

Known DRM sources/call signs are dropped before playlist generation.

### Tune

1. Emby or Jellyfin opens `/watch/{stationId}` from the M3U
2. Bridge calls `vapi/asset/v1?channelId=…&type=live`
3. `drmProtected` → HTTP 502; else **302** to HLS URL

### Guide

1. Load channels; probe authenticated schedule endpoints
2. Map listings to playlist `tvg-id` (= call sign)
3. Cache body for `EPG_CACHE_SECONDS`
4. If no schedule payload → XMLTV still has `<channel>` rows for mapping

### Caching

| Data | TTL | Storage |
| --- | --- | --- |
| Bearer token | ~4 hours | Process memory |
| Channel list | 30 minutes | Process memory |
| XMLTV body | `EPG_CACHE_SECONDS` (default 1h) | Process memory |
| Device id | Permanent until deleted | `CONFIG_DIR/device.json` |

## Product decisions (locked)

1. **Sidecar over plugin** — Emby and Jellyfin already support M3U + XMLTV.
2. **`tvg-id` = Fubo call sign** — must match XMLTV `channel id` for mapping.
3. **Watch URLs are local** (`/watch/{id}`), never raw CDN URLs in the M3U.
4. **Tune = 302 redirect** — requires Emby/Jellyfin and bridge to share public egress IP.
5. **Credentials** — `config/credentials.env` (or JSON) preferred for Portainer; else `FUBO_USER` / `FUBO_PASS`; device id in `CONFIG_DIR/device.json`.
6. **Channel discovery** — try subscriptions APIs first, fall back to plan-manager + user recurly packages.
7. **EPG best-effort** — probe bulk then sample per-network schedule endpoints; channel-only XMLTV if listings fail.
8. **Credit prior art** — see `CREDITS.md` (vlc-bridge-fubo lineage, deps).
9. **Context files** — durable facts here; mutable status in `WORKING_MEMORY.md`.
10. **Emby and Jellyfin are equal first-class targets** — one HTTP surface; quirks only in docs (`docs/MEDIA_SERVERS.md`).
11. **Short name `fbtv`** — GitHub repo, Compose service/image, GHCR package, and XMLTV `generator-info-name`; public visibility.

## Environment (from `docs/CONFIGURATION.md`)

| Variable | Default | Required |
| --- | --- | --- |
| `FUBO_USER` | — | yes |
| `FUBO_PASS` | — | yes |
| `HOST` | `0.0.0.0` | no |
| `PORT` | `7777` | no |
| `CONFIG_DIR` | `./config` | no |
| `EPG_CACHE_SECONDS` | `3600` | no |
| `EPG_DAYS` | `2` | no |

Process **refuses to start** if `FUBO_USER` or `FUBO_PASS` is missing.

Runtime files: `.env` (secrets, not committed), `config/device.json`, `config/.gitkeep`.

Reverse proxy: forward `X-Forwarded-Host` and `X-Forwarded-Proto` so playlist watch URLs use the public host.

Compose mounts `./config:/app/config` and pulls `ghcr.io/cbodden/fbtv:latest`. Credentials: `config/credentials.env` (file wins) or host env `FUBO_USER` / `FUBO_PASS`. Local Python may use `.env` with `interpolate=False`.

## Media server wiring summary

**Emby** (`docs/EMBY_SETUP.md`): Premiere required → M3U tuner + XMLTV → same egress. Sparse EPG: Emby Guide Data FuboTV lineup + manual map.

**Jellyfin** (`docs/JELLYFIN_SETUP.md`): Live TV included → same M3U + XMLTV URLs → same egress. Sparse EPG: Schedules Direct **or** other XMLTV (not both with bridge XMLTV); map under Live TV → Channels.

**Both:** Cap combined simultaneous streams to the Fubo plan (`docs/MEDIA_SERVERS.md`).

## Constraints & risks (from README + troubleshooting)

- Unofficial Fubo API; headers/endpoints can break without notice
- Stream URLs often IP-bound; Emby/Jellyfin must fetch redirected CDN URL from an accepted IP
- Personal use with subscriber’s own account only; respect ToS
- Never commit `.env` or live tokens
- Docker was not available in the original agent environment; image build unverified there
- Playlist generated via `localhost` will break a media server on another host — use LAN IP or forwarded headers
- Emby or Jellyfin in Docker reaching host bridge: use `host.docker.internal` or host LAN IP, not container `localhost`
- Delete `config/device.json` only as last resort for sign-in loops

## Planned (CHANGELOG Unreleased)

- Optional MPEG-TS remux / stream proxy for clients that do not share egress IP
- Richer EPG once stable schedule endpoints confirmed in the field
- Configurable DRM allow/deny lists

## Docs map

| Need | File |
| --- | --- |
| Quick start | `README.md` |
| Docs index | `docs/README.md` |
| Emby & Jellyfin | `docs/MEDIA_SERVERS.md` |
| Emby wiring | `docs/EMBY_SETUP.md` |
| Jellyfin wiring | `docs/JELLYFIN_SETUP.md` |
| Status / metrics | `docs/STATUS.md` |
| Env vars | `docs/CONFIGURATION.md` |
| HTTP API | `docs/API.md` |
| Design | `docs/ARCHITECTURE.md` |
| Failures | `docs/TROUBLESHOOTING.md` |
| Attribution | `CREDITS.md` |
| History | `CHANGELOG.md` |
| Security | `SECURITY.md` |
| Contributing | `CONTRIBUTING.md` |
| Session state | `WORKING_MEMORY.md` |

## Agent guidance

- Prefer reading this file + `WORKING_MEMORY.md` before large changes
- Keep secrets out of git and out of memory files
- When changing public behavior, update `CHANGELOG.md` and the matching `docs/` page
- When adopting another project’s approach or a new dependency, update `CREDITS.md`
- After doc edits that change durable facts, re-sync this file from `docs/`
- Treat Emby and Jellyfin as peer targets in user-facing copy (do not frame Jellyfin as an afterthought)
