# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-08-13 (B1 docs + commit/push to `dev`)  
**Active version:** 1.0.6 (Unreleased on `dev` → `:dev`)  
**Phase:** Post-1.0.6 hardening on `dev`  
**Git:** `dev` (B1 STREAM_PROXY)

---

## Resume here (this session)

Section **B1** landed on `dev`. Field-check remux after GHCR `:dev` rebuilds:

1. `STREAM_PROXY=false` — GET `/watch/<id>` still **302**
2. `STREAM_PROXY=true` — GET `video/mp2t`; `/status.json` → `stream_proxy.enabled=true`
3. Over `STREAM_PROXY_MAX` → **503**

Next: **B2** DRM allow/deny lists when requested.

---

## Backlog (section by section)

### A. Do first — done (field-checked)

### B. Unreleased product

4. Optional MPEG-TS remux / stream proxy — **done** (`STREAM_PROXY`)
5. Configurable DRM allow/deny lists — **next**

### C. Hygiene

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

- B1 pushed; ready for B2 or field remux verify.

## Scratch

_Scratch: Classify DRM only — do not decrypt. Pace probes._
_STREAM_PROXY default false; ffmpeg -c copy -f mpegts._
