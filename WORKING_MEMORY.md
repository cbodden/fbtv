# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-08-06 (saved full session snapshot)  
**Active version:** 1.0.0  
**Phase:** v1 implementation + docs complete; git initial commit saved  
**Git:** `main` @ `1553836` — *Initial Fubo→Emby Python bridge with docs and agent context.*

---

## Current focus

- Persist all work (context + code + docs) so nothing lives only in chat
- Next real work: user supplies Fubo credentials and validates against Emby

## Snapshot — what exists on disk

Complete sidecar project under `/Users/cesarbodden/ai/fubotv_emby`:

- App: `app/{main,fubo_client,m3u,epg,config}.py`
- Ops: `Dockerfile`, `docker-compose.yml`, `.env.example`, `.gitignore`, `requirements.txt`
- Docs: `README`, `CHANGELOG`, `CONTRIBUTING`, `SECURITY`, `CREDITS`, `docs/*`
- Agent: `CONTEXT.md`, `WORKING_MEMORY.md`, `.cursor/rules/project-context.mdc`
- Tests: `tests/test_builders.py` (passed locally)
- Local `.venv` present (not for commit)

## Done this session

- [x] Chose architecture: Python sidecar (not Emby .NET plugin)
- [x] FastAPI routes: `/`, `/playlist.m3u`, `/epg.xml`, `/watch/{id}`, `/health`
- [x] Fubo client: device id, sign-in/token cache, subscriptions + plan-manager channels, DRM skip, watch, EPG probe
- [x] M3U + XMLTV builders; EPG TTL cache
- [x] Docker / compose scaffolding
- [x] Full documentation suite
- [x] `CREDITS.md` (vlc-bridge prior art + deps)
- [x] Context + working memory + Cursor rule
- [x] Builder unit tests (`PYTHONPATH=. python tests/test_builders.py` → ok)
- [x] Saved durable context + this memory snapshot

## Open questions / blockers

| Item | Status | Notes |
| --- | --- | --- |
| Live Fubo sign-in | Not run | Needs `.env` with real credentials |
| Usable EPG endpoint in production | Unknown | Probe logic in place; may be channel-only |
| Emby ↔ bridge network topology | Unknown | 302 model needs shared egress IP |
| Docker image build | Unverified in agent env | `docker` was missing there |

## Next actions (suggested)

1. ~~Ensure git repo initialized and this tree committed~~ → done (`1553836`)
2. `cp .env.example .env` → set `FUBO_USER` / `FUBO_PASS`
3. `docker compose up -d --build` **or** `uvicorn app.main:app --host 0.0.0.0 --port 7777`
4. `curl` `/health`, `/playlist.m3u`, `/epg.xml`
5. Wire Emby per `docs/EMBY_SETUP.md`
6. Record field notes below (channel count, EPG path, playback)

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

## Decisions log (session)

| When | Decision | Why |
| --- | --- | --- |
| 2026-08-06 | Sidecar + Python, not Emby .NET plugin | User chose #1 + Python; matches M3U/EPG ask |
| 2026-08-06 | HLS 302 only in v1 | Avoid streamlink/ffmpeg complexity |
| 2026-08-06 | Call sign as tvg-id | Emby XMLTV auto-map |
| 2026-08-06 | Full docs + CREDITS + CONTEXT/WORKING_MEMORY | Attribution, operability, agent continuity |
| 2026-08-06 | Save all work to disk + git | User requested persist everything |

## Do not forget

- Update `CREDITS.md` if patterns are copied from other bridges
- Do not commit secrets (`.env`, tokens)
- Prefer editing `WORKING_MEMORY.md` over scattering status only in chat
- Planned later (changelog Unreleased): MPEG-TS remux, richer EPG, configurable DRM lists

## Scratch

_Session closed for “save all work” — clear/replace when next coding session starts._

- Chat built empty repo → full v1 bridge + docs
- No live Fubo validation yet
