from __future__ import annotations

import base64
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings

TOKEN_URL = "https://joystick.tv/api/oauth/token"


@dataclass(frozen=True)
class OAuthToken:
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str


def _maybe_base64_basic_key(raw: str) -> str:
    """Accept either:
    - base64("client_id:client_secret")  (recommended, per Joystick docs)
    - "client_id:client_secret"          (common dev mistake)
    - already prefixed "Basic XXX"       (we'll strip it)

    Return just the base64 part (no 'Basic ' prefix).
    """
    s = (raw or "").strip()
    if not s:
        return ""

    if s.lower().startswith("basic "):
        s = s[6:].strip()

    # If they pasted client_id:client_secret, encode it.
    if ":" in s and " " not in s:
        return base64.b64encode(s.encode("utf-8")).decode("ascii")

    # Otherwise assume it's already base64
    return s


def _basic_headers(settings: Settings) -> dict[str, str]:
    basic = _maybe_base64_basic_key(getattr(settings, "JOYSTICK_BASIC_KEY", "") or "")
    if not basic:
        raise ValueError("JOYSTICK_BASIC_KEY is missing (must be base64(client_id:client_secret))")

    return {
        "Authorization": f"Basic {basic}",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }


def _post_form(url: str, params: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    qs = urllib.parse.urlencode({k: str(v) for k, v in params.items() if v is not None})
    req = urllib.request.Request(
        url=f"{url}?{qs}",
        method="POST",
        headers=headers,
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if not body:
                return {}
            return json.loads(body)
    except urllib.error.HTTPError as e:
        # Very important: surface Joystick's response body, otherwise we’re blind.
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        raise RuntimeError(f"Joystick token endpoint HTTP {e.code}: {err_body or e.reason}") from e


def exchange_code_for_token(settings: Settings, code: str, *, state: str | None = None) -> OAuthToken:
    """Exchange authorization code for access+refresh tokens.

    Per Joystick docs:
      POST https://joystick.tv/api/oauth/token?redirect_uri=...&code=...&grant_type=authorization_code
      Authorization: Basic base64(client_id:client_secret)
    """
    payload = {
        "redirect_uri": getattr(settings, "JOYSTICK_REDIRECT_URI", "") or "unused",
        "code": code,
        "grant_type": "authorization_code",
    }

    headers = _basic_headers(settings)

    # Optional: pass arbitrary state through header if you want (Joystick supports X-JOYSTICK-STATE).
    if state:
        headers["X-JOYSTICK-STATE"] = str(state)

    data = _post_form(TOKEN_URL, payload, headers=headers)

    return OAuthToken(
        access_token=str(data.get("access_token", "")),
        token_type=str(data.get("token_type", "Bearer")),
        expires_in=int(data.get("expires_in", 0) or 0),
        refresh_token=str(data.get("refresh_token", "")),
    )


def refresh_access_token(settings: Settings, refresh_token: str, *, state: str | None = None) -> OAuthToken:
    payload = {
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    headers = _basic_headers(settings)
    if state:
        headers["X-JOYSTICK-STATE"] = str(state)

    data = _post_form(TOKEN_URL, payload, headers=headers)

    return OAuthToken(
        access_token=str(data.get("access_token", "")),
        token_type=str(data.get("token_type", "Bearer")),
        expires_in=int(data.get("expires_in", 0) or 0),
        refresh_token=str(data.get("refresh_token", "")),
    )
