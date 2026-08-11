# Fubo → Emby Bridge

**Version 1.0.0** — Python sidecar that signs into your personal Fubo account and exposes Emby-ready Live TV feeds (M3U playlist + XMLTV guide + per-channel watch redirects).

This is **not** an Emby .NET plugin. Emby Premiere already supports M3U tuners and XMLTV natively; this service sits beside Emby and translates Fubo’s private API into those formats.

| Endpoint | What Emby uses it for |
| --- | --- |
| `http://<host>:7777/playlist.m3u` | Live TV → **M3U Tuner** (channel list + tune URLs) |
| `http://<host>:7777/epg.xml` | Live TV → **XMLTV** guide data |
| `http://<host>:7777/watch/<id>` | Stream URL inside the playlist (302 → live HLS) |
| `http://<host>:7777/` | HTML index with copy-paste URLs |
| `http://<host>:7777/health` | Liveness check (`{"status":"ok","version":"…"}`) |

---

## Table of contents

1. [What this does](#what-this-does)
2. [Requirements](#requirements)
3. [Install](#install)
4. [Configure](#configure)
5. [Implement in Emby](#implement-in-emby)
6. [How to use day-to-day](#how-to-use-day-to-day)
7. [Verify with curl](#verify-with-curl)
8. [How it works](#how-it-works)
9. [Limitations](#limitations)
10. [Troubleshooting](#troubleshooting)
11. [Further documentation](#further-documentation)

---

## What this does

Fubo does not offer an official Emby plugin. This bridge fills that gap for **personal use** with your own paid subscription:

1. **Signs in** to `api.fubo.tv` with your email/password and a stable device id (`config/device.json`).
2. **Discovers your lineup** from Fubo subscription / plan APIs and **skips known DRM packages** (Disney, Starz, Showtime, Max/HBO, and similar).
3. **Serves an M3U** whose each channel points at this bridge (`/watch/<stationId>`), not at a raw CDN URL.
4. **On tune**, resolves a live HLS URL from Fubo and **HTTP 302 redirects** Emby (or VLC) to that stream.
5. **Builds XMLTV** when Fubo schedule endpoints respond; otherwise still emits channel rows so Emby can map by call sign (`tvg-id`).

```text
┌─────────────┐     playlist.m3u / epg.xml     ┌──────────────────┐
│ Emby Server │ ─────────────────────────────► │ Fubo Emby Bridge │
│  Live TV    │ ◄───────────────────────────── │   (FastAPI)      │
└─────────────┘                                └────────┬─────────┘
       │                                                │
       │  GET /watch/{id}                               │ auth, lineup,
       └────────────────────────────────────────────────┤ schedule, stream
                         302 → HLS URL                  ▼
                                                 ┌─────────────┐
                                                 │ api.fubo.tv │
                                                 └─────────────┘
```

**Best topology for v1:** run the bridge on the **same machine (or same public egress IP)** as Emby. Fubo often binds stream URLs to the IP that requested them; a redirect minted on one network and fetched from another commonly fails.

---

## Requirements

- A valid **Fubo** subscription (use **your own** credentials only)
- **Emby Server** with **Premiere** (Live TV)
- **Docker** (recommended) **or** Python **3.11+**
- Network path so Emby can reach the bridge on port `7777` (or your chosen `PORT`)

Personal / home-LAN use only. Respect Fubo’s terms of service. Do not redistribute streams or share accounts. See [SECURITY.md](SECURITY.md).

---

## Install

### Option A — Docker (recommended)

From the project root:

```bash
cp .env.example .env
# edit .env — set FUBO_USER and FUBO_PASS

docker compose up -d --build
```

Compose builds image `fubo-emby`, maps host `${PORT:-7777}` → container `7777`, loads `.env`, and mounts `./config` for the persistent device id.

Check it:

```bash
curl -sS http://127.0.0.1:7777/health
# → {"status":"ok","version":"1.0.0"}
```

Open `http://localhost:7777/` in a browser for copy-paste Emby URLs.

Logs:

```bash
docker compose logs -f fubo-emby
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

The process **will not start** if `FUBO_USER` or `FUBO_PASS` is missing.

---

## Configure

Copy `.env.example` → `.env` and edit. Never commit `.env`.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `FUBO_USER` | yes | — | Fubo account email |
| `FUBO_PASS` | yes | — | Fubo account password |
| `HOST` | no | `0.0.0.0` | Bind address (local uvicorn) |
| `PORT` | no | `7777` | Listen port (Compose maps host `PORT` → container `7777`) |
| `CONFIG_DIR` | no | `./config` | Writable dir for `device.json` |
| `EPG_CACHE_SECONDS` | no | `3600` | How long to reuse generated `epg.xml` |
| `EPG_DAYS` | no | `2` | Desired guide window when schedule data exists |

**Runtime files**

| Path | Purpose |
| --- | --- |
| `.env` | Secrets (gitignored) |
| `config/device.json` | Stable Fubo `x-device-id` (created on first run) |
| `config/.gitkeep` | Keeps empty config dir in git |

Delete `config/device.json` only if you intentionally want a new device identity (can trigger extra sign-in friction).

**Reverse proxy:** if Emby reaches the bridge through a proxy, forward `X-Forwarded-Host` and `X-Forwarded-Proto` so playlist watch URLs use the public hostname Emby can resolve.

Full detail: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

---

## Implement in Emby

Emby Premiere is required for Live TV.

### Prerequisites

1. Bridge is running.
2. From the **Emby Server host**, `http://<bridge-host>:7777/health` returns OK.
3. `http://<bridge-host>:7777/playlist.m3u` downloads a non-empty playlist.
4. Prefer **same machine or same public egress IP** for Emby and the bridge.

Use a hostname/IP Emby can resolve (LAN IP or `host.docker.internal` if Emby is in Docker and the bridge is on the host). Avoid putting `localhost` in the M3U unless Emby and the bridge share that loopback.

### 1. Add the M3U tuner

1. **Emby Dashboard → Live TV**
2. Under **Tuner Devices**, click **+**
3. Select **M3U Tuner**
4. Set:
   - **File or URL:** `http://<bridge-host>:7777/playlist.m3u`
   - A clear name (e.g. `Fubo`)
   - Simultaneous stream limit matching your Fubo plan
5. Save and allow Emby to import channels

Playlist fields Emby cares about:

| M3U attribute | Meaning |
| --- | --- |
| `tvg-id` | Joins to XMLTV `channel id` (Fubo call sign) |
| `tvg-name` / display name | Channel label |
| `tvg-logo` | Artwork when present |
| `group-title` | Package / plan grouping (tags) |
| URL line | `http://<bridge>/watch/<stationId>` |

### 2. Add XMLTV guide data

1. Under **TV Guide Data Providers**, click **+**
2. Select **XMLTV**
3. URL: `http://<bridge-host>:7777/epg.xml`
4. Choose a refresh interval (daily is typical; the bridge caches EPG for `EPG_CACHE_SECONDS`)
5. Save and refresh guide data

When `tvg-id` matches XMLTV channel ids, Emby often maps automatically. If programme rows are sparse, keep the bridge XMLTV for identity and optionally add Emby Guide Data’s **FuboTV** lineup for your ZIP, then map manually by name/call sign.

### 3. Playback check

1. Tune a non-DRM channel (news/basic sports usually fare better than premium movie nets).
2. If tune fails immediately → check bridge logs for DRM or HTTP errors.
3. If tune starts then fails → suspect **IP binding**; co-locate bridge and Emby egress.
4. Optional: on the Emby host, open a `/watch/<id>` URL from the M3U in VLC and confirm it redirects to an `.m3u8`.

Longer walkthrough: [docs/EMBY_SETUP.md](docs/EMBY_SETUP.md).

---

## How to use day-to-day

Once installed and wired:

1. **Leave the bridge running** (Compose `restart: unless-stopped`, or a systemd/user service for uvicorn).
2. Use Emby Live TV as usual — channel change hits `/watch/{id}`, which redirects to Fubo HLS.
3. **Guide refresh** happens on Emby’s XMLTV schedule; the bridge may serve a cached `/epg.xml` for up to `EPG_CACHE_SECONDS`.
4. **Credential / device changes:** update `.env` and restart the container/process. Only delete `config/device.json` as a last resort.
5. **After Fubo plan changes:** restart the bridge (or wait for the ~30 minute in-memory channel cache) and re-refresh the Emby tuner if channel counts look wrong.
6. **OpenAPI:** while running, browse `http://<host>:7777/docs` for interactive endpoint docs.

You do not paste raw Fubo CDN URLs into Emby. Always use the bridge playlist so each tune goes through a fresh `/watch/{id}` resolve.

---

## Verify with curl

Run these from a machine that can reach the bridge (ideally the Emby host):

```bash
curl -sS http://127.0.0.1:7777/health
curl -sS http://127.0.0.1:7777/playlist.m3u | head
curl -sS http://127.0.0.1:7777/epg.xml | head
curl -sSI http://127.0.0.1:7777/watch/<stationId>   # expect 302 + Location: …m3u8
```

`<stationId>` is the numeric id on the `channel-id=` attribute / watch path in the M3U.

---

## How it works

1. Load or create `CONFIG_DIR/device.json` (`x-device-id`).
2. `PUT /signin` with Android TV–style client headers; cache bearer token ~4 hours.
3. Build lineup via subscriptions APIs, with plan-manager + recurly packages as fallback; drop DRM sources.
4. Serve M3U with absolute `/watch/…` URLs (honors `X-Forwarded-Host` / `X-Forwarded-Proto`).
5. On watch: call `vapi/asset/v1?channelId=…&type=live`; reject `drmProtected`; otherwise **302** to HLS.
6. On EPG: probe schedule endpoints; map to call signs; cache XMLTV body.

Design notes: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). HTTP details: [docs/API.md](docs/API.md).

---

## Limitations

- **Unofficial API** — Fubo does not document this for third-party use. Endpoints/headers can change without notice.
- **DRM** — Protected packages are skipped; they will not appear or play.
- **IP binding** — Stream URLs are often tied to the requesting public IP. Same host / same egress as Emby is strongly recommended.
- **EPG depth** — If schedule endpoints fail or change, `/epg.xml` still lists channels; programme rows may be empty or sparse.
- **No remux in v1** — Redirect only (no streamlink/ffmpeg MPEG-TS proxy yet; see CHANGELOG Unreleased).
- **Personal use** — Your own paid account only.

---

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| Process exits mentioning `FUBO_USER` / `FUBO_PASS` | Create `.env` from `.env.example`; Compose must load it |
| Empty playlist or `502` on `/playlist.m3u` | Confirm credentials on fubo.tv; check logs for sign-in / API drift |
| Channels import but will not play | Confirm non-DRM; test watch URL in VLC on Emby host; fix shared egress |
| Guide has channels but no programmes | Often expected; use Emby Guide Data Fubo lineup as backup |
| Emby cannot reach bridge | `curl` health from Emby host; fix Docker networking / firewall / published port |
| Playlist URLs say `localhost` but Emby is elsewhere | Fetch playlist via LAN IP Emby can use, or set forwarded host headers |

More: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

---

## Further documentation

| Doc | Description |
| --- | --- |
| [docs/README.md](docs/README.md) | Documentation index |
| [docs/EMBY_SETUP.md](docs/EMBY_SETUP.md) | Detailed Emby Live TV wiring |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Environment variables and runtime files |
| [docs/API.md](docs/API.md) | HTTP API reference |
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
  main.py          # FastAPI routes
  fubo_client.py   # Auth, channels, watch, schedule
  m3u.py           # Playlist builder
  epg.py           # XMLTV builder + cache
  config.py        # Env settings
docs/              # Deep-dive documentation
tests/             # Unit checks (no live Fubo calls)
```

```bash
PYTHONPATH=. python tests/test_builders.py
```

---

## Credits

Auth, lineup, and stream patterns draw on community Fubo bridge projects (Yankees4life, maus-me, jgomez177 / Channels DVR thread) and open-source Python libraries (FastAPI, Uvicorn, HTTPX, python-dotenv). Full attribution: [CREDITS.md](CREDITS.md).
