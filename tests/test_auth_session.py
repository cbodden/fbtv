"""Auth session persistence and sign-in cool-down."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from app.config import Settings, password_fingerprint
from app.fubo.client import FuboClient
from app.fubo.models import FuboError
from app.fubo.session import (
    AuthSession,
    apply_signin_failure,
    apply_signin_success,
    credentials_match,
    load_session,
    save_session,
)


def _settings(config_dir: Path, *, cooldown: int = 1800) -> Settings:
    return Settings(
        fubo_user="u@example.com",
        fubo_pass="secret$1",
        host="0.0.0.0",
        port=7777,
        config_dir=config_dir,
        epg_cache_seconds=3600,
        epg_empty_cache_seconds=120,
        epg_days=2,
        credentials_source="test",
        drm_scan_on_start=False,
        drm_scan_concurrency=1,
        drm_scan_delay_ms=0,
        drm_scan_max_age_hours=24,
        drm_scan_interval_hours=0,
        stream_proxy=False,
        stream_proxy_max=3,
        ffmpeg_path="ffmpeg",
        admin_token="",
        auth_cooldown_seconds=cooldown,
    )


def test_session_save_load_roundtrip(tmp_path: Path) -> None:
    fp = password_fingerprint("secret$1")[0]
    session = AuthSession(
        access_token="tok",
        refresh_token=None,
        token_at=time.time(),
        expires_in=3600,
        user="u@example.com",
        pass_fp=fp,
    )
    save_session(tmp_path, session)
    loaded = load_session(tmp_path)
    assert loaded.access_token == "tok"
    assert loaded.user == "u@example.com"
    assert loaded.pass_fp == fp
    assert loaded.token_valid(time.time())
    assert credentials_match(loaded, user="u@example.com", pass_fp=fp)


def test_apply_signin_failure_sets_cooldown() -> None:
    now = 1_000_000.0
    session = apply_signin_failure(
        AuthSession(access_token="old"),
        error="401: nope",
        now=now,
        cooldown_seconds=600,
    )
    assert session.access_token is None
    assert session.in_cooldown(now + 10)
    assert not session.in_cooldown(now + 601)
    assert session.cooldown_remaining(now) == 600


def test_apply_signin_success_clears_cooldown() -> None:
    now = 1_000_000.0
    session = AuthSession(cooldown_until=now + 999, last_error="x")
    session = apply_signin_success(
        session,
        payload={"access_token": "abc", "expires_in": 120},
        user="u@example.com",
        pass_fp="fp",
        now=now,
    )
    assert session.access_token == "abc"
    assert session.expires_in == 120
    assert session.cooldown_until is None
    assert session.last_error is None


def test_client_restores_persisted_session(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    fp = password_fingerprint(settings.fubo_pass)[0]
    save_session(
        tmp_path,
        AuthSession(
            access_token="persisted-token",
            token_at=time.time(),
            expires_in=3600,
            user=settings.fubo_user,
            pass_fp=fp,
        ),
    )
    client = FuboClient(settings)
    try:
        assert client.token() == "persisted-token"
        # No HTTP call should be needed.
        assert client._http is not None
    finally:
        client.close()


def test_client_cooldown_blocks_password_retry(tmp_path: Path) -> None:
    settings = _settings(tmp_path, cooldown=1800)
    client = FuboClient(settings)

    def fake_put(*_args, **_kwargs):
        response = MagicMock()
        response.status_code = 401
        response.text = '{"error":{"code":"INVALID_USERNAME_PASSWORD"}}'
        return response

    client._http.put = fake_put  # type: ignore[method-assign]
    try:
        with pytest.raises(FuboError, match="Sign-in failed \\(401\\)"):
            client.token()
        # Second call must not hit network — cool-down.
        calls = {"n": 0}

        def boom(*_a, **_k):
            calls["n"] += 1
            raise AssertionError("password sign-in should be cool-down blocked")

        client._http.put = boom  # type: ignore[method-assign]
        with pytest.raises(FuboError, match="cool-down"):
            client.token()
        assert calls["n"] == 0

        disk = load_session(tmp_path)
        assert disk.in_cooldown(time.time())
        assert disk.access_token is None
        stats = client.runtime_stats()
        assert stats["auth_cooldown_active"] is True
        assert stats["auth_cooldown_remaining_seconds"]
    finally:
        client.close()


def test_client_persists_successful_signin(tmp_path: Path) -> None:
    settings = _settings(tmp_path, cooldown=60)
    client = FuboClient(settings)

    def fake_put(*_args, **_kwargs):
        return httpx.Response(
            200,
            json={"access_token": "fresh-token", "expires_in": 7200},
        )

    client._http.put = fake_put  # type: ignore[method-assign]
    try:
        assert client.token() == "fresh-token"
        disk = load_session(tmp_path)
        assert disk.access_token == "fresh-token"
        assert disk.expires_in == 7200
        assert disk.user == settings.fubo_user
        path = tmp_path / "session.json"
        assert path.is_file()
        raw = json.loads(path.read_text())
        assert raw["access_token"] == "fresh-token"
    finally:
        client.close()
