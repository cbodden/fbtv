# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-11-10 (v1.0.11 on `main`; `dev` Compose `:dev`)  
**Active version:** 1.0.11  
**Phase:** Post-1.0.11  
**Git:** `dev` (Compose `:dev`); `main` / `:latest` = 1.0.11

---

## Resume here (this session)

**1.0.10** shipped (PR #4 client hardening, PR #5 release). Tag `v1.0.10` + GitHub release published.

### Next actions
1. Get from the deployed host: `docker inspect fbtv --format 'oom={{.State.OOMKilled}} restarts={{.RestartCount}} memlimit={{.HostConfig.Memory}}'` and `/status.json` auth + `epg.programme_count` to confirm OOM vs sign-in as the field cause
2. Pull `:latest` (1.0.11) on the host, request `/epg.xml`, re-check `epg.programme_count`

---

## Field notes (2026-11-10, browser + live probe)

- Parser is **not** the bug: live `/epg` and `papi/v1/guide/epg` responses match fbtv's parsers; station ids join the lineup (e.g. `16689` = WCBS)
- Both guide endpoints answer **anonymously** with fbtv's android_tv headers; without device headers `papi` returns 528 `cannot MatchDevicePageManagerWithDeviceAgent`
- Fubo web guide uses `papi/v1/guide/epg` in 5h windows
- Live `schedule()` (sign-in stubbed): one 49h `/epg` call = ~80 MB JSON, **645 MB** peak RSS; 6h chunks = **245 MB**, same 3,963 programmes on 83/85 channels
- Local `session.json` last sign-in: `401 INVALID_USERNAME_PASSWORD` (Sep 17)

---

## Backlog

- **DRM sweep:** 2026-08-13 local scan learned 296 DRM vs 85 playable (incl. BTN, CBSSN, BET). Test whether `x-drm-scheme: widevine` makes Fubo serve DRM variants; learned ids are only re-checked with `force=true`
- `token()` holds the shared lock during network sign-in (status/metrics can stall up to 30s)

---

## Current focus

- Empty guide: chunked `/epg` to fix memory; confirm field cause (OOM vs sign-in).

## Scratch

_Public imports stay `from app.fubo_client import …`._
_Guide join = tvg-id call sign only._
_Compose: `main` → `:latest`, `dev` → `:dev`._
_Do not log or commit secrets / raw passwords / bearer tokens / session.json._
