from __future__ import annotations
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json


class OverlayBus:
    def __init__(self) -> None:
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, message: dict) -> None:
        async with self._lock:
            targets = list(self._clients)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)


def overlay_ws_router(bus: OverlayBus) -> APIRouter:
    router = APIRouter()

    @router.websocket("/overlay/ws")
    async def ws_overlay(ws: WebSocket):
        await bus.connect(ws)
        try:
            while True:
                # Clients (like Admin Quick Spin) may send JSON we should rebroadcast.
                # Overlays usually send nothing; that's fine.
                raw = await ws.receive_text()
                if not raw:
                    continue

                # If it's JSON, rebroadcast it.
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue

                if isinstance(msg, dict) and msg.get("type"):
                    await bus.broadcast(msg)

        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            await bus.disconnect(ws)

    return router
