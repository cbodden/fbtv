# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-08-13 (1.0.7 merged to `main`; `dev` Compose restored to `:dev`)  
**Active version:** 1.0.7  
**Phase:** Post-1.0.7 hygiene on `dev`  
**Git:** `dev` (Compose `:dev`); `main` / `:latest` = 1.0.7

---

## Resume here (this session)

**1.0.7** shipped to `main` (PR #1). Next: **C** hygiene when requested.

---

## Backlog

### A / B — done (1.0.7)

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

- Wait for GHCR `:latest` = 1.0.7; then hygiene C.

## Scratch

_Deny wins over allow. Allow is not DRM decrypt._
_STREAM_PROXY default false; ffmpeg -c copy -f mpegts._
