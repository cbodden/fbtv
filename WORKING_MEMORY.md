# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-08-11 ~15:50 local (status/metrics docs synced across tree)  
**Active version:** 1.0.0  
**Phase:** Metrics implemented + docs synced (`docs/STATUS.md`); next = continue smoke test / Emby-Jellyfin wiring  
**Git:** `main` (may be ahead of `origin/main`)

---

## Resume here (this session)

1. Read [CONTEXT.md](CONTEXT.md) then this file
2. `cp .env.example .env` and set real `FUBO_USER` / `FUBO_PASS` (do not commit `.env`; quote passwords with symbols in single quotes)
3. Start bridge:
   - `docker compose up -d --build` **or**
   - `source .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port 7777`
4. Verify per `docs/TROUBLESHOOTING.md` / `docs/STATUS.md`:
   - `curl -sS http://127.0.0.1:7777/health`
   - `curl -sS http://127.0.0.1:7777/status.json`
   - `curl -sS http://127.0.0.1:7777/playlist.m3u | head`
   - `curl -sS http://127.0.0.1:7777/epg.xml | head`
5. Wire M3U + XMLTV:
   - Emby → `docs/EMBY_SETUP.md`
   - Jellyfin → `docs/JELLYFIN_SETUP.md`
   - Both → `docs/MEDIA_SERVERS.md` (same egress; combined stream caps)
6. Fill **Field notes** below; update this file with results

## Current focus

- Emby and Jellyfin documented as equal first-class targets (shared HTTP surface; no API fork)
- Added HTML/JSON/Prometheus runtime metrics endpoints
- Field validation / Emby-Jellyfin wiring still in progress

## Snapshot — what exists on disk

Path: `/Users/cesarbodden/git/work/fubo_emby`

| Area | Contents |
| --- | --- |
| App | `app/{main,fubo_client,m3u,epg,config,__init__}.py` |
| Ops | `Dockerfile`, `docker-compose.yml`, `.env.example`, `.gitignore`, `requirements.txt` |
| Docs | `README`, `CHANGELOG`, `CONTRIBUTING`, `SECURITY`, `CREDITS`, `docs/{README,API,ARCHITECTURE,CONFIGURATION,MEDIA_SERVERS,EMBY_SETUP,JELLYFIN_SETUP,STATUS,TROUBLESHOOTING}` |
| Agent | `CONTEXT.md`, `WORKING_MEMORY.md`, `.cursor/rules/project-context.mdc` |
| Tests | `tests/test_builders.py` |
| Local only | `.venv/` (gitignored); secrets must stay in `.env` only |

## Done so far

- [x] Architecture: Python FastAPI sidecar (not Emby/Jellyfin native plugin)
- [x] Routes: `/`, `/playlist.m3u`, `/epg.xml`, `/watch/{id}`, `/health`, `/status`, `/status.json`, `/metrics` (+ OpenAPI `/docs`)
- [x] Fubo client: device id, token cache, subscriptions + plan-manager fallback, DRM skip, watch, EPG probe
- [x] M3U + XMLTV builders; EPG TTL cache
- [x] Docker / compose scaffolding
- [x] Full docs + CREDITS + CONTEXT/WORKING_MEMORY + Cursor rule
- [x] Builder unit tests
- [x] Git init + commits on `main`
- [x] Pause save (2026-08-06)
- [x] CONTEXT re-sync from `docs/` (2026-08-11)
- [x] Expand README into detailed user guide (2026-08-11)
- [x] Jellyfin setup + MEDIA_SERVERS + dual branding (2026-08-11)
- [x] Recreated `.venv` for this checkout path (was stale from `ai/fubotv_emby`)
- [x] Rebalanced README + all docs for equal Emby & Jellyfin framing (2026-08-11)
- [x] Runtime metrics: `/` snapshot, `/status`, `/status.json`, `/metrics` (2026-08-11)
- [x] Docs synced for metrics across README + `docs/` + SECURITY/CONTRIBUTING/CONTEXT (2026-08-11)

## Open questions / blockers

| Item | Status | Notes |
| --- | --- | --- |
| Live Fubo sign-in | Not run | Needs `.env` — see `docs/CONFIGURATION.md` |
| Usable EPG endpoint | Unknown | Probe logic present; may be channel-only XMLTV (`docs/TROUBLESHOOTING.md`) |
| Emby/Jellyfin ↔ bridge topology | Unknown | HLS 302 needs shared public egress IP |
| Docker build | Unverified in original agent env | `docker` was missing there |
| Jellyfin field validation | Not run | Docs added; playback untested |

## Field notes (fill in during smoke test)

```text
Date:
Bridge URL:
Media server(s): Emby / Jellyfin / both
Same egress?:
Channel count in playlist:
EPG programmes present?:
Working EPG endpoint (from logs):
Playback result (sample channels):
DRM skips observed:
Issues:
```

## Decisions log

| When | Decision | Why |
| --- | --- | --- |
| 2026-08-06 | Sidecar + Python, not Emby .NET plugin | User chose #1 + Python |
| 2026-08-06 | HLS 302 only in v1 | Avoid streamlink/ffmpeg for now |
| 2026-08-06 | Call sign as tvg-id | Emby XMLTV auto-map |
| 2026-08-06 | Docs + CREDITS + context/memory | Attribution + continuity |
| 2026-08-06 | Pause with memory update | Continue later |
| 2026-08-11 | Re-sync CONTEXT from `docs/` | User: update from docs folder |
| 2026-08-11 | Document Jellyfin + dual-server use | User: add Emby && Jellyfin specific bits; same HTTP surface |
| 2026-08-11 | Rebalance all docs for equal Emby/Jellyfin framing | User: README still Emby-heavy |
| 2026-08-11 | Add `/`, `/status`, `/status.json`, `/metrics` | User: show metrics three ways |
| 2026-08-11 | Sync all docs for metrics | User: update documentation for metrics additions |

## Do not forget

- Do not commit secrets
- Update `CREDITS.md` if borrowing more bridge patterns
- Planned later (`CHANGELOG` Unreleased): MPEG-TS remux, richer EPG, configurable DRM lists
- Prefer updating this file over leaving status only in chat
- When public behavior changes, update matching `docs/` page and re-sync `CONTEXT.md`

## Scratch

_Emby and Jellyfin are peer consumers of the M3U/XMLTV API. Docs rebalanced 2026-08-11. Ready for smoke test._
