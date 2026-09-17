"""Persisted Fubo auth session + sign-in cool-down (lockout spiral guard)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SESSION_FILENAME = "session.json"
DEFAULT_EXPIRES_IN = 4 * 60 * 60
# Renew a few minutes early so Emby polls don't race the hard expiry.
TOKEN_SKEW_SECONDS = 300


@dataclass
class AuthSession:
    access_token: str | None = None
    refresh_token: str | None = None
    token_at: float = 0.0
    expires_in: int = DEFAULT_EXPIRES_IN
    user: str = ""
    pass_fp: str = ""
    cooldown_until: float | None = None
    last_error: str | None = None
    last_error_at: float | None = None

    def token_ttl_remaining(self, now: float) -> float:
        if not self.access_token or self.token_at <= 0:
            return 0.0
        return (self.token_at + max(0, self.expires_in)) - now

    def token_valid(self, now: float, *, skew_seconds: int = TOKEN_SKEW_SECONDS) -> bool:
        return self.token_ttl_remaining(now) > max(0, skew_seconds)

    def in_cooldown(self, now: float) -> bool:
        return self.cooldown_until is not None and now < self.cooldown_until

    def cooldown_remaining(self, now: float) -> int:
        if not self.in_cooldown(now):
            return 0
        assert self.cooldown_until is not None
        return max(0, int(self.cooldown_until - now))


def session_path(config_dir: Path) -> Path:
    return config_dir / SESSION_FILENAME


def load_session(config_dir: Path) -> AuthSession:
    path = session_path(config_dir)
    if not path.is_file():
        return AuthSession()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Ignoring unreadable auth session %s: %s", path, exc)
        return AuthSession()
    if not isinstance(raw, dict):
        return AuthSession()
    return AuthSession(
        access_token=_opt_str(raw.get("access_token")),
        refresh_token=_opt_str(raw.get("refresh_token")),
        token_at=_opt_float(raw.get("token_at"), 0.0),
        expires_in=max(0, int(_opt_float(raw.get("expires_in"), DEFAULT_EXPIRES_IN))),
        user=str(raw.get("user") or ""),
        pass_fp=str(raw.get("pass_fp") or ""),
        cooldown_until=_opt_float_or_none(raw.get("cooldown_until")),
        last_error=_opt_str(raw.get("last_error")),
        last_error_at=_opt_float_or_none(raw.get("last_error_at")),
    )


def save_session(config_dir: Path, session: AuthSession) -> None:
    path = session_path(config_dir)
    payload = asdict(session)
    # Never write empty file noise; always atomic-ish replace.
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        logger.warning("Could not persist auth session %s: %s", path, exc)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def clear_access_token(session: AuthSession) -> AuthSession:
    session.access_token = None
    session.refresh_token = None
    session.token_at = 0.0
    return session


def apply_signin_success(
    session: AuthSession,
    *,
    payload: dict[str, Any],
    user: str,
    pass_fp: str,
    now: float,
) -> AuthSession:
    token = payload.get("access_token")
    if not token:
        raise ValueError("missing access_token")
    expires_in = payload.get("expires_in")
    try:
        expires_val = int(expires_in) if expires_in is not None else DEFAULT_EXPIRES_IN
    except (TypeError, ValueError):
        expires_val = DEFAULT_EXPIRES_IN
    if expires_val <= 0:
        expires_val = DEFAULT_EXPIRES_IN

    session.access_token = str(token)
    refresh = payload.get("refresh_token")
    session.refresh_token = str(refresh) if refresh else None
    session.token_at = now
    session.expires_in = expires_val
    session.user = user
    session.pass_fp = pass_fp
    session.cooldown_until = None
    session.last_error = None
    session.last_error_at = None
    return session


def apply_signin_failure(
    session: AuthSession,
    *,
    error: str,
    now: float,
    cooldown_seconds: int,
) -> AuthSession:
    session = clear_access_token(session)
    cool = max(0, int(cooldown_seconds))
    session.cooldown_until = now + cool if cool > 0 else None
    session.last_error = error[:500]
    session.last_error_at = now
    return session


def credentials_match(session: AuthSession, *, user: str, pass_fp: str) -> bool:
    return bool(session.user) and session.user == user and session.pass_fp == pass_fp


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _opt_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _opt_float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
