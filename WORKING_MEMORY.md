# Working memory

Short-lived project state for the current effort. Agents and humans should **update this file** as work progresses. Durable facts belong in [CONTEXT.md](CONTEXT.md).

**Last updated:** 2026-08-12 (1.0.4 docs + `/epg` parser + GHCR `:dev` workflow; commit requested)  
**Active version:** 1.0.4  
**Phase:** Commit 1.0.4 on `dev`; pull `ghcr.io/cbodden/fbtv:dev` for field EPG confirm; Emby Guide Data until then  
**Git:** committing on `dev`; **do not merge to `main` unless user asks**

---

## Resume here (this session)

1. After push: wait for Actions → image `ghcr.io/cbodden/fbtv:dev`
2. Compose/Portainer: `image: ghcr.io/cbodden/fbtv:dev` + `pull_policy: always` → pull/up
3. Confirm `/health` version `1.0.4`; warm `/epg.xml`; logs should show `Loaded N programmes from epg` or clear INFO failures
4. Emby: keep **Guide Data FuboTV** until `epg.programme_count` > 0
5. Later (user-gated): merge `dev` → `main` for `:latest`

## Current focus

- Ship 1.0.4: parse live `/epg` 200 payload; GHCR builds on `dev` as `:dev`
- Emby Guide Data remains recommended until field-confirmed programmes

## Open questions / blockers

| Item | Status | Notes |
| --- | --- | --- |
| `/epg` HTTP | 200 in field (2026-08-12) | Old image mapped 0 programmes (wrong JSON shape) |
| Usable EPG programmes | Pending `:dev` deploy | 1.0.4 dedicated parser |
| Merge `dev` → `main` | Blocked by user | Explicitly hold off |
| Jellyfin field validation | Not run | Docs exist |

## Field notes

```text
Date: 2026-08-12
/epg?startTime&endTime → 200 OK
v3/epg, tvguide, kgraph epg, epg/v1/listings, per-station → 404
No papi call on pre-1.0.4 image
"Loaded N programmes" is a log line only (not in epg.xml body)
```

## Decisions log (recent)

| When | Decision | Why |
| --- | --- | --- |
| 2026-08-12 | Prefer `/epg` assets parser; Emby Guide Data docs; no merge | User logs + #2/#3 |
| 2026-08-12 | GHCR workflow on `dev` → `:dev` tag | User: automatic image from dev |
| 2026-08-12 | Full docs sync + commit, no co-author | User request |

## Scratch

_Scratch: After commit/push, operator switches Compose to `:dev` for EPG field test._
