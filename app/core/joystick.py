from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

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
    """Simple adapter wrapper.

    If token is empty -> Dev/Sim mode with internal queue.
    If token is present -> Real mode placeholder (network ingest TBD).

    NEW: sim_push_* now dispatch immediately in BOTH modes, so the Admin Chat Console
    always works (even when a real token is configured).
    """

    def __init__(self, token: str, room_id: str | None = None) -> None:
        self.token = (token or "").strip()
        self.room_id = (room_id or "").strip()
        self._cbs = JoystickCallbacks()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._sim_queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()

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

    async def send_chat(self, text: str) -> None:
        # TODO: implement chat post to Joystick API when in real mode
        print(f"[joystick] (send_chat) {text}")

    # --- Dev/Sim helpers (now work in ALL modes) ---
    async def sim_push_chat(self, user: str, text: str) -> None:
        # Dispatch immediately so admin console works in live mode too
        await self._dispatch('chat', { 'user': user, 'text': text })

    async def sim_push_follow(self, user: str) -> None:
        await self._dispatch('follow', { 'user': user })

    async def sim_push_sub(self, user: str, months: int) -> None:
        await self._dispatch('sub', { 'user': user, 'months': months })

    async def sim_push_tip(self, user: str, tokens: int) -> None:
        await self._dispatch('tip', { 'user': user, 'tokens': tokens })

    async def sim_push_dropin(self, user: str) -> None:
        await self._dispatch('dropin', { 'user': user })

    # --- Internals ---
    async def _run(self) -> None:
        if not self.token:
            await self._run_sim()
        else:
            await self._run_real()

    async def _run_sim(self) -> None:
        print("[joystick] Sim mode active. Use Admin to inject chat/events.")
        while not self._stop.is_set():
            try:
                kind, payload = await asyncio.wait_for(self._sim_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            await self._dispatch(kind, payload)

    async def _run_real(self) -> None:
        # TODO: Replace with real Joystick.tv socket/HTTP stream per docs.
        print("[joystick] Real mode placeholder active. Implement network ingest here.")
        while not self._stop.is_set():
            await asyncio.sleep(1.0)

    async def _dispatch(self, kind: str, payload: dict) -> None:
        c = self._cbs
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