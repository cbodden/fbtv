# Project context

Durable facts for humans and agents working on this repo. For ephemeral session state, see [WORKING_MEMORY.md](WORKING_MEMORY.md). Update this file when architecture or product decisions change.

## What this is

- **Name:** Fubo → Emby Bridge (`fubotv_emby`)
- **Workspace:** `/Users/cesarbodden/ai/fubotv_emby`
- **Version:** 1.0.0 (`app/__version__`)
- **Kind:** Python FastAPI **sidecar**, not an Emby .NET plugin
- **Purpose:** Authenticate with a personal Fubo account; serve Emby Live TV via:
  - `GET /playlist.m3u` → Emby M3U Tuner
  - `GET /epg.xml` → Emby XMLTV guide
  - `GET /watch/{id}` → 302 to live HLS
  - `GET /` → HTML index with copy-paste URLs
  - `GET /health` → `{"status":"ok","version":"…"}`

## Origin / session summary

Built from an empty workspace (2026-08-06) after the user chose:

1. Emby integration via **sidecar** (not a native .NET plugin)
2. **Python** as the language
3. Outputs Emby expects: **playlist.m3u** + **epg.xml**

Implementation patterns for Fubo auth/lineup/watch were informed by community vlc-bridge projects (see `CREDITS.md`).

## Non-goals (v1)

- Native Emby `ITunerHost` plugin
- DRM decryption / playback of Disney, Starz, Showtime, Max/HBO, etc.
- MPEG-TS remux via streamlink/ffmpeg
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
app/main.py                 # routes, lifespan
app/fubo_client.py          # auth, channels, watch, schedule probe
app/m3u.py                  # playlist builder
app/epg.py                  # XMLTV + TTL cache
app/config.py               # Settings
app/__init__.py             # __version__
docs/                       # full documentation
CREDITS.md                  # attribution (required when borrowing patterns)
CONTEXT.md                  # this file
WORKING_MEMORY.md           # session / next actions
.cursor/rules/project-context.mdc
tests/test_builders.py
Dockerfile
docker-compose.yml
.env.example
```

## HTTP surface

| Path | Behavior |
| --- | --- |
| `/playlist.m3u` | Subscribed non-DRM channels; stream URLs → `/watch/{stationId}` |
| `/epg.xml` | XMLTV; `channel id` = call sign; cached `EPG_CACHE_SECONDS` |
| `/watch/{id}` | Resolve live URL; reject DRM; **302** to HLS |
| `/health` | Liveness + version |
| `/docs` | FastAPI OpenAPI UI |

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

## Environment

| Variable | Default | Required |
| --- | --- | --- |
| `FUBO_USER` | — | yes |
| `FUBO_PASS` | — | yes |
| `HOST` | `0.0.0.0` | no |
| `PORT` | `7777` | no |
| `CONFIG_DIR` | `./config` | no |
| `EPG_CACHE_SECONDS` | `3600` | no |
| `EPG_DAYS` | `2` | no |

## Constraints & risks

- Unofficial Fubo API; headers/endpoints can break without notice
- Stream URLs often IP-bound
- Personal use with subscriber’s own account only; respect ToS
- Never commit `.env` or live tokens
- Docker was not available in the original agent environment; image build unverified there

## Docs map

| Need | File |
| --- | --- |
| Quick start | `README.md` |
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
