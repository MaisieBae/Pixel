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
    token_type: str
    refresh_token: str
    expires_in: int  # seconds (per docs)
    expires_at: datetime


def _basic_headers(settings: Settings) -> Dict[str, str]:
    if not settings.JOYSTICK_BASIC_KEY:
        raise RuntimeError("Missing JOYSTICK_BASIC_KEY (Authorization: Basic ...)")
    return {
        "Authorization": f"Basic {settings.JOYSTICK_BASIC_KEY}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }


def _post_form(url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _parse_token_response(data: Dict[str, Any]) -> TokenResponse:
    # Docs show:
    #  {
    #    "access_token": "JSON_WEB_TOKEN",
    #    "token_type": "Bearer",
    #    "expires_in": 1682098467,
    #    "refresh_token": "REFRESH_TOKEN"
    #  }
    access_token = str(data.get("access_token", "") or "")
    token_type = str(data.get("token_type", "") or "")
    refresh_token = str(data.get("refresh_token", "") or "")
    expires_in = int(data.get("expires_in", 0) or 0)

    if not access_token or not refresh_token:
        raise RuntimeError(f"Invalid token response: {data}")

    # Joystick's docs show expires_in as a large number in examples; treat it as seconds.
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(0, expires_in))
    return TokenResponse(
        access_token=access_token,
        token_type=token_type or "Bearer",
        refresh_token=refresh_token,
        expires_in=expires_in,
        expires_at=expires_at,
    )


def exchange_code_for_token(settings: Settings, code: str) -> TokenResponse:
    if not settings.JOYSTICK_CLIENT_ID or not settings.JOYSTICK_CLIENT_SECRET:
        raise RuntimeError("Missing JOYSTICK_CLIENT_ID / JOYSTICK_CLIENT_SECRET")

    # Docs: redirect_uri is "not currently used, but may be used in the future"
    # We'll send it if configured (otherwise "unused" keeps parity with docs examples).
    redirect_uri = (settings.JOYSTICK_REDIRECT_URI or "").strip() or "unused"

    payload = {
        "redirect_uri": redirect_uri,
        "code": code,
        "grant_type": "authorization_code",
    }

    data = _post_form(TOKEN_URL, payload, headers=_basic_headers(settings))
    return _parse_token_response(data)


def refresh_access_token(settings: Settings, refresh_token: str) -> TokenResponse:
    if not settings.JOYSTICK_CLIENT_ID or not settings.JOYSTICK_CLIENT_SECRET:
        raise RuntimeError("Missing JOYSTICK_CLIENT_ID / JOYSTICK_CLIENT_SECRET")

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    data = _post_form(TOKEN_URL, payload, headers=_basic_headers(settings))
    return _parse_token_response(data)
