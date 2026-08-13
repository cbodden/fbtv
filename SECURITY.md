# Security

Public repository: [cbodden/fbtv](https://github.com/cbodden/fbtv). Treat the tree as visible to anyone — never commit secrets.

## Credentials

- Store Fubo credentials in `config/credentials.env` (`FUBO_PASS_B64` preferred), `config/credentials.json`, process env, or a local-Python `.env` — never in the image
- Never commit `.env`, `config/credentials.*`, `config/device.json`, `config/drm_skipped.json`, `config/drm_overrides.json` (if it encodes your private lineup choices), or logs containing access tokens
- `.gitignore` excludes `.env` and `config/` runtime files (keeps `config/.gitkeep`)
- Compose does **not** use `env_file`; Portainer should use the credentials file (base64 the password if it contains `$`)
- Logs may include `pass_fp` (SHA-256 prefix) and `pass_len`, never the password itself

## Threat model (personal LAN tool)

This bridge is intended for a trusted home network:

| Risk | Mitigation |
| --- | --- |
| Credential leakage via git | Prefer `config/credentials.env` on the volume (gitignored); never commit secrets (repo is public) |
| Open HTTP on the LAN | Bind to trusted interfaces; put behind a reverse proxy / VPN if exposed remotely |
| Token theft from memory/logs | Tokens live in process memory only; avoid debug-logging Authorization headers |
| Status / metrics exposure | `/`, `/status`, `/status.json`, `/metrics` are unauthenticated and show operational counts (not passwords or bearer tokens); `/admin/drm-scan` is open unless `ADMIN_TOKEN` is set — do not expose them on the public internet without additional controls |
| Admin DRM scan | Set `ADMIN_TOKEN` and call with `Authorization: Bearer …` or `X-Admin-Token` if the bridge is reachable beyond a trusted LAN |
| Unofficial API breakage | Treat as best-effort; pin your own deploy and watch Fubo client changes |
| Public container image | `ghcr.io/cbodden/fbtv` has no credentials baked in; inject secrets at runtime only |

## Reporting issues

If you discover a vulnerability in **this project’s code** (not Fubo’s platform), open a private report or issue without including live credentials or session tokens.

## Unsupported

- Circumventing DRM
- Sharing accounts or redistributing streams
- Hardening for public internet exposure without additional controls
