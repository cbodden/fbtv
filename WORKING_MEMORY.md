# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-08-11 ~22:50 local (docs synced on `dev` for 1.0.2 credentials)  
**Active version:** 1.0.2  
**Phase:** Docs on `dev` match B64/file credentials; GHCR `:latest` still from `main` until merge  
**Git:** `dev` → `origin/dev` (`git@github.com:cbodden/fbtv.git`); `main` is older

---

## Resume here (this session)

1. Read [CONTEXT.md](CONTEXT.md) then this file
2. Credentials: `config/credentials.env` with `FUBO_PASS_B64` (or `python -m app.set_credentials`). Alphanumeric `FUBO_PASS` works in Portainer today.
3. Start: `docker compose up -d` pulls **`main`’s** GHCR image unless you build locally from `dev`
4. Verify: `/health` (expect 1.0.2 only after `dev` is in the image), `/status.json`, playlist, epg
5. Wire Emby / Jellyfin per `docs/MEDIA_SERVERS.md`
6. Retry `$` password once via `FUBO_PASS_B64` after 1.0.2 is running

## Current focus

- Documentation aligned to 1.0.2 credential model on branch `dev`
- Confirm `$` password via `FUBO_PASS_B64` after image includes this branch
- Emby/Jellyfin wiring still pending

## Snapshot — what exists on disk

Path: `/home/cbodden/git/mine/fubo_emby` (local folder; GitHub is `cbodden/fbtv`)

| Area | Contents |
| --- | --- |
| App | `app/{main,fubo_client,m3u,epg,status,config,set_credentials,__init__}.py` |
| Ops | `Dockerfile`, `docker-compose.yml` (GHCR pull), `.env.example`, `credentials.env.example` |
| CI | `.github/workflows/docker.yml` → GHCR on **`main` only** |
| Docs | README + `docs/` + SECURITY/CONTRIBUTING/CREDITS/CHANGELOG |
| Agent | `CONTEXT.md`, `WORKING_MEMORY.md`, `.cursor/rules/project-context.mdc` |
| Tests | `tests/test_builders.py` |
| Local only | `.venv/`; secrets in volume `config/credentials.*` or env |

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
- [x] GitHub Actions Docker build → GHCR (2026-08-11)
- [x] Repo renamed to `fbtv` + public; Compose/GHCR image `fbtv` (2026-08-11)
- [x] Docs tree synced for fbtv naming / public / GHCR (2026-08-11)
- [x] Live Fubo sign-in (alphanumeric password, Portainer) (2026-08-11)
- [x] FUBO_PASS_B64 + set_credentials on `dev` (2026-08-11)
- [x] Docs resynced on `dev` for 1.0.2 credentials (2026-08-11)

## Open questions / blockers

| Item | Status | Notes |
| --- | --- | --- |
| Live Fubo sign-in | OK without `$` | Portainer + credentials file; `$` still needs B64 (1.0.2 image) |
| Usable EPG endpoint | Unknown | Probe logic present; may be channel-only XMLTV (`docs/TROUBLESHOOTING.md`) |
| Emby/Jellyfin ↔ bridge topology | Unknown | HLS 302 needs shared public egress IP |
| Docker build | Unverified in original agent env | `docker` was missing there |
| Jellyfin field validation | Not run | Docs added; playback untested |

## Field notes (fill in during smoke test)

```text
Date: 2026-08-11
Bridge URL: Portainer / Docker (fbtv)
Media server(s): not wired yet
Same egress?:
Channel count in playlist:
EPG programmes present?:
Working EPG endpoint (from logs):
Playback result (sample channels):
DRM skips observed:
Issues: Sign-in 401 until password had no `$`. File load worked (pass_len=14, has_dollar=True) but Fubo rejected; alphanumeric password succeeded. B64 path not field-tested yet.
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
| 2026-08-11 | GH Actions build/push to GHCR on Dockerfile context changes | User: auto-build image when Dockerfile pushed |
| 2026-08-11 | GitHub repo renamed `fubo_emby` → `fbtv`, visibility public | User request |
| 2026-08-11 | Compose + GHCR image name `fbtv` (not `fubo-emby`) | User request |
| 2026-08-11 | Full docs sync for fbtv / public / GHCR | User: update all documentation |
| 2026-08-11 | Compose pulls GHCR; no env_file — host env for secrets | User request |
| 2026-08-11 | Portainer auth troubleshooting (`$` mangling) | User: 401 in Portainer |
| 2026-08-11 | credentials.env/json file wins over env; strip wrapping quotes | User: quotes/$$ still 401 in Portainer |
| 2026-08-11 | Bump Fubo client headers to 5.40.0 | User: 401 persists with correct email + pass_len=14 / `$` |
| 2026-08-11 | FUBO_PASS_B64 + set_credentials for `$` passwords | User: works without `$`, wants secure passwords |
| 2026-08-11 | Resync all docs on `dev` for 1.0.2 credential model | User: update all documentation on dev |

## Do not forget

- Do not commit secrets
- Update `CREDITS.md` if borrowing more bridge patterns
- Planned later (`CHANGELOG` Unreleased): MPEG-TS remux, richer EPG, configurable DRM lists
- Prefer updating this file over leaving status only in chat
- When public behavior changes, update matching `docs/` page and re-sync `CONTEXT.md`

## Scratch

_Scratch: Docs on `dev` describe FUBO_PASS_B64 / set_credentials / GHCR-from-main. Alphanumeric Fubo sign-in works. Merge `dev` → `main` before `:latest` includes 1.0.2._
