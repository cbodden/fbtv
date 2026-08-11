# Security

Public repository: [cbodden/fbtv](https://github.com/cbodden/fbtv). Treat the tree as visible to anyone — never commit secrets.

## Credentials

- Store Fubo credentials only in `.env` or your orchestrator’s secret store
- Never commit `.env`, `config/device.json` with production tokens, or logs containing access tokens
- `.gitignore` excludes `.env` and `config/` runtime files (keeps `config/.gitkeep`)

## Threat model (personal LAN tool)

This bridge is intended for a trusted home network:

| Risk | Mitigation |
| --- | --- |
| Credential leakage via git | Use `.env` locally; never commit secrets (repo is public) |
| Open HTTP on the LAN | Bind to trusted interfaces; put behind a reverse proxy / VPN if exposed remotely |
| Token theft from memory/logs | Tokens live in process memory only; avoid debug-logging Authorization headers |
| Status / metrics exposure | `/`, `/status`, `/status.json`, and `/metrics` are unauthenticated and show operational counts (not passwords or bearer tokens); do not expose them on the public internet without additional controls |
| Unofficial API breakage | Treat as best-effort; pin your own deploy and watch Fubo client changes |
| Public container image | `ghcr.io/cbodden/fbtv` has no credentials baked in; still keep runtime `.env` private |

## Reporting issues

If you discover a vulnerability in **this project’s code** (not Fubo’s platform), open a private report or issue without including live credentials or session tokens.

## Unsupported

- Circumventing DRM
- Sharing accounts or redistributing streams
- Hardening for public internet exposure without additional controls
