from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

import websockets
from websockets import WebSocketClientProtocol
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.models import JoystickInstall


# Types for callbacks
OnChat = Callable[[str, str], Awaitable[None]]              # (user, text)
OnFollow = Callable[[str], Awaitable[None]]                 # (user)
OnSub = Callable[[str, int], Awaitable[None]]               # (user, months)
OnTip = Callable[[str, int], Awaitable[None]]               # (user, tokens)
OnDropIn = Callable[[str], Awaitable[None]]                 # (user)


@dataclass
class JoystickCallbacks:
    on_chat: Optional[OnChat] = None
    on_follow: Optional[OnFollow] = None
    on_sub: Optional[OnSub] = None
    on_tip: Optional[OnTip] = None
    on_dropin: Optional[OnDropIn] = None


class JoystickClient:
    """Joystick gateway client (ActionCable).

    - Connects to wss://joystick.tv/cable?token=<BASIC_KEY>
    - Subscribes to GatewayChannel
    - Dispatches incoming events to callbacks
    - Can send chat messages and whispers via ActionCable "message" commands

    Notes:
    - Incoming events include a `channelId`. We keep the callbacks as (user,text,etc) for stability.
      For sending messages, we pick a channelId via:
        1) explicit parameter,
        2) settings default channel id (stored outside here),
        3) first installed channel in DB.
    """

    def __init__(self, basic_key: str, *, default_channel_id: str = "") -> None:
        self.basic_key = (basic_key or "").strip()
        self.default_channel_id = (default_channel_id or "").strip()

        self._cbs: JoystickCallbacks = JoystickCallbacks()
        self._stop = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

        self._ws: Optional[WebSocketClientProtocol] = None
        self._last_seen_channel_id: Optional[str] = None

        # Debug logging toggle. Keep default False to avoid noisy logs.
        # You can enable by setting JOYSTICK_DEBUG=1 and wiring it through Settings if desired.
        self.debug: bool = False

        # reconnect backoff
        self._backoff_s = 1.0

    def set_callbacks(self, cbs: JoystickCallbacks) -> None:
        self._cbs = cbs

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
            self._task = None

    # --------------------------
    # Outgoing (send to Joystick)
    # --------------------------
    async def send_message(self, text: str, *, channel_id: str | None = None) -> None:
        cid = await self._resolve_channel_id(channel_id)
        if not cid:
            # No installed channel yet; keep the bot stable.
            print("[joystick] No channel_id available for send_message")
            return
        await self._send_action(
            {
                "action": "send_message",
                "text": str(text),
                "channelId": cid,
            }
        )

    async def send_whisper(self, username: str, text: str, *, channel_id: str | None = None) -> None:
        cid = await self._resolve_channel_id(channel_id)
        if not cid:
            print("[joystick] No channel_id available for send_whisper")
            return
        await self._send_action(
            {
                "action": "send_whisper",
                "username": str(username),
                "text": str(text),
                "channelId": cid,
            }
        )

    async def send_chat(self, text: str) -> None:
        """Backward-compatible helper used by older code paths."""
        await self.send_message(text)

    async def _resolve_channel_id(self, explicit: str | None) -> str:
        if explicit:
            return str(explicit).strip()
        if self.default_channel_id:
            return self.default_channel_id
        if self._last_seen_channel_id:
            return self._last_seen_channel_id

        # Fall back to first installation in DB
        with SessionLocal() as db:
            inst = db.scalar(select(JoystickInstall).order_by(JoystickInstall.updated_at.desc()))
            if inst and inst.channel_id:
                return inst.channel_id
        return ""

    async def _send_action(self, action_payload: dict) -> None:
        ws = self._ws
        if not ws:
            print("[joystick] Cannot send action (not connected)")
            return

        # websockets library has changed its client connection type across versions.
        # Some versions expose `.closed`, others expose `.close_code` / `.state`.
        # We avoid hard-binding to a specific attribute and instead do a best-effort
        # check + handle send failures gracefully.
        try:
            if hasattr(ws, "closed") and bool(getattr(ws, "closed")):
                print("[joystick] Cannot send action (socket closed)")
                return
            if hasattr(ws, "close_code") and getattr(ws, "close_code") is not None:
                print("[joystick] Cannot send action (socket closed)")
                return
        except Exception:
            # If the object doesn't behave as expected, we'll just attempt the send.
            pass
        identifier = json.dumps({"channel": "GatewayChannel"})
        data = json.dumps(action_payload)
        msg = {
            "command": "message",
            "identifier": identifier,
            "data": data,
        }
        try:
            await ws.send(json.dumps(msg))
        except Exception as e:
            # Do not crash callers (admin endpoints / command replies).
            # Mark connection as unusable so the reconnect loop can restore it.
            print(f"[joystick] send failed: {e}")
            self._ws = None
            return

    # --------------------------
    # Dev/Sim helpers (work in ALL modes)
    # --------------------------
    async def sim_push_chat(self, user: str, text: str) -> None:
        await self._dispatch('chat', { 'user': user, 'text': text })

    async def sim_push_follow(self, user: str) -> None:
        await self._dispatch('follow', { 'user': user })

    async def sim_push_sub(self, user: str, months: int) -> None:
        await self._dispatch('sub', { 'user': user, 'months': months })

    async def sim_push_tip(self, user: str, tokens: int) -> None:
        await self._dispatch('tip', { 'user': user, 'tokens': tokens })

    async def sim_push_dropin(self, user: str) -> None:
        await self._dispatch('dropin', { 'user': user })

    # --------------------------
    # Internal loop
    # --------------------------
    async def _run(self) -> None:
        # If not configured, just idle so the rest of the app still works.
        if not self.basic_key:
            while not self._stop.is_set():
                await asyncio.sleep(1.0)
            return

        url = f"wss://joystick.tv/cable?token={self.basic_key}"
        protocol = "actioncable-v1-json"

        while not self._stop.is_set():
            try:
                async with websockets.connect(url, subprotocols=[protocol]) as ws:
                    self._ws = ws
                    self._backoff_s = 1.0

                    if self.debug:
                        print("[joystick] connected")

                    # Subscribe to GatewayChannel
                    sub = {
                        "command": "subscribe",
                        "identifier": json.dumps({"channel": "GatewayChannel"}),
                    }
                    await ws.send(json.dumps(sub))

                    # Read loop
                    while not self._stop.is_set():
                        raw = await ws.recv()
                        await self._handle_raw(raw)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[joystick] gateway error: {e}")
                self._ws = None
                # simple backoff
                await asyncio.sleep(min(30.0, self._backoff_s))
                self._backoff_s = min(30.0, self._backoff_s * 2)

        self._ws = None

    async def _handle_raw(self, raw: str) -> None:
        # websockets may yield str or bytes depending on version/config
        if isinstance(raw, (bytes, bytearray)):
            try:
                raw = raw.decode("utf-8", errors="replace")
            except Exception:
                return

        if self.debug:
            # Useful when diagnosing new/changed payload shapes.
            print(f"[joystick] <= {raw[:400]}")

        try:
            data = json.loads(raw)
        except Exception:
            return

        # ActionCable control messages:
        # {"type":"welcome"}, {"type":"ping","message":...}, {"type":"confirm_subscription",...}
        if isinstance(data, dict) and data.get("type") in ("welcome", "ping", "confirm_subscription", "reject_subscription"):
            if self.debug and data.get("type") in ("confirm_subscription", "reject_subscription"):
                print(f"[joystick] subscription: {data.get('type')}")
            return

        # Actual payload is typically: {"identifier":..., "message": {...}}
        msg = data.get("message") if isinstance(data, dict) else None

        # Some servers send message as a JSON string; handle both.
        if isinstance(msg, str):
            try:
                msg = json.loads(msg)
            except Exception:
                msg = None

        # Some implementations wrap again: {"message": {...}}.
        # IMPORTANT: do NOT unwrap if this already looks like the event envelope.
        if isinstance(msg, dict) and "event" not in msg and isinstance(msg.get("message"), dict):
            msg = msg.get("message")

        if not isinstance(msg, dict):
            return

        # Remember channelId if present
        ch = msg.get("channelId") or msg.get("channel_id") or msg.get("channel")
        if isinstance(ch, str) and ch:
            self._last_seen_channel_id = ch

        # Joystick's gateway messages put the high-level kind in `event`.
        # `type` is used for sub-types (e.g. ChatMessage: new_message, UserPresence: enter_stream, StreamEvent: Tipped).
        event = (msg.get("event") or "").strip()
        ev = event.lower()
        if ev in ("chatmessage", "chat_message"):
            # Joystick's documented ChatMessage shape has `text` at top-level and user info under `author`.
            # However, older/internal shapes may still nest a payload.
            text = msg.get("text") or ""
            author = msg.get("author") or {}
            user = ""
            if isinstance(author, dict):
                user = author.get("username") or author.get("slug") or author.get("displayName") or ""

            if not text or not user:
                payload = msg.get("payload") or msg.get("data") or {}
                if isinstance(payload, dict) and isinstance(payload.get("message"), dict):
                    payload = payload.get("message")
                if not user:
                    u = payload.get("username") or payload.get("user") or payload.get("sender") or payload.get("display_name") or ""
                    if isinstance(u, dict):
                        u = u.get("username") or u.get("name") or u.get("display_name") or ""
                    user = str(u)
                if not text:
                    t = payload.get("text") or payload.get("body") or ""
                    if not t and isinstance(payload.get("message"), str):
                        t = payload.get("message")
                    if not t and isinstance(payload.get("content"), str):
                        t = payload.get("content")
                    text = str(t)

            if user or text:
                await self._dispatch("chat", {"user": str(user), "text": str(text)})
            return

        if ev in ("userpresence","user_presence"):
            # Joystick's documented UserPresence shape:
            #   event: "UserPresence"
            #   type: "enter_stream"|"leave_stream"
            #   text: "username"
            ptype = (msg.get("type") or "").lower()
            user = msg.get("text") or ""
            if not user:
                payload = msg.get("payload") or {}
                user = payload.get("username") or payload.get("user") or ""
            if ptype == "enter_stream":
                await self._dispatch("dropin", {"user": user})
            return

        if ev in ("streamevent","stream_event"):
            # Joystick's documented StreamEvent shape:
            #   event: "StreamEvent"
            #   type: e.g. "Tipped", "Followed", "WheelSpinClaimed", ...
            #   metadata: JSON string with keys like who/how_much/... (varies by type)
            stype = (msg.get("type") or "").strip()
            stype_l = stype.lower()

            meta_raw = msg.get("metadata")
            meta: dict = {}
            if isinstance(meta_raw, str) and meta_raw.strip():
                try:
                    meta = json.loads(meta_raw)
                except Exception:
                    meta = {}

            user = ""
            if isinstance(meta, dict):
                user = str(meta.get("who") or meta.get("username") or meta.get("user") or "")

            # Fall back to older shapes
            if not user:
                payload = msg.get("payload") or {}
                user = payload.get("username") or payload.get("user") or ""

            if "follow" in stype_l:
                await self._dispatch("follow", {"user": user})
                return

            if "sub" in stype_l or "subscriber" in stype_l or "gift" in stype_l:
                months = 1
                if isinstance(meta, dict) and meta.get("months") is not None:
                    try:
                        months = int(meta.get("months") or 1)
                    except Exception:
                        months = 1
                await self._dispatch("sub", {"user": user, "months": months})
                return

            if "tip" in stype_l or "tipped" in stype_l:
                tokens = 0
                if isinstance(meta, dict):
                    try:
                        tokens = int(meta.get("how_much") or meta.get("tokens") or meta.get("amount") or 0)
                    except Exception:
                        tokens = 0
                await self._dispatch("tip", {"user": user, "tokens": tokens})
                return
            return

    async def _dispatch(self, kind: str, payload: dict) -> None:
        c = self._cbs
        try:
            if kind == "chat" and c.on_chat:
                await c.on_chat(payload.get("user", ""), payload.get("text", ""))
            elif kind == "follow" and c.on_follow:
                await c.on_follow(payload.get("user", ""))
            elif kind == "sub" and c.on_sub:
                await c.on_sub(payload.get("user", ""), int(payload.get("months", 1)))
            elif kind == "tip" and c.on_tip:
                await c.on_tip(payload.get("user", ""), int(payload.get("tokens", 0)))
            elif kind == "dropin" and c.on_dropin:
                await c.on_dropin(payload.get("user", ""))
        except Exception as e:
            print(f"[joystick] callback error: {e}")
