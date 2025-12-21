import logging
from obsws_python import obsws
from .base import Signal, BaseSignalHandler

log = logging.getLogger("pixel.obs")

class OBSHandler(BaseSignalHandler):
    def __init__(self, host: str, port: int, password: str):
        self._client = obsws(host=host, port=port, password=password)
        self._connected = False

    async def connect(self):
        try:
            self._client.connect()
            self._connected = True
            log.info("[OBS] Connected")
            status = self._client.call("GetReplayBufferStatus")
            if not status.get("outputActive"):
                log.warning("[OBS] Replay buffer is NOT active")
            else:
                log.info("[OBS] Replay buffer active")
        except Exception as e:
            log.error(f"[OBS] Connection failed: {e}")

    async def handle(self, signal: Signal) -> None:
        if not self._connected:
            return
        if signal.name == "clip.requested":
            try:
                self._client.call("SaveReplayBuffer")
                log.info("[OBS] Replay buffer saved")
            except Exception as e:
                log.error(f"[OBS] SaveReplayBuffer failed: {e}")
