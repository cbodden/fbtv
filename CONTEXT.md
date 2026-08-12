# Project context

Durable facts for humans and agents working on this repo. For ephemeral session state, see [WORKING_MEMORY.md](WORKING_MEMORY.md). Update this file when architecture or product decisions change.

**Synced from:** `docs/` + root docs on 2026-08-12 (1.0.6 released on `main`).

## What this is

- **Name:** Fubo → Emby & Jellyfin Bridge — short name **`fbtv`**
- **GitHub:** https://github.com/cbodden/fbtv (public)
- **Docker:** Compose service/container `fbtv` pulls `ghcr.io/cbodden/fbtv:latest` by default (`pull_policy: always`); use `ghcr.io/cbodden/fbtv:dev` for pre-release. No Compose `env_file`. Credentials: `config/credentials.env` (`FUBO_PASS_B64` preferred) or `credentials.json` (file wins); else host env. CI publishes GHCR from **`main`** (`:latest`) and **`dev`** (`:dev`) — `.github/workflows/docker.yml`.
- **Workspace:** `/home/cbodden/git/mine/fbtv` (also historically `/home/cbodden/git/mine/fubo_emby`)
- **Historical names:** `fubo_emby`, `fubo-emby`, `fubotv_emby`, `fubotv-emby` (docs only)
- **Version:** 1.0.6 (`app/__version__`; see `CHANGELOG.md`)
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

Built from an empty workspace (2026-08-06) after the user chose sidecar + Python + M3U/XMLTV. Patterns informed by community vlc-bridge projects (`CREDITS.md`).

**2026-08-11:** Emby and Jellyfin equal first-class; metrics; GHCR; repo renamed `fbtv`.

**Status:** **v1.0.6** on `main` / GHCR `:latest` (EPG `/epg` parser, DRM background scan with 429 pacing). Pre-release continues on `dev` → `:dev`.

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
| Config | python-dotenv (`interpolate=False`); credentials file / `FUBO_PASS_B64` / env |
| Deploy | Docker Compose pulls GHCR; CI builds `:latest` from `main`, `:dev` from `dev` |

## Key paths

```text
app/main.py                 # routes, lifespan, base URL detection
app/fubo_client.py          # auth, channels, watch, schedule (/epg + papi)
app/m3u.py / epg.py / status.py / config.py / set_credentials.py
docs/                       # full documentation
docs/EMBY_SETUP.md          # Guide Data FuboTV recommended while bridge EPG empty
.github/workflows/docker.yml   # GHCR on main + dev
```

## Guide (from docs)

1. Prefer `/epg` → parse `channelWithProgramAssets` (field-confirmed 200)
2. Fall back to chunked `papi/v1/guide/epg`, then older sample paths
3. Map to `tvg-id` (= call sign); cache `EPG_CACHE_SECONDS`
4. Empty programmes → channel-only XMLTV; Emby: Guide Data FuboTV

## Product decisions (locked)

1. Sidecar over plugin
2. `tvg-id` = Fubo call sign
3. Watch URLs local (`/watch/{id}`); tune = 302 (shared egress)
4. Credentials file wins; `FUBO_PASS_B64` for `$`/`!`
5. Emby and Jellyfin equal first-class targets
6. Short name `fbtv`; GHCR `:latest` from `main`, `:dev` from `dev`
7. EPG best-effort; Emby Guide Data as operator workaround when empty
8. Credit prior art in `CREDITS.md`

## Planned

- Optional MPEG-TS remux / stream proxy
- Configurable DRM allow/deny lists (manual overrides on top of scan)

## Agent guidance

- Prefer this file + `WORKING_MEMORY.md` before large changes
- Keep secrets out of git and memory files
- When public behavior changes, update `CHANGELOG.md` and matching `docs/`
- Treat Emby and Jellyfin as peers in user-facing copy
