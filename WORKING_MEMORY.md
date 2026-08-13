# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-08-13 (release/1.0.7 → main PR; Compose `:latest`)  
**Active version:** 1.0.7  
**Phase:** Release 1.0.7 to `main`  
**Git:** `release/1.0.7` (PR into `main`); keep `dev` Compose on `:dev` after merge

---

## Resume here (this session)

Ship **1.0.7** to `main` / `:latest`. After merge: restore `dev` Compose to `:dev` if needed, then **C** hygiene.

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

- Merge release PR; wait for GHCR `:latest`.

## Scratch

_Deny wins over allow. Allow is not DRM decrypt._
_STREAM_PROXY default false; ffmpeg -c copy -f mpegts._
