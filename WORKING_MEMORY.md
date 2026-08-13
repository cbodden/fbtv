# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-08-13 (hygiene C committed + pushed to `dev`)  
**Active version:** 1.0.7 (+ Unreleased hygiene on `dev` → `:dev`)  
**Phase:** Hygiene C complete  
**Git:** `dev`

---

## Resume here (this session)

**C** shipped on `dev`: CI tests, multi-arch GHCR, `ADMIN_TOKEN`, `/ready`.

Next: field-check `:dev` image after GHCR rebuild, or **D** later items when requested.

---

## Backlog

### A / B / C — done

### D. Later

10. Split `app/fubo_client.py`
11. pytest conversion
12. M3U `tvg-chno`
13. Warm caches on `/status`

---

## Current focus

- Hygiene C on `dev`; next backlog is D.

## Scratch

_ADMIN_TOKEN empty = open admin endpoints. /ready = creds only, no Fubo HTTP._
_Multi-arch lengthens docker CI._
