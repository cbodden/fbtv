"""Environment configuration for the Fubo Emby bridge."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    fubo_user: str
    fubo_pass: str
    host: str
    port: int
    config_dir: Path
    epg_cache_seconds: int
    epg_days: int


def load_settings() -> Settings:
    user = os.environ.get("FUBO_USER", "").strip()
    password = os.environ.get("FUBO_PASS", "").strip()
    if not user or not password:
        raise RuntimeError("FUBO_USER and FUBO_PASS must be set")

    config_dir = Path(os.environ.get("CONFIG_DIR", "./config")).expanduser()
    config_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        fubo_user=user,
        fubo_pass=password,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "7777")),
        config_dir=config_dir,
        epg_cache_seconds=int(os.environ.get("EPG_CACHE_SECONDS", "3600")),
        epg_days=int(os.environ.get("EPG_DAYS", "2")),
    )
