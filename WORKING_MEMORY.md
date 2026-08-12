# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-08-12 (1.0.6 docs sync for field test)  
**Active version:** 1.0.6  
**Phase:** Field-test paced DRM scan on `:dev`  
**Git:** push `dev` only (no merge to `main`)

---

## Resume here (this session)

1. Pull `ghcr.io/cbodden/fbtv:dev` after Actions builds (docs-only commit may not rebuild image — code already at 1.0.6)
2. Confirm `/health` → `1.0.6`; logs `concurrency=1, delay_ms=750`
3. Optional: `POST /admin/drm-scan?force=true`; watch `rate_limited` stay low
4. If still 429-heavy: `DRM_SCAN_DELAY_MS=1500`
5. Later (user-gated): merge `dev` → `main` for `:latest`

## Current focus

- Documentation synced for 1.0.6 DRM pacing; awaiting operator retest

## Scratch

_Scratch: Classify DRM only — do not decrypt. Pace probes._
