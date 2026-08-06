# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-08-06 ~16:02 local (pause / continue-later save)  
**Active version:** 1.0.0  
**Phase:** **Paused.** v1 code + docs complete on local `main`; next session = live smoke test with Fubo credentials + Emby  
**Git:** local `main`, working tree clean before this pause-note commit; Co-authored-by trailers already stripped from history; no remote configured

---

## Resume here (next session)

1. Read [CONTEXT.md](CONTEXT.md) then this file
2. `cp .env.example .env` and set real `FUBO_USER` / `FUBO_PASS` (do not commit `.env`)
3. Start bridge:
   - `docker compose up -d --build` **or**
   - `source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 7777`
4. Verify: `curl` `/health`, `/playlist.m3u`, `/epg.xml`
5. Wire Emby M3U + XMLTV per `docs/EMBY_SETUP.md`
6. Fill **Field notes** below; update this file with results

## Current focus

- Hand off a clean pause point — no unfinished code edits
- First unfinished product work: real-account validation and Emby playback

## Snapshot — what exists on disk

Path: `/Users/cesarbodden/ai/fubotv_emby`

| Area | Contents |
| --- | --- |
| App | `app/{main,fubo_client,m3u,epg,config,__init__}.py` |
| Ops | `Dockerfile`, `docker-compose.yml`, `.env.example`, `.gitignore`, `requirements.txt` |
| Docs | `README`, `CHANGELOG`, `CONTRIBUTING`, `SECURITY`, `CREDITS`, `docs/*` |
| Agent | `CONTEXT.md`, `WORKING_MEMORY.md`, `.cursor/rules/project-context.mdc` |
| Tests | `tests/test_builders.py` (passed earlier) |
| Local only | `.venv/` (gitignored); no `.env` with secrets expected in git |

## Done so far

- [x] Architecture: Python FastAPI sidecar (not Emby .NET plugin)
- [x] Routes: `/`, `/playlist.m3u`, `/epg.xml`, `/watch/{id}`, `/health` (+ OpenAPI `/docs`)
- [x] Fubo client: device id, token cache, subscriptions + plan-manager fallback, DRM skip, watch, EPG probe
- [x] M3U + XMLTV builders; EPG TTL cache
- [x] Docker / compose scaffolding
- [x] Full docs + CREDITS + CONTEXT/WORKING_MEMORY + Cursor rule
- [x] Builder unit tests
- [x] Git init + commits on `main` (no Co-authored-by trailers)
- [x] Pause save for continue-later

## Open questions / blockers

| Item | Status | Notes |
| --- | --- | --- |
| Live Fubo sign-in | Not run | Needs `.env` |
| Usable EPG endpoint | Unknown | Probe logic present; may be channel-only XMLTV |
| Emby ↔ bridge topology | Unknown | HLS 302 needs shared public egress IP |
| Docker build | Unverified in original agent env | `docker` was missing there |
| Remote / push | None | Local-only repo |

## Field notes (fill in during smoke test)

```text
Date:
Bridge URL:
Emby host / same egress?:
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
| 2026-08-06 | Strip Co-authored-by from commits | User request |
| 2026-08-06 | Pause with memory update | Continue later |

## Do not forget

- Do not commit secrets
- Update `CREDITS.md` if borrowing more bridge patterns
- Planned later (`CHANGELOG` Unreleased): MPEG-TS remux, richer EPG, configurable DRM lists
- Prefer updating this file over leaving status only in chat

## Scratch

_Paused for later. Next agent/human: start at **Resume here**._
