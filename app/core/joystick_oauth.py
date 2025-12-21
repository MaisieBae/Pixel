from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.core.config import Settings


TOKEN_URL = "https://joystick.tv/api/oauth/token"


@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    refresh_token: str
    expires_at: Optional[datetime]
    raw: Dict[str, Any]


def _post_form(url: str, data: dict, headers: dict | None = None) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def exchange_code_for_token(settings: Settings, code: str) -> TokenResponse:
    if not settings.JOYSTICK_CLIENT_ID or not settings.JOYSTICK_CLIENT_SECRET:
        raise RuntimeError("Missing JOYSTICK_CLIENT_ID / JOYSTICK_CLIENT_SECRET")

    payload = {
        "client_id": settings.JOYSTICK_CLIENT_ID,
        "client_secret": settings.JOYSTICK_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
    }
    data = _post_form(TOKEN_URL, payload)
    return _parse_token_response(data)


def refresh_access_token(settings: Settings, refresh_token: str) -> TokenResponse:
    if not settings.JOYSTICK_CLIENT_ID or not settings.JOYSTICK_CLIENT_SECRET:
        raise RuntimeError("Missing JOYSTICK_CLIENT_ID / JOYSTICK_CLIENT_SECRET")

    payload = {
        "client_id": settings.JOYSTICK_CLIENT_ID,
        "client_secret": settings.JOYSTICK_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    data = _post_form(TOKEN_URL, payload)
    return _parse_token_response(data)


def _parse_token_response(data: dict) -> TokenResponse:
    access = str(data.get("access_token", "") or "")
    refresh = str(data.get("refresh_token", "") or "")
    expires_in = data.get("expires_in", None)
    expires_at: Optional[datetime] = None
    try:
        if expires_in is not None:
            sec = int(expires_in)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=sec)
    except Exception:
        expires_at = None

    return TokenResponse(access_token=access, refresh_token=refresh, expires_at=expires_at, raw=data)
