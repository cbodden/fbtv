# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-08-12 (1.0.6 docs cut + merge to `main`)  
**Active version:** 1.0.6  
**Phase:** Released on `main` (`:latest`)  
**Git:** `dev` + `main` both at 1.0.6

---

## Resume here (this session)

1. After GHCR builds `main`, pull `ghcr.io/cbodden/fbtv:latest` (`pull_policy: always`)
2. Confirm `/health` → `1.0.6`
3. Optional: `POST /admin/drm-scan?force=true`; if 429-heavy raise `DRM_SCAN_DELAY_MS`

## Current focus

- 1.0.6 released; monitor `:latest` field use

## Scratch

_Scratch: Classify DRM only — do not decrypt. Pace probes._
