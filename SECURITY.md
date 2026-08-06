# Security

## Credentials

- Store Fubo credentials only in `.env` or your orchestrator’s secret store
- Never commit `.env`, `config/device.json` with production tokens, or logs containing access tokens
- `.gitignore` excludes `.env` and `config/` runtime files (keeps `config/.gitkeep`)

## Threat model (personal LAN tool)

This bridge is intended for a trusted home network:

| Risk | Mitigation |
| --- | --- |
| Credential leakage via git | Use `.env` locally; never commit secrets |
| Open HTTP on the LAN | Bind to trusted interfaces; put behind a reverse proxy / VPN if exposed remotely |
| Token theft from memory/logs | Tokens live in process memory only; avoid debug-logging Authorization headers |
| Unofficial API breakage | Treat as best-effort; pin your own deploy and watch Fubo client changes |

## Reporting issues

If you discover a vulnerability in **this project’s code** (not Fubo’s platform), open a private report or issue without including live credentials or session tokens.

## Unsupported

- Circumventing DRM
- Sharing accounts or redistributing streams
- Hardening for public internet exposure without additional controls
