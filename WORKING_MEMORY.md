# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-11-10 (v1.0.13 on `main`; `dev` Compose `:dev`)  
**Active version:** 1.0.13  
**Phase:** Post-1.0.13  
**Git:** `dev` (Compose `:dev`); `main` / `:latest` = 1.0.13

---

## Resume here (this session)

**1.0.13** shipped (PR #10 DRM re-checks, PR #11 release; tag `v1.0.13` + GitHub release). 1.0.12 = overlap-free guide (PR #8/#9). 1.0.11 = chunked `/epg` (PR #6/#7); 1.0.10 = session persist + client hardening (PR #4/#5).

### Next actions
1. Get from the deployed host: `docker inspect fbtv --format 'oom={{.State.OOMKilled}} restarts={{.RestartCount}} memlimit={{.HostConfig.Memory}}'` and `/status.json` auth + `epg.programme_count` to confirm OOM vs sign-in as the field cause
2. Pull `:latest` (1.0.13) on the host, request `/epg.xml`, re-check `epg.programme_count` and AMTEVE / FUBOCRM in the guide; after the first sweep (~5 min) confirm `rechecked_drm` > 0 and BTN back in the M3U

---

## Field notes (2026-11-10, browser + live probe)

- Parser is **not** the bug: live `/epg` and `papi/v1/guide/epg` responses match fbtv's parsers; station ids join the lineup (e.g. `16689` = WCBS)
- Both guide endpoints answer **anonymously** with fbtv's android_tv headers; without device headers `papi` returns 528 `cannot MatchDevicePageManagerWithDeviceAgent`
- Fubo web guide uses `papi/v1/guide/epg` in 5h windows
- Live `schedule()` (sign-in stubbed): one 49h `/epg` call = ~80 MB JSON, **645 MB** peak RSS; 6h chunks = **245 MB**, same 3,963 programmes on 83/85 channels
- Local `session.json` last sign-in: `401 INVALID_USERNAME_PASSWORD` (Sep 17)
- Local test of 1.0.13 (2026-11-10, venv, sign-in stubbed, 85 playable stations): all endpoints 200; valid XMLTV 3,787 programmes on 83/85 channels (MBLC, NFLNRZD empty upstream), 0 overlaps, tvg-id ↔ XMLTV ids match. Fubo Radio FM001–FM010 carry one week-long listing (upstream, fine). Docker Desktop was not running, so the image itself wasn't run locally. Not covered without sign-in: lineup API, `GET /watch`, DRM re-check
- DRM header test (8 stations, user's web session): without `x-drm-scheme: widevine`, DRM channels → HTTP 400 (no clear fallback); clear channels unchanged. DRM status drifts: BTN learned DRM 2026-08-13 is clear now, BTN2 went DRM. Fix: scheduled sweeps re-check stale learned DRM (`fix/drm-recheck`)

---

## Backlog

- `token()` holds the shared lock during network sign-in (status/metrics can stall up to 30s)

---

## Current focus

- Empty guide: chunked `/epg` to fix memory; confirm field cause (OOM vs sign-in).

## Scratch

_Public imports stay `from app.fubo_client import …`._
_Guide join = tvg-id call sign only._
_Compose: `main` → `:latest`, `dev` → `:dev`._
_Do not log or commit secrets / raw passwords / bearer tokens / session.json._
