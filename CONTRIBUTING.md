# Contributing

Thanks for improving **fbtv** (Fubo → Emby & Jellyfin bridge). Public repo: [cbodden/fbtv](https://github.com/cbodden/fbtv). This project is a personal-use sidecar around Fubo’s unofficial API — keep changes focused and defensive.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# set FUBO_USER / FUBO_PASS (or FUBO_PASS_B64) for live API work
```

Run the server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 7777 --reload
```

Or with Compose (pulls `ghcr.io/cbodden/fbtv:latest` built from **`main`**; no project `.env` / `env_file`):

```bash
# alphanumeric:
export FUBO_USER='…'
export FUBO_PASS='…'
docker compose up -d

# or special characters — file on the config volume:
#   FUBO_USER=…
#   FUBO_PASS_B64=…
docker compose logs -f fbtv
```

Run builder tests (no Fubo credentials required):

```bash
PYTHONPATH=. python tests/test_builders.py
```

## Guidelines

- Prefer small, focused changes over broad refactors
- Do not commit `.env`, `config/credentials.*`, tokens, or real credentials
- Match existing style in `app/` (type hints, dataclasses, clear error messages)
- When Fubo endpoints or client headers change, update `app/fubo_client.py` and note it in `CHANGELOG.md`
- When status/metrics fields change, update `docs/STATUS.md` and `docs/API.md`
- Document user-facing behavior in `README.md` and the relevant file under `docs/`
- Treat **Emby and Jellyfin** as equal first-class targets in copy (avoid Emby-only framing)
- Keep the short name **`fbtv`** for the GitHub repo, Compose service, and GHCR package (`ghcr.io/cbodden/fbtv`); CI on `main` lives in `.github/workflows/docker.yml`
- Credit new prior art or dependencies in `CREDITS.md`
- Keep `CONTEXT.md` accurate for lasting decisions; refresh `WORKING_MEMORY.md` for current focus/blockers

## Pull request checklist

- [ ] `PYTHONPATH=. python tests/test_builders.py` passes
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Docs updated if endpoints, env vars, credentials, status/metrics, naming, or Emby/Jellyfin setup steps changed
- [ ] `CREDITS.md` updated if new dependencies or borrowed approaches were introduced
- [ ] No secrets in the diff

## Scope boundaries

Out of scope unless explicitly agreed:

- Native Emby .NET or Jellyfin plugins
- DRM decryption
- Redistributing Fubo content or credentials
