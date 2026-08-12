"""Environment configuration for the Fubo Emby bridge."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Do not interpolate `$VAR` inside values (passwords often contain `$`).
load_dotenv(interpolate=False)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    fubo_user: str
    fubo_pass: str
    host: str
    port: int
    config_dir: Path
    epg_cache_seconds: int
    epg_days: int
    credentials_source: str


def _strip_wrapping_quotes(value: str) -> tuple[str, bool]:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1], True
    return text, False


def _decode_b64_password(value: str) -> str:
    blob = "".join(value.split())
    if not blob:
        return ""
    try:
        return base64.b64decode(blob, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise RuntimeError("FUBO_PASS_B64 is not valid base64 UTF-8") from exc


def _parse_kv_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value, _ = _strip_wrapping_quotes(value.strip())
        if key:
            parsed[key] = value
    return parsed


def _password_from_mapping(data: dict[str, object]) -> str:
    b64 = str(data.get("FUBO_PASS_B64") or "").strip()
    if b64:
        return _decode_b64_password(b64)
    password = str(data.get("FUBO_PASS") or data.get("password") or "")
    password, _ = _strip_wrapping_quotes(password)
    return password


def _from_mapping(data: dict[str, object]) -> tuple[str, str]:
    user = str(data.get("FUBO_USER") or data.get("email") or "")
    user, _ = _strip_wrapping_quotes(user)
    return user, _password_from_mapping(data)


def password_fingerprint(password: str) -> tuple[str, str]:
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest()[:12]
    classes = "".join(
        flag
        for flag, ok in (
            ("U", any(c.isupper() for c in password)),
            ("L", any(c.islower() for c in password)),
            ("D", any(c.isdigit() for c in password)),
            ("S", any(not c.isalnum() for c in password)),
        )
        if ok
    )
    return digest, classes or "-"


def _load_credentials(config_dir: Path) -> tuple[str, str, str, bool]:
    """Return (user, password, source, quotes_stripped). File beats env (Portainer-safe)."""
    json_path = config_dir / "credentials.json"
    if json_path.is_file():
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Cannot read {json_path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"{json_path} must contain a JSON object")
        user, password = _from_mapping(payload)
        if user and password:
            return user, password, str(json_path), False

    env_path = config_dir / "credentials.env"
    if env_path.is_file():
        try:
            parsed = _parse_kv_file(env_path)
        except OSError as exc:
            raise RuntimeError(f"Cannot read {env_path}: {exc}") from exc
        user, password = _from_mapping(parsed)
        if user and password:
            return user, password, str(env_path), False

    user_file = os.environ.get("FUBO_USER_FILE", "").strip()
    pass_file = os.environ.get("FUBO_PASS_FILE", "").strip()
    if user_file or pass_file:
        if not (user_file and pass_file):
            raise RuntimeError("FUBO_USER_FILE and FUBO_PASS_FILE must be set together")
        try:
            user, user_quoted = _strip_wrapping_quotes(
                Path(user_file).read_text(encoding="utf-8")
            )
            password, pass_quoted = _strip_wrapping_quotes(
                Path(pass_file).read_text(encoding="utf-8")
            )
        except OSError as exc:
            raise RuntimeError(f"Cannot read credential files: {exc}") from exc
        if user and password:
            return user, password, "FUBO_*_FILE", user_quoted or pass_quoted

    user, user_quoted = _strip_wrapping_quotes(os.environ.get("FUBO_USER", ""))
    env_b64 = os.environ.get("FUBO_PASS_B64", "").strip()
    if env_b64:
        password = _decode_b64_password(env_b64)
        return user, password, "environment+FUBO_PASS_B64", user_quoted
    password, pass_quoted = _strip_wrapping_quotes(os.environ.get("FUBO_PASS", ""))
    return user, password, "environment", user_quoted or pass_quoted


def load_settings() -> Settings:
    config_dir = Path(os.environ.get("CONFIG_DIR", "./config")).expanduser()
    config_dir.mkdir(parents=True, exist_ok=True)

    user, password, source, quotes_stripped = _load_credentials(config_dir)
    if not user or not password:
        raise RuntimeError(
            "Set FUBO_USER and FUBO_PASS (or FUBO_PASS_B64), or create "
            "config/credentials.env / credentials.json on the config volume"
        )

    fingerprint, classes = password_fingerprint(password)
    settings = Settings(
        fubo_user=user,
        fubo_pass=password,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "7777")),
        config_dir=config_dir,
        epg_cache_seconds=int(os.environ.get("EPG_CACHE_SECONDS", "3600")),
        epg_days=int(os.environ.get("EPG_DAYS", "2")),
        credentials_source=source,
    )
    logger.info(
        "Fubo credentials source=%s user=%s pass_len=%d pass_fp=%s "
        "pass_classes=%s has_dollar=%s wrapping_quotes_stripped=%s",
        source,
        user,
        len(password),
        fingerprint,
        classes,
        "$" in password,
        quotes_stripped,
    )
    return settings
