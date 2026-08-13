# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-08-13 (B2 DRM allow/deny docs + push to `dev`)  
**Active version:** 1.0.6 (Unreleased on `dev` → `:dev`)  
**Phase:** Post-1.0.6 hardening on `dev`  
**Git:** `dev`

---

## Resume here (this session)

Section **B** complete on `dev` (STREAM_PROXY + DRM allow/deny).

Field-check overrides after `:dev` rebuild:

1. Deny an id → missing from `/playlist.m3u` after refresh
2. Allow a learned DRM id → back in playlist; real DRM still 502 on tune
3. `/status.json` → `fubo.drm_overrides`

Next: **C** hygiene when requested.

---

## Backlog

### A / B — done

### C. Hygiene — next

6. Run `tests/test_builders.py` in GitHub Actions
7. Multi-arch `linux/arm64` GHCR image
8. Optional shared secret on `/admin/drm-scan`
9. `/ready` vs `/health`

### D. Later

10. Split `app/fubo_client.py`
11. pytest conversion
12. M3U `tvg-chno`
13. Warm caches on `/status`

---

## Current focus

- B2 pushed; ready for C or field override check.

## Scratch

_Deny wins over allow. Allow is not DRM decrypt._
