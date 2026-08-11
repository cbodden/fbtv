# Project context

Durable facts for humans and agents working on this repo. For ephemeral session state, see [WORKING_MEMORY.md](WORKING_MEMORY.md). Update this file when architecture or product decisions change.

**Synced from:** `docs/` + root docs (`README`, `CHANGELOG`, `CREDITS`, `SECURITY`, `CONTRIBUTING`) on 2026-08-11.

## What this is

- **Name:** Fubo → Emby Bridge (`fubotv_emby` / `fubotv-emby`)
- **Workspace:** `/Users/cesarbodden/ai/fubotv_emby`
- **Version:** 1.0.0 (`app/__version__`; see `CHANGELOG.md`)
- **Kind:** Python FastAPI **sidecar**, not an Emby .NET plugin
- **Purpose:** Authenticate with a personal Fubo account; serve Emby Live TV via:
  - `GET /playlist.m3u` → Emby M3U Tuner
  - `GET /epg.xml` → Emby XMLTV guide
  - `GET /watch/{id}` → 302 to live HLS
  - `GET /` → HTML index with copy-paste URLs
  - `GET /health` → `{"status":"ok","version":"…"}` (liveness only; does not verify Fubo credentials)
  - `GET /docs` / `/openapi.json` → FastAPI OpenAPI UI

Emby Premiere is required for Live TV on the Emby side.

## Origin / session summary

Built from an empty workspace (2026-08-06) after the user chose:

1. Emby integration via **sidecar** (not a native .NET plugin)
2. **Python** as the language
3. Outputs Emby expects: **playlist.m3u** + **epg.xml**

Implementation patterns for Fubo auth/lineup/watch were informed by community vlc-bridge projects (see `CREDITS.md`).

**Status:** v1 implementation and documentation complete on local git `main`. Live Fubo/Emby smoke test not yet run. No git remote. Commit messages must not include Co-authored-by trailers (user preference).

## Non-goals (v1)

- Native Emby `ITunerHost` plugin
- DRM decryption / playback of Disney, Starz, Showtime, Max/HBO, etc.
- MPEG-TS remux via streamlink/ffmpeg (planned under Unreleased)
- Public redistribution of streams or credentials
- Gracenote / Schedules Direct as a first-class guide path (Emby Guide Data Fubo lineup can be used separately)

## Stack

| Layer | Choice |
| --- | --- |
| Language | Python 3.11+ (dev venv used 3.14 locally) |
| HTTP | FastAPI + Uvicorn |
| Fubo HTTP | httpx |
| Config | python-dotenv / env vars |
| Deploy | Docker + docker-compose |

## Key paths

```text
app/main.py                 # routes, lifespan, base URL detection
app/fubo_client.py          # auth, channels, watch, schedule probe
app/m3u.py                  # playlist builder
app/epg.py                  # XMLTV + TTL cache
app/config.py               # Settings
app/__init__.py             # __version__
docs/                       # full documentation (source for this file)
CREDITS.md                  # attribution (required when borrowing patterns)
CONTEXT.md                  # this file
WORKING_MEMORY.md           # session / next actions
.cursor/rules/project-context.mdc
tests/test_builders.py
Dockerfile
docker-compose.yml
.env.example
```

## HTTP surface (from `docs/API.md`)

| Path | Behavior |
| --- | --- |
| `/` | HTML index; copy-paste playlist/EPG URLs |
| `/playlist.m3u` | Subscribed non-DRM channels; stream URLs → `/watch/{stationId}`; absolute URLs from request host or `X-Forwarded-*` |
| `/epg.xml` | XMLTV; `channel id` = call sign; cached `EPG_CACHE_SECONDS`; programmes when schedule probe succeeds |
| `/watch/{id}` | Resolve live URL; reject DRM; **302** to HLS |
| `/health` | Liveness + version |
| `/docs` | FastAPI OpenAPI UI |

**Typical errors:** `502` Fubo/auth/DRM/missing URL; `503` service not initialized.

### M3U attributes Emby uses (`docs/EMBY_SETUP.md`)

| Attribute | Meaning |
| --- | --- |
| `tvg-id` | Joins to XMLTV `channel id` (Fubo call sign) |
| `tvg-name` / display name | Channel label |
| `tvg-logo` | Artwork when present |
| `group-title` | Package / plan grouping (Emby tags) |
| URL line | `http://<bridge>/watch/<stationId>` |

## Architecture (from `docs/ARCHITECTURE.md`)

```text
┌─────────────┐     playlist.m3u / epg.xml     ┌──────────────────┐
│ Emby Server │ ─────────────────────────────► │ Fubo Emby Bridge │
│  Live TV    │ ◄───────────────────────────── │   (FastAPI)      │
└─────────────┘     M3U rows + XMLTV           └────────┬─────────┘
       │                                                │
       │  GET /watch/{id}                               │ sign-in, lineup,
       └────────────────────────────────────────────────┤ schedule, stream
                         302 → HLS URL                  ▼
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

1. Emby opens `/watch/{stationId}` from the M3U
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

1. **Sidecar over plugin** — Emby already supports M3U + XMLTV.
2. **`tvg-id` = Fubo call sign** — must match XMLTV `channel id` for mapping.
3. **Watch URLs are local** (`/watch/{id}`), never raw CDN URLs in the M3U.
4. **Tune = 302 redirect** — requires Emby and bridge to share public egress IP.
5. **Credentials via env** — `FUBO_USER` / `FUBO_PASS`; device id in `CONFIG_DIR/device.json`.
6. **Channel discovery** — try subscriptions APIs first, fall back to plan-manager + user recurly packages.
7. **EPG best-effort** — probe bulk then sample per-network schedule endpoints; channel-only XMLTV if listings fail.
8. **Credit prior art** — see `CREDITS.md` (vlc-bridge-fubo lineage, deps).
9. **Context files** — durable facts here; mutable status in `WORKING_MEMORY.md`.

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

Compose mounts `./config:/app/config` and loads credentials from `.env`.

## Emby wiring summary (from `docs/EMBY_SETUP.md`)

1. **Dashboard → Live TV → Tuner Devices → +** → **M3U Tuner** → `http://<bridge>:7777/playlist.m3u`
2. **TV Guide Data Providers → +** → **XMLTV** → `http://<bridge>:7777/epg.xml`
3. Prefer same host / same public egress for Emby and bridge
4. Sparse EPG: keep bridge XMLTV for identity, and/or add Emby Guide Data FuboTV lineup and map manually
5. Remote Emby over Tailscale/VPN with bridge elsewhere often breaks HLS redirects (IP minting)

## Constraints & risks (from README + troubleshooting)

- Unofficial Fubo API; headers/endpoints can break without notice
- Stream URLs often IP-bound; Emby must fetch redirected CDN URL from an accepted IP
- Personal use with subscriber’s own account only; respect ToS
- Never commit `.env` or live tokens
- Docker was not available in the original agent environment; image build unverified there
- Playlist generated via `localhost` will break Emby on another host — use LAN IP or forwarded headers
- Emby-in-Docker reaching host bridge: use `host.docker.internal` or host LAN IP, not container `localhost`
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
| Emby wiring | `docs/EMBY_SETUP.md` |
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
