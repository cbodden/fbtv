# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-08-12 (1.0.5 DRM scan docs + commit/push to `dev`)  
**Active version:** 1.0.5  
**Phase:** Push `:dev` for field DRM-sweep test  
**Git:** committing + pushing `dev` (no merge to `main`)

---

## Resume here (this session)

1. Pull `ghcr.io/cbodden/fbtv:dev` after Actions builds 1.0.5
2. Confirm `/health` → `1.0.5`; logs `DRM scan complete…`
3. Refresh Emby M3U/EPG; optional `POST /admin/drm-scan?force=true`
4. Later (user-gated): merge `dev` → `main` for `:latest`

## Current focus

- 1.0.5 background DRM sweep shipped to `dev` for testing

## Scratch

_Scratch: Classify DRM only — do not decrypt._
