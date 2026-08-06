# Fubo → Emby Bridge

Python sidecar that signs into your Fubo account and serves Emby-ready Live TV feeds.

| Endpoint | Emby use |
| --- | --- |
| `http://<host>:7777/playlist.m3u` | Live TV → M3U Tuner |
| `http://<host>:7777/epg.xml` | Live TV → XMLTV guide |
| `http://<host>:7777/watch/<id>` | Per-channel HLS redirect |

This is **not** an Emby .NET plugin. Emby Premiere Live TV already supports M3U + XMLTV natively.

**Current version:** 1.0.0 — see [CHANGELOG.md](CHANGELOG.md).

## Documentation

| Doc | Description |
| --- | --- |
| [docs/README.md](docs/README.md) | Documentation index |
| [docs/EMBY_SETUP.md](docs/EMBY_SETUP.md) | Emby Live TV setup |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Environment variables |
| [docs/API.md](docs/API.md) | HTTP API reference |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Design and data flow |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development guidelines |
| [SECURITY.md](SECURITY.md) | Credentials and threat model |
| [CREDITS.md](CREDITS.md) | Attribution for prior art and dependencies |
| [CONTEXT.md](CONTEXT.md) | Durable project context for humans/agents |
| [WORKING_MEMORY.md](WORKING_MEMORY.md) | Current focus, blockers, next actions |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

## Requirements

- A valid Fubo subscription (your own credentials)
- Emby Server with Premiere (Live TV)
- Docker (recommended) or Python 3.11+

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env and set FUBO_USER / FUBO_PASS

docker compose up -d --build
```

Open `http://localhost:7777/` for copy-paste URLs.

## Quick start (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env

uvicorn app.main:app --host 0.0.0.0 --port 7777
```

## Emby setup (summary)

1. **Dashboard → Live TV → Tuner Devices → +** → **M3U Tuner**
2. URL: `http://<bridge-host>:7777/playlist.m3u`
3. **TV Guide Data Providers → +** → **XMLTV**
4. URL: `http://<bridge-host>:7777/epg.xml`
5. Refresh guide / map any unmatched channels

Full walkthrough: [docs/EMBY_SETUP.md](docs/EMBY_SETUP.md).

`tvg-id` in the playlist matches XMLTV `channel id` (Fubo call sign) so Emby can auto-map when possible.

## Environment

| Variable | Default | Description |
| --- | --- | --- |
| `FUBO_USER` | _(required)_ | Fubo account email |
| `FUBO_PASS` | _(required)_ | Fubo account password |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `7777` | Listen port |
| `CONFIG_DIR` | `./config` | Device id + cache directory |
| `EPG_CACHE_SECONDS` | `3600` | How long to reuse generated `epg.xml` |
| `EPG_DAYS` | `2` | Guide window when schedule data is available |

Details: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## How it works

1. Authenticates to `api.fubo.tv` and caches a bearer token
2. Builds your subscribed channel lineup (skips known DRM packages)
3. Serves an M3U whose stream URLs point at this bridge
4. On tune, resolves a live HLS URL and **302 redirects** to it
5. Builds XMLTV from Fubo schedule endpoints when available (falls back to channel list only)

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Limitations

- **Unofficial API** — Fubo does not document this for third-party use. Endpoints/headers can change.
- **DRM** — Disney, Starz, Showtime, Max/HBO, and similar protected channels are skipped. They will not play.
- **IP binding** — Stream URLs are often tied to the IP that requested them. Run this bridge on the **same host / public egress** as Emby when possible.
- **EPG depth** — If Fubo’s schedule endpoints are unavailable or change, `/epg.xml` still lists channels so Emby mapping works; programme rows may be sparse. You can also use Emby Guide Data’s Fubo lineup as a secondary guide source and map manually.
- Personal use with your own paid account only. Respect Fubo’s terms of service.

More help: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Development layout

```text
app/
  main.py          # FastAPI routes
  fubo_client.py   # Auth, channels, watch, schedule
  m3u.py           # Playlist builder
  epg.py           # XMLTV builder + cache
  config.py        # Env settings
docs/              # Full documentation
tests/             # Unit checks (no live Fubo calls)
```

```bash
PYTHONPATH=. python tests/test_builders.py
```

## Credits

Auth, lineup, and stream patterns draw on community Fubo bridge projects (Yankees4life, maus-me, jgomez177 / Channels DVR thread) and open-source Python libraries (FastAPI, Uvicorn, HTTPX, python-dotenv). Full attribution: [CREDITS.md](CREDITS.md).
