import logging
from obsws_python import ReqClient
from .base import Signal, BaseSignalHandler

log = logging.getLogger("pixel.obs")

class OBSHandler(BaseSignalHandler):
    def __init__(self, host: str, port: int, password: str):
        self._host = host
        self._port = port
        self._password = password
        self._client = None
        self._connected = False

    async def connect(self):
        try:
            # obsws-python v1.7.0+ uses ReqClient instead of obsws
            self._client = ReqClient(host=self._host, port=self._port, password=self._password)
            self._connected = True
            log.info("[OBS] Connected")
            
            # Check replay buffer status
            try:
                status = self._client.get_replay_buffer_status()
                if hasattr(status, 'output_active'):
                    if not status.output_active:
                        log.warning("[OBS] Replay buffer is NOT active")
                    else:
                        log.info("[OBS] Replay buffer active")
                else:
                    log.info("[OBS] Replay buffer status unknown")
            except Exception as e:
                log.warning(f"[OBS] Could not check replay buffer status: {e}")
                
        except Exception as e:
            log.error(f"[OBS] Connection failed: {e}")
            self._connected = False

    async def handle(self, signal: Signal) -> None:
        if not self._connected or not self._client:
            return
        if signal.name == "clip.requested":
            try:
                self._client.save_replay_buffer()
                log.info("[OBS] Replay buffer saved")
            except Exception as e:
                log.error(f"[OBS] SaveReplayBuffer failed: {e}")
