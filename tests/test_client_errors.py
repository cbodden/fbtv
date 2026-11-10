"""Regression tests: timestamp parsing, transport/JSON errors, 401 re-auth, sign-in cool-down."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from app.config import password_fingerprint
from app.fubo.client import REAUTH_MIN_TOKEN_AGE_SECONDS, FuboClient
from app.fubo.models import FuboError
from app.fubo.schedule import ScheduleMixin
from app.fubo.session import AuthSession, load_session, save_session
from tests.test_auth_session import _settings


def _client(tmp_path: Path, handler, *, token: str | None = None, token_age: float = 0.0) -> FuboClient:
    settings = _settings(tmp_path, cooldown=1800)
    if token:
        save_session(
            tmp_path,
            AuthSession(
                access_token=token,
                token_at=time.time() - token_age,
                expires_in=4 * 3600,
                user=settings.fubo_user,
                pass_fp=password_fingerprint(settings.fubo_pass)[0],
            ),
        )
    client = FuboClient(settings)
    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(handler))
    return client


# --- 1. digit-string timestamps ---------------------------------------------


def test_parse_dt_accepts_digit_string_epoch_ms() -> None:
    expected = datetime(2024, 11, 10, 16, 0, tzinfo=timezone.utc)
    assert ScheduleMixin._parse_dt("1731254400000") == expected
    assert ScheduleMixin._parse_dt("1731254400") == expected


# --- 2. transport / JSON errors become FuboError ------------------------------


def test_api_get_wraps_timeout_as_fubo_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = _client(tmp_path, handler, token="tok")
    try:
        with pytest.raises(FuboError, match="request failed"):
            client.api_get("epg")
    finally:
        client.close()


def test_api_get_wraps_invalid_json_as_fubo_error(tmp_path: Path) -> None:
    client = _client(tmp_path, lambda _r: httpx.Response(200, text="<html>"), token="tok")
    try:
        with pytest.raises(FuboError, match="invalid JSON"):
            client.api_get("epg")
    finally:
        client.close()


def test_signin_transport_error_is_fubo_error_without_cooldown(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    client = _client(tmp_path, handler)
    try:
        with pytest.raises(FuboError, match="Sign-in request failed"):
            client.token()
        assert not load_session(tmp_path).in_cooldown(time.time())
    finally:
        client.close()


def test_schedule_survives_endpoint_timeouts(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = _client(tmp_path, handler, token="tok")
    try:
        assert client.schedule([], days=1) == []
    finally:
        client.close()


# --- 3. 401 drops a revoked token and signs in once ---------------------------


def test_api_get_reauths_once_on_401(tmp_path: Path) -> None:
    calls = {"signin": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/signin":
            calls["signin"] += 1
            return httpx.Response(200, json={"access_token": "fresh", "expires_in": 3600})
        if request.headers.get("authorization") == "Bearer fresh":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(401, json={"error": "expired"})

    client = _client(
        tmp_path, handler, token="revoked", token_age=REAUTH_MIN_TOKEN_AGE_SECONDS + 60
    )
    try:
        assert client.api_get("user") == {"ok": True}
        assert calls["signin"] == 1
        assert load_session(tmp_path).access_token == "fresh"
    finally:
        client.close()


def test_api_get_does_not_reauth_for_fresh_token(tmp_path: Path) -> None:
    calls = {"signin": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/signin":
            calls["signin"] += 1
            return httpx.Response(200, json={"access_token": "fresh"})
        return httpx.Response(401, json={"error": "nope"})

    client = _client(tmp_path, handler, token="new", token_age=10)
    try:
        with pytest.raises(FuboError, match="401"):
            client.api_get("user")
        assert calls["signin"] == 0
    finally:
        client.close()


# --- 4. 200 sign-in without a token starts the cool-down ----------------------


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"no_token": True}),
        httpx.Response(200, text="not json"),
    ],
)
def test_signin_without_token_starts_cooldown(tmp_path: Path, response: httpx.Response) -> None:
    calls = {"signin": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["signin"] += 1
        return response

    client = _client(tmp_path, handler)
    try:
        with pytest.raises(FuboError, match="missing access_token"):
            client.token()
        with pytest.raises(FuboError, match="cool-down"):
            client.token()
        assert calls["signin"] == 1
        assert load_session(tmp_path).in_cooldown(time.time())
    finally:
        client.close()
