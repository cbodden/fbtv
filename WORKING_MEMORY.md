# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-08-13 (dev; section A + docs; ready to push)  
**Active version:** 1.0.6 (Unreleased work on `dev` → `:dev`)  
**Phase:** Post-1.0.6 hardening on `dev`  
**Git:** `dev` (section A unreleased)

---

## Resume here (this session)

Section **A** is in the working tree. Next: field-check, then **B** when you say so.

Field check after this lands on `:dev`:

1. Pull `ghcr.io/cbodden/fbtv:dev` (or run local uvicorn)
2. `GET /epg.xml` then `/status.json` → `epg.programme_count` and `epg.ttl_seconds` (expect ~120 if empty)
3. Logs: `Loaded N programmes from epg` **or** `mapped 0 programmes … sample_unmatched=`
4. `curl -sSI http://127.0.0.1:7777/watch/<id>` → **200**; GET → **302**

---

## Backlog (section by section)

### A. Do first — this branch

1. **EPG mapping / field confirm** — done in code (join `id` / `stationId` / `callSign` + unmatched log). Live `programme_count` still needs a field check.
2. **HEAD `/watch/{id}`** — done. HEAD → 200 mpegurl, no `vapi/asset`. GET unchanged 302.
3. **Empty EPG short cache** — done. `EPG_EMPTY_CACHE_SECONDS` default 120 (`0` = no cache).

### B. Unreleased product (CHANGELOG) — next

4. Optional MPEG-TS remux / stream proxy (split-IP / Docker-on-another-host)
5. Configurable DRM allow/deny lists (manual overrides on top of scan)

### C. Hygiene

6. Run `tests/test_builders.py` in GitHub Actions (image build does not)
7. Multi-arch `linux/arm64` GHCR image (NAS / Pi)
8. Optional shared secret on `/admin/drm-scan`
9. `/ready` vs `/health` (signed-in / credentials, not just liveness)

### D. Later / leave until it hurts

10. Split `app/fubo_client.py`
11. pytest conversion
12. M3U `tvg-chno`
13. Warm caches on `/status`

---

## Current focus

- Section **A** implemented on `dev`; waiting on field EPG check / next section

## Scratch

_Scratch: Classify DRM only — do not decrypt. Pace probes._
_HEAD /watch must not call Fubo. Empty XMLTV uses short TTL._
