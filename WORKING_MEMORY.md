# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-09-17  
**Active version:** 1.0.10  
**Phase:** Auth hardening on `dev`  
**Git:** `dev` (Compose `:dev`); `main` / `:latest` = 1.0.9 until merge

---

## Resume here (this session)

**1.0.10** on `dev`: session persist (`config/session.json`) + `AUTH_COOLDOWN_SECONDS` cool-down; docs aligned; tests green.

### Next actions
1. Deploy `:dev` after push; confirm `/status.json` auth fields after a successful sign-in
2. One clean sign-in after any remaining lockout (reset once if needed), then leave `session.json` alone
3. Optional: `DRM_SCAN_ON_START=false` until first successful session is stable
4. Merge to `main` when ready for `:latest`

---

## Backlog

_(None beyond merge 1.0.10 to main when ready.)_

---

## Current focus

- Auth session persistence + cool-down on `dev`.

## Scratch

_Public imports stay `from app.fubo_client import …`._
_Guide join = tvg-id call sign only._
_Compose: `main` → `:latest`, `dev` → `:dev`._
_Do not log or commit secrets / raw passwords / bearer tokens / session.json._
