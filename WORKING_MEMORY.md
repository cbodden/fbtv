# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-08-12 (1.0.6 DRM scan 429 pacing)  
**Active version:** 1.0.6  
**Phase:** Push `:dev` for field retest after Fubo 429  
**Git:** committing + pushing `dev` (no merge to `main`)

---

## Resume here (this session)

1. Pull `ghcr.io/cbodden/fbtv:dev` after Actions builds 1.0.6
2. Confirm `/health` → `1.0.6`; logs should show concurrency=1, delay_ms=750, and few/no unhandled 429 floods
3. Optional: `POST /admin/drm-scan?force=true`; watch `rate_limited` in progress/complete logs
4. If still 429-heavy: raise `DRM_SCAN_DELAY_MS` (e.g. 1500)
5. Later (user-gated): merge `dev` → `main` for `:latest`

## Current focus

- 1.0.6 DRM scan pacing after field `vapi/asset` **429 Too Many Requests**

## Scratch

_Scratch: Classify DRM only — do not decrypt. Pace probes; do not decrypt._
