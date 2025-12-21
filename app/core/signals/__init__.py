from pathlib import Path
import asyncio
from .bus import SignalBus
from .obs import OBSHandler
from .vrchat import VRChatOSCHandler

def init_signal_bus(settings) -> SignalBus:
    bus = SignalBus()

    obs = OBSHandler(
        settings.OBS_WS_HOST,
        settings.OBS_WS_PORT,
        settings.OBS_WS_PASSWORD,
    )

    osc_map = Path("./data/signal_osc_map.json")
    vrc = VRChatOSCHandler(
        settings.VRC_OSC_HOST,
        settings.VRC_OSC_PORT,
        osc_map if osc_map.exists() else None
    )

    bus.register(obs)
    bus.register(vrc)

    asyncio.create_task(obs.connect())
    return bus
