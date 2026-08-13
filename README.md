# Fubo → Emby & Jellyfin Bridge (`fbtv`)

**Version 1.0.7** — Python sidecar that signs into your personal Fubo account and exposes Live TV feeds for **Emby** and **Jellyfin** (M3U playlist + XMLTV guide + per-channel watch resolve).

**Project:** [`cbodden/fbtv`](https://github.com/cbodden/fbtv) (public) · **Docker image:** `fbtv` / [`ghcr.io/cbodden/fbtv`](https://github.com/cbodden/fbtv/pkgs/container/fbtv)

This is **not** a native Emby plugin or Jellyfin plugin. Both servers already support M3U tuners and XMLTV; this service sits beside them and translates Fubo’s private API into those formats. **One bridge instance** can feed Emby, Jellyfin, or both — see [docs/MEDIA_SERVERS.md](docs/MEDIA_SERVERS.md).

| Endpoint | Emby / Jellyfin use |
| --- | --- |
| `http://<host>:7777/playlist.m3u` | Live TV → **M3U Tuner** (channel list + tune URLs) |
| `http://<host>:7777/epg.xml` | Live TV → **XMLTV** guide data |
| `http://<host>:7777/watch/<id>` | Stream URL in the playlist: default **302 → HLS**; with `STREAM_PROXY=true` → **MPEG-TS** remux |
| `http://<host>:7777/` | HTML index with copy-paste URLs + live snapshot |
| `http://<host>:7777/status` | Human status page |
| `http://<host>:7777/status.json` | JSON status |
| `http://<host>:7777/metrics` | Prometheus metrics |
| `http://<host>:7777/health` | Liveness check (`{"status":"ok","version":"…"}`) |
| `http://<host>:7777/ready` | Readiness (`credentials` resolvable; no live Fubo call) |

---

## Table of contents

1. [What this does](#what-this-does)
2. [Requirements](#requirements)
3. [Install](#install)
4. [Configure](#configure)
5. [Wire Emby and Jellyfin](#wire-emby-and-jellyfin)
6. [How to use day-to-day](#how-to-use-day-to-day)
7. [Status and metrics](#status-and-metrics)
8. [Verify with curl](#verify-with-curl)
9. [How it works](#how-it-works)
10. [Limitations](#limitations)
11. [Troubleshooting](#troubleshooting)
12. [Further documentation](#further-documentation)

---

## What this does

Fubo does not offer an official Emby or Jellyfin plugin. This bridge fills that gap for **personal use** with your own paid subscription:

1. **Signs in** to `api.fubo.tv` with your email/password and a stable device id (`config/device.json`).
2. **Discovers your lineup** from Fubo subscription / plan APIs and **skips DRM** (known packages, learned/scanned `drmProtected`, plus optional allow/deny overrides).
3. **Serves an M3U** whose each channel points at this bridge (`/watch/<stationId>`), not at a raw CDN URL. Lines include `tvg-id` (call sign) and `tvg-chno` (1-based lineup order).
4. **On tune**, resolves a live HLS URL from Fubo and either **HTTP 302 redirects** to that stream (default; shared egress) or **remuxes to MPEG-TS** when `STREAM_PROXY=true` (split egress).
5. **Builds XMLTV** from Fubo guide data when available (prefers `/epg`, then `papi/v1/guide/epg`); otherwise still emits channel rows so Emby and Jellyfin can map by call sign (`tvg-id`). Emby operators can use **Guide Data FuboTV** when programmes are empty.

```text
┌────────────────────┐   playlist.m3u / epg.xml   ┌──────────────────────────┐
│ Emby Live TV       │ ─────────────────────────► │ Fubo → Emby & Jellyfin   │
│ and/or             │ ◄───────────────────────── │ Bridge (FastAPI)         │
│ Jellyfin Live TV   │                            └────────────┬─────────────┘
└────────────────────┘                                         │
       │                                                       │ auth, lineup,
       │  GET /watch/{id}                                      │ schedule, stream
       └───────────────────────────────────────────────────────┤
              302 → HLS (default; client hits CDN)             ▼
              or video/mp2t remux (STREAM_PROXY)        ┌─────────────┐
                                                        │ api.fubo.tv │
                                                        │ + CDN       │
                                                        └─────────────┘
```

**Topology**

- **Default (302):** run the bridge on the **same machine (or same public egress IP)** as Emby and/or Jellyfin. Fubo often binds stream URLs to the IP that requested them; a redirect minted on one network and fetched from another commonly fails.
- **Split egress:** set `STREAM_PROXY=true` so the bridge pulls HLS and streams MPEG-TS to the media server (higher CPU; see [docs/CONFIGURATION.md](docs/CONFIGURATION.md)).

```text
Same egress (default 302)
  Emby/Jellyfin  ──LAN──►  fbtv:7777  ──302──►  Fubo CDN

Split egress (optional remux)
  Emby/Jellyfin elsewhere  ──►  fbtv:7777 (STREAM_PROXY=true)  ──►  Fubo CDN
```

---

## Requirements

- A valid **Fubo** subscription (use **your own** credentials only)
- At least one media server:
  - **Emby Server** with **Premiere** (required for Live TV), and/or
  - **Jellyfin** (Live TV included; no Premiere equivalent)
- **Docker** (recommended) **or** Python **3.11+**
- Network path so Emby and/or Jellyfin can reach the bridge on port `7777` (or your chosen `PORT`)

Personal / home-LAN use only. Respect Fubo’s terms of service. Do not redistribute streams or share accounts. See [SECURITY.md](SECURITY.md).

---

## Install

### Option A — Docker (recommended)

Compose **pulls** `ghcr.io/cbodden/fbtv:latest` on **`main`** (no local build) and does **not** load a project `.env` file. GHCR publishes on pushes to **`main`** (`:latest`) and **`dev`** (`:dev`). The **`dev`** branch Compose should use `:dev` for pre-release.

**Credentials (pick one; file wins over env):**

1. **Portainer / special characters (`$`, `!`):** put this on the config volume as `config/credentials.env` (no quotes):

```text
FUBO_USER=you@example.com
FUBO_PASS_B64=<output of: printf '%s' 'your$password' | base64 -w0>
```

   Or: `printf '%s\n%s\n' 'you@example.com' 'your$password' | docker exec -i fbtv python -m app.set_credentials`

2. **CLI alphanumeric password:**

```bash
export FUBO_USER='you@example.com'
export FUBO_PASS='your-password'
docker compose up -d
```

Service/container name is **`fbtv`**. It maps host `${PORT:-7777}` → container `7777`, mounts `./config`, and sets `pull_policy: always`.

Optional overrides: `PORT`, `EPG_CACHE_SECONDS`, `EPG_EMPTY_CACHE_SECONDS`, `EPG_DAYS`, `STREAM_PROXY`, `STREAM_PROXY_MAX`, `ADMIN_TOKEN`, `DRM_DENY_IDS` / `DRM_ALLOW_IDS` (prefer `config/drm_overrides.json`). Full detail: [docs/CONFIGURATION.md](docs/CONFIGURATION.md) and [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

GitHub Actions: `.github/workflows/docker.yml` (multi-arch `amd64`/`arm64`; tags `latest` / `dev` / `sha-<commit>`) and `.github/workflows/test.yml` (unit tests).

If the GHCR package is private, authenticate once: `echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin`.

Check it:

```bash
curl -sS http://127.0.0.1:7777/health
# → {"status":"ok","version":"1.0.7"}
curl -sS http://127.0.0.1:7777/ready
# → {"status":"ready","version":"1.0.7"}
```

Open `http://localhost:7777/` in a browser for copy-paste URLs and a live status snapshot (also `/status`, `/status.json`, `/metrics`).

Logs:

```bash
docker compose logs -f fbtv
```

Stop:

```bash
docker compose down
```

### Option B — Local Python

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env — set FUBO_USER and FUBO_PASS

uvicorn app.main:app --host 0.0.0.0 --port 7777
```

The process **will not start** unless credentials are available from a credentials file, `FUBO_PASS_B64`, or `FUBO_USER` + `FUBO_PASS`.

---

## Configure

### Docker Compose / Portainer

Compose does not use `env_file`. Prefer `config/credentials.env` with `FUBO_PASS_B64` when the password has `$` or other special characters. Alphanumeric passwords may be exported as `FUBO_USER` / `FUBO_PASS`.

### Local Python

Copy `.env.example` → `.env` and edit. Never commit `.env`. Loaded with `interpolate=False` so `$` in `.env` is left alone. You can also use `config/credentials.json`.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `FUBO_USER` | if no credentials file | — | Fubo account email |
| `FUBO_PASS` | if no file / B64 | — | Password (avoid `$` here) |
| `FUBO_PASS_B64` | no | — | Base64 UTF-8 password; wins over `FUBO_PASS` |
| `HOST` | no | `0.0.0.0` | Bind address (local uvicorn) |
| `PORT` | no | `7777` | Listen port (Compose maps host `PORT` → container `7777`) |
| `CONFIG_DIR` | no | `./config` | Writable dir for `device.json`, credentials files, `drm_skipped.json`, `drm_overrides.json` |
| `EPG_CACHE_SECONDS` | no | `3600` | How long to reuse generated `epg.xml` when programmes exist |
| `EPG_EMPTY_CACHE_SECONDS` | no | `120` | How long to reuse channel-only XMLTV (`0` = no cache) |
| `EPG_DAYS` | no | `2` | Desired guide window when schedule data exists |
| `DRM_SCAN_ON_START` | no | `true` | Background DRM asset sweep after startup |
| `DRM_SCAN_CONCURRENCY` | no | `1` | Parallel `vapi/asset` probes (keep at 1; Fubo **429**s) |
| `DRM_SCAN_DELAY_MS` | no | `750` | Minimum gap between probes |
| `DRM_SCAN_MAX_AGE_HOURS` | no | `24` | Skip non-forced scans when `last_scan_at` is fresh |
| `DRM_SCAN_INTERVAL_HOURS` | no | `24` | Periodic rescan (0 = off) |
| `STREAM_PROXY` | no | `false` | Remux HLS→MPEG-TS via ffmpeg on `/watch` (split egress) |
| `STREAM_PROXY_MAX` | no | `3` | Max concurrent remuxes |
| `FFMPEG_PATH` | no | `ffmpeg` | ffmpeg binary path |
| `DRM_DENY_IDS` / `DRM_ALLOW_IDS` | no | — | Optional station-id overrides (prefer `config/drm_overrides.json`) |
| `DRM_DENY_CALL_SIGNS` / `DRM_ALLOW_CALL_SIGNS` | no | — | Optional call-sign overrides |
| `ADMIN_TOKEN` | no | — | When set, require Bearer or `X-Admin-Token` on `/admin/drm-scan` |

**Runtime files**

| Path | Purpose |
| --- | --- |
| `.env` | Optional local-Python secrets (gitignored); not used by Compose |
| `config/credentials.env` | `FUBO_USER` + `FUBO_PASS_B64` (preferred) or `FUBO_PASS` |
| `config/credentials.json` | Same secrets; write with `python -m app.set_credentials` |
| `config/device.json` | Stable Fubo `x-device-id` (created on first run) |
| `config/drm_skipped.json` | DRM station ids from tune or background scan (kept out of later playlists/EPG) |
| `config/drm_overrides.json` | Optional manual DRM allow/deny station ids / call signs |
| `config/.gitkeep` | Keeps empty config dir in git |

Delete `config/device.json` only if you intentionally want a new device identity (can trigger extra sign-in friction).

**Reverse proxy:** if Emby or Jellyfin reaches the bridge through a proxy, forward `X-Forwarded-Host` and `X-Forwarded-Proto` so playlist watch URLs use a hostname both servers can resolve.

Full detail: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

---

## Wire Emby and Jellyfin

Emby and Jellyfin use the **same** bridge URLs. Differences are mostly license (Emby Premiere vs Jellyfin included Live TV) and guide fallbacks. Full comparison: [docs/MEDIA_SERVERS.md](docs/MEDIA_SERVERS.md).

### Shared prerequisites

1. Bridge is running.
2. From each **media server host**, `http://<bridge-host>:7777/health` and `/ready` return OK.
3. `http://<bridge-host>:7777/playlist.m3u` downloads a non-empty playlist.
4. Prefer **same machine or same public egress IP** for the bridge and every server that will tune.

Use a hostname/IP Emby and Jellyfin can resolve (LAN IP or `host.docker.internal` if the media server runs in Docker and the bridge is on the host). Avoid `localhost` in the M3U unless that loopback is shared.

### Shared playlist fields

| M3U attribute | Meaning |
| --- | --- |
| `tvg-id` | Joins to XMLTV `channel id` (Fubo call sign) |
| `tvg-chno` | 1-based channel number in current lineup order |
| `tvg-name` / display name | Channel label |
| `tvg-logo` | Artwork when present |
| `group-title` | Package / plan grouping (tags) |
| URL line | `http://<bridge>/watch/<stationId>` |

### Emby

1. **Dashboard → Live TV → Tuner Devices → +** → **M3U Tuner** → `http://<bridge-host>:7777/playlist.m3u`
2. **Guide (recommended while bridge programmes are empty):** **TV Guide Data Providers → +** → **Emby Guide Data** → **FuboTV** lineup for your ZIP
3. Optional: also add **XMLTV** → `http://<bridge-host>:7777/epg.xml` once `/status.json` shows `epg.programme_count` > 0
4. Set simultaneous streams to match your Fubo plan (lower if Jellyfin also uses this bridge)
5. Tune a non-DRM channel; if playback fails after redirect, fix shared egress or enable `STREAM_PROXY`

Premiere is required. Full walkthrough: [docs/EMBY_SETUP.md](docs/EMBY_SETUP.md).

### Jellyfin

1. **Dashboard → Live TV → Tuner Devices → +** → **M3U Tuner** → `http://<bridge-host>:7777/playlist.m3u`
2. **TV Guide Data Providers → +** → **XMLTV** → `http://<bridge-host>:7777/epg.xml`
3. Set simultaneous streams to match your Fubo plan (lower if Emby also uses this bridge)
4. If guide rows do not auto-map, edit channels under **Live TV → Channels**
5. Tune a non-DRM channel; if playback fails after redirect, fix shared egress or enable `STREAM_PROXY`

Live TV needs no Premiere equivalent. Full walkthrough: [docs/JELLYFIN_SETUP.md](docs/JELLYFIN_SETUP.md).

### Sparse EPG fallbacks

When `tvg-id` matches XMLTV channel ids, mapping is often automatic. If `/status.json` shows `epg.programme_count` at `0` (common when older schedule URLs 404), prefer a denser third-party guide:

| Server | Recommended while bridge programmes are empty |
| --- | --- |
| Emby | **Emby Guide Data FuboTV** lineup + manual map (primary guide until bridge EPG is populated) |
| Jellyfin | Schedules Direct **or** another XMLTV source (**not** together with bridge XMLTV) + manual map |

From **1.0.4+** the bridge probes `/epg` first (with a dedicated parser), then `papi/v1/guide/epg`. **1.0.5+** adds a background DRM asset sweep (paced for Fubo **429** limits in **1.0.6+**) so DRM stations are dropped from M3U/EPG without waiting for a failed tune. **1.0.7** adds HEAD `/watch`, empty-EPG short TTL, stronger `/epg` joins, optional `STREAM_PROXY` remux, and DRM allow/deny. Unreleased on `:dev`: CI unit tests, multi-arch images, `ADMIN_TOKEN`, `/ready`, M3U `tvg-chno`, status channel warm. Stable image: `ghcr.io/cbodden/fbtv:latest` (**1.0.7**). Pre-release: `:dev`.

### Using Emby and Jellyfin together

Point both at the same `playlist.m3u` / `epg.xml`. Cap **combined** simultaneous streams to your Fubo plan. Every host that tunes must share egress with the bridge.

---

## How to use day-to-day

Once installed and wired:

1. **Leave the bridge running** (Compose `restart: unless-stopped`, or a systemd/user service for uvicorn).
2. Use **Emby** and/or **Jellyfin** Live TV as usual — channel change hits `/watch/{id}` (302 to HLS by default, or MPEG-TS when `STREAM_PROXY=true`).
3. **Guide refresh** happens on each media server’s XMLTV schedule; the bridge may serve a cached `/epg.xml` for up to `EPG_CACHE_SECONDS` (or `EPG_EMPTY_CACHE_SECONDS` when programmes are empty).
4. **Credential / device changes:** update `config/credentials.env` (or JSON / env) and restart. Only delete `config/device.json` as a last resort. Delete `config/drm_skipped.json` only if you want previously learned DRM stations back in the playlist. Edit `config/drm_overrides.json` (or `DRM_*` env) to force-deny or allowlist stations — see [docs/CONFIGURATION.md](docs/CONFIGURATION.md#drm-allow--deny-overrides).
5. **After Fubo plan changes:** restart the bridge (or wait for the ~30 minute in-memory channel cache) and re-refresh tuners in Emby and Jellyfin if channel counts look wrong.
6. **Status / metrics:** see [Status and metrics](#status-and-metrics) below.
7. **OpenAPI:** while running, browse `http://<host>:7777/docs` for interactive endpoint docs.

Do not paste raw Fubo CDN URLs into Emby or Jellyfin. Always use the bridge playlist so each tune goes through a fresh `/watch/{id}` resolve.

---

## Status and metrics

Operators can inspect runtime state without scraping logs:

| URL | Purpose |
| --- | --- |
| `http://<host>:7777/` | HTML index + live snapshot cards (channels, signed-in, DRM skips/learned, EPG programmes, uptime, watch counters) |
| `http://<host>:7777/status` | Full HTML status table |
| `http://<host>:7777/status.json` | Same snapshot as JSON |
| `http://<host>:7777/metrics` | Prometheus text metrics (`fubo_bridge_*`) |
| `http://<host>:7777/health` | Liveness only (`status` + `version`) — does **not** verify Fubo |
| `http://<host>:7777/ready` | Readiness — credentials resolvable (no live Fubo call) |

Counts on `/`, `/status`, and `/status.json` **warm the channel lineup** (cached ~30 minutes). `/metrics` stays cache-only. EPG programme fields still need `/epg.xml`. Snapshots do not include passwords or bearer tokens.

Guide: [docs/STATUS.md](docs/STATUS.md). API details: [docs/API.md](docs/API.md).

---

## Verify with curl

Run these from a machine that can reach the bridge (ideally each Emby / Jellyfin host):

```bash
curl -sS http://127.0.0.1:7777/health
curl -sS http://127.0.0.1:7777/ready
curl -sS http://127.0.0.1:7777/status.json
curl -sS http://127.0.0.1:7777/metrics | head
curl -sS http://127.0.0.1:7777/playlist.m3u | head
curl -sS http://127.0.0.1:7777/epg.xml | head
curl -sSI http://127.0.0.1:7777/watch/<stationId>              # HEAD probe: 200 (no tune)
curl -sS -D - -o /dev/null http://127.0.0.1:7777/watch/<stationId>  # GET: 302 + Location: …m3u8
```

`<stationId>` is the numeric id on the `channel-id=` attribute / watch path in the M3U.

---

## How it works

1. Load or create `CONFIG_DIR/device.json` (`x-device-id`).
2. `PUT /signin` with Android TV–style client headers; cache bearer token ~4 hours.
3. Build lineup via subscriptions APIs, with plan-manager + recurly packages as fallback; drop DRM sources and previously learned/scanned DRM station ids. Optional background DRM sweep probes assets and updates the skip list.
4. Serve M3U with absolute `/watch/…` URLs (honors `X-Forwarded-Host` / `X-Forwarded-Proto`).
5. On watch **GET**: call `vapi/asset/v1?channelId=…&type=live`; reject `drmProtected` (and remember the station for future playlists); otherwise **302** to HLS, or **MPEG-TS remux** when `STREAM_PROXY=true`. **HEAD** returns 200 without calling Fubo (probe only; Content-Type follows mode).
6. On EPG: probe `/epg` (`channelWithProgramAssets`, join by `id` / `stationId` / `callSign`), then `papi/v1/guide/epg`, then older fallbacks; map to call signs; cache XMLTV (`EPG_CACHE_SECONDS`, or `EPG_EMPTY_CACHE_SECONDS` when programmes are empty).

Design notes: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). HTTP details: [docs/API.md](docs/API.md).

---

## Limitations

- **Unofficial API** — Fubo does not document this for third-party use. Endpoints/headers can change without notice.
- **DRM** — Protected packages are skipped; tune-time and background-scan `drmProtected` stations are remembered and dropped from later playlists/EPG (`config/drm_skipped.json`). Optional allow/deny overrides adjust that list (`config/drm_overrides.json`). Decryption is out of scope.
- **IP binding** — Stream URLs are often tied to the requesting public IP. Same host / same egress is recommended for **302** mode. Set `STREAM_PROXY=true` to remux through the bridge when egress cannot be shared (CPU cost).
- **EPG depth** — If schedule endpoints fail or change, `/epg.xml` still lists channels; programme rows may be empty or sparse. Empty guides are cached only briefly (`EPG_EMPTY_CACHE_SECONDS`).
- **Remux is opt-in** — Default remains redirect-only; enable `STREAM_PROXY` when needed (see CHANGELOG **1.0.7** / CONFIGURATION).

> **Personal use — Your own paid account only.**
>
> This bridge is for personal / home-LAN use with **your own** paid Fubo subscription. Do not redistribute streams or share accounts. See [SECURITY.md](SECURITY.md).

---

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| Process exits mentioning credentials | Set `config/credentials.env` (`FUBO_PASS_B64` if the password has `$`), or env / local `.env` |
| Sign-in 401 `INVALID_USERNAME_PASSWORD` | Use `FUBO_PASS_B64` or `python -m app.set_credentials`; do not quote passwords — [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) |
| Empty playlist or `502` on `/playlist.m3u` | Confirm credentials on fubo.tv; check logs for sign-in / API drift |
| Channels import but will not play | Confirm non-DRM; run `/admin/drm-scan` then refresh M3U; GET `/watch/{id}` (302 or `video/mp2t` if `STREAM_PROXY`); fix shared egress / Cloudflare 403 or enable remux |
| Logs show `vapi/asset` **429** during DRM scan | Use **1.0.6+** (`:latest` or `:dev`); keep `DRM_SCAN_CONCURRENCY=1`; raise `DRM_SCAN_DELAY_MS` (e.g. 1500) |
| Guide has channels but no programmes | Emby: Guide Data FuboTV (recommended); Jellyfin: Schedules Direct; after 1.0.4+ check logs for `Loaded N programmes from epg` (log line, not XML) |
| Want to force-drop or un-skip a channel | `config/drm_overrides.json` deny/allow — [docs/CONFIGURATION.md](docs/CONFIGURATION.md#drm-allow--deny-overrides) |
| Emby or Jellyfin cannot reach bridge | `curl` health (or `/status.json`) from that host; fix Docker networking / firewall / published port |
| Status shows empty channel count after restart | Open `/` or `/status.json` (they warm the lineup), or hit `/playlist.m3u` |
| Playlist URLs say `localhost` but server is elsewhere | Fetch playlist via LAN IP Emby/Jellyfin can use, or set forwarded host headers |

More: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

---

## Further documentation

| Doc | Description |
| --- | --- |
| [docs/README.md](docs/README.md) | Documentation index |
| [docs/MEDIA_SERVERS.md](docs/MEDIA_SERVERS.md) | Emby & Jellyfin comparison; one bridge for both |
| [docs/EMBY_SETUP.md](docs/EMBY_SETUP.md) | Emby Live TV wiring |
| [docs/JELLYFIN_SETUP.md](docs/JELLYFIN_SETUP.md) | Jellyfin Live TV wiring |
| [docs/STATUS.md](docs/STATUS.md) | Status / metrics (`/` `/status` `/status.json` warm channels; `/metrics` cache-only; `/health` `/ready`) |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Environment variables and runtime files (incl. `ADMIN_TOKEN`, `STREAM_PROXY`) |
| [docs/API.md](docs/API.md) | HTTP API reference (incl. M3U `tvg-chno`) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Design and data flow |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common failures and curl checks |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development guidelines |
| [SECURITY.md](SECURITY.md) | Credentials and threat model |
| [CREDITS.md](CREDITS.md) | Attribution for prior art and dependencies |
| [CHANGELOG.md](CHANGELOG.md) | Release history |
| [CONTEXT.md](CONTEXT.md) | Durable project context (agents/humans) |
| [WORKING_MEMORY.md](WORKING_MEMORY.md) | Current session focus |

### Development layout

```text
app/
  main.py             # FastAPI routes
  fubo_client.py      # Auth (client 5.40.0), channels, watch, schedule
  config.py           # Settings + credentials file / FUBO_PASS_B64
  set_credentials.py  # Write credentials.json from stdin
  m3u.py / epg.py / status.py
docs/                 # Deep-dive documentation
tests/                # Unit checks (no live Fubo calls)
credentials.env.example
.github/workflows/docker.yml  # Multi-arch GHCR (main → :latest, dev → :dev)
.github/workflows/test.yml    # Unit tests (test_builders.py)
docker-compose.yml            # On `main` pulls ghcr.io/cbodden/fbtv:latest (`dev` branch uses :dev)
```

```bash
PYTHONPATH=. python tests/test_builders.py
```

---

## Credits

Auth, lineup, and stream patterns draw on community Fubo bridge projects (Yankees4life, maus-me, jgomez177 / Channels DVR thread) and open-source Python libraries (FastAPI, Uvicorn, HTTPX, python-dotenv). Full attribution: [CREDITS.md](CREDITS.md).
