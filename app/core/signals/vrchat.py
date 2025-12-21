import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from pythonosc.udp_client import SimpleUDPClient
from .base import Signal, BaseSignalHandler

log = logging.getLogger("pixel.vrchat")

class VRChatOSCHandler(BaseSignalHandler):
    def __init__(self, host: str, port: int, mapping_path: Path | None):
        self._client = SimpleUDPClient(host, port)
        self._mappings: Dict[str, List[Dict[str, Any]]] = {}
        if mapping_path and mapping_path.exists():
            try:
                self._mappings = json.loads(mapping_path.read_text())
                log.info("[VRC] Loaded OSC signal mappings")
            except Exception as e:
                log.error(f"[VRC] Failed to load mapping file: {e}")

    async def handle(self, signal: Signal) -> None:
        actions = self._mappings.get(signal.name)
        if not actions:
            return
        for action in actions:
            addr = action["address"]
            typ = action["type"]
            if typ == "pulse":
                duration = float(action.get("duration", 0.25))
                self._client.send_message(addr, True)
                await asyncio.sleep(duration)
                self._client.send_message(addr, False)
            elif typ in ("bool", "int", "float"):
                self._client.send_message(addr, action["value"])
