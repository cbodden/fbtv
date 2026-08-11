# Contributing

Thanks for improving the Fubo → Emby & Jellyfin bridge. This project is a personal-use sidecar around Fubo’s unofficial API — keep changes focused and defensive.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# set FUBO_USER / FUBO_PASS for live API work
```

Run the server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 7777 --reload
```

Run builder tests (no Fubo credentials required):

```bash
PYTHONPATH=. python tests/test_builders.py
```

## Guidelines

- Prefer small, focused changes over broad refactors
- Do not commit `.env`, tokens, or real credentials
- Match existing style in `app/` (type hints, dataclasses, clear error messages)
- When Fubo endpoints change, update `app/fubo_client.py` and note it in `CHANGELOG.md`
- Document user-facing behavior in `README.md` and the relevant file under `docs/`
- Treat **Emby and Jellyfin** as equal first-class targets in copy (avoid Emby-only framing)
- Credit new prior art or dependencies in `CREDITS.md`
- Keep `CONTEXT.md` accurate for lasting decisions; refresh `WORKING_MEMORY.md` for current focus/blockers

## Pull request checklist

- [ ] `PYTHONPATH=. python tests/test_builders.py` passes
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Docs updated if endpoints, env vars, or Emby/Jellyfin setup steps changed
- [ ] `CREDITS.md` updated if new dependencies or borrowed approaches were introduced
- [ ] No secrets in the diff

## Scope boundaries

Out of scope unless explicitly agreed:

- Native Emby .NET or Jellyfin plugins
- DRM decryption
- Redistributing Fubo content or credentials
