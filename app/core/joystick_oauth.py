from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import urllib.parse
import urllib.request
import urllib.error

from app.core.config import Settings

TOKEN_URL = "https://joystick.tv/api/oauth/token"


@dataclass(frozen=True)
class OAuthToken:
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str

    @property
    def expires_at(self):
        """Absolute UTC expiry time computed from `expires_in` seconds."""
        try:
            sec = int(self.expires_in or 0)
        except Exception:
            sec = 0
        if sec <= 0:
            return None
        return datetime.utcnow() + timedelta(seconds=sec)


def _maybe_base64_basic_key(raw: str) -> str:
    """Return the base64 portion for HTTP Basic auth.

    Accepts:
    - base64("client_id:client_secret")  (recommended)
    - "client_id:client_secret"          (common dev mistake)
    - "Basic <base64>"                   (we strip the prefix)
    """
    s = (raw or "").strip()
    if not s:
        return ""
    if s.lower().startswith("basic "):
        s = s[6:].strip()

    # If they pasted client_id:client_secret, encode it.
    if ":" in s and " " not in s:
        return base64.b64encode(s.encode("utf-8")).decode("ascii")
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


def extract_channel_id_from_access_token(access_token: str) -> str | None:
    """Best-effort extraction of channel id from the JWT access_token.

    Joystick docs don't guarantee a `channelId` query param on callback; some installs only return `code` and `state`.
    If Joystick encodes a channel identifier claim in the JWT, this will find it.

    We do NOT verify the JWT signature here; this is only used to populate convenience defaults.
    """
    tok = (access_token or "").strip()
    if not tok or tok.count(".") < 2:
        return None

    try:
        payload_b64 = tok.split(".")[1]
        # base64url padding
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8", errors="replace")
        data = json.loads(payload_json)
    except Exception:
        return None

    # Try common claim names
    for key in ("channelId", "channel_id", "channel", "room_id", "roomId"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None
