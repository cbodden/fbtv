# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-11-10 (v1.0.10 on `main`; `dev` Compose `:dev`)  
**Active version:** 1.0.10  
**Phase:** Post-1.0.10  
**Git:** `dev` (Compose `:dev`); `main` / `:latest` = 1.0.10

---

## Resume here (this session)

**1.0.10** shipped (PR #4 client hardening, PR #5 release). Tag `v1.0.10` / GitHub release not created yet.

### Next actions
1. Tag `v1.0.10` on the merge commit and publish the GitHub release (pending owner OK)
2. Pull `:latest`; confirm `/health` = 1.0.10 and `/status.json` `session_persisted: true` after a clean sign-in

---

## Backlog

- **Empty guide:** the `/epg` parser was never validated against a real response (the vlc-bridge references don't fetch a Fubo EPG; they map Gracenote ids). Need field logs (`docker logs fbtv 2>&1 | grep -E "EPG|Loaded .* programmes"`) or a redacted raw `/epg` payload; `/epg` is requested as one ~49h window
- **DRM sweep:** 2026-08-13 local scan learned 296 DRM vs 85 playable (incl. BTN, CBSSN, BET). Test whether `x-drm-scheme: widevine` makes Fubo serve DRM variants; learned ids are only re-checked with `force=true`
- `token()` holds the shared lock during network sign-in (status/metrics can stall up to 30s)

---

## Current focus

- Idle; guide investigation blocked on field data.

## Scratch

_Public imports stay `from app.fubo_client import …`._
_Guide join = tvg-id call sign only._
_Compose: `main` → `:latest`, `dev` → `:dev`._
_Do not log or commit secrets / raw passwords / bearer tokens / session.json._
