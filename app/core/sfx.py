from __future__ import annotations
from typing import Optional
from app.core.overlay_bus import OverlayBus

def _name_or_url(name_or_url: str) -> dict:
    s = (name_or_url or "").strip()
    # If it looks like a URL or already absolute path, keep as url; else treat as name
    if s.startswith("http://") or s.startswith("https://") or s.startswith("/"):
        return {"url": s}
    return {"name": s}

async def play_sfx(bus: OverlayBus, name_or_url: str) -> None:
    """
    One-shot playback. Matches overlay_sfx.html listener:
      { type: 'sfx', action: 'play', url?: string, name?: string }
    """
    await bus.broadcast({
        "type": "sfx",
        "action": "play",
        **_name_or_url(name_or_url),
    })

async def loop_start(bus: OverlayBus, name_or_url: str) -> None:
    """
    Start looping playback. Matches overlay_sfx.html:
      { type: 'sfx', action: 'loop-start', url?: string, name?: string }
    """
    await bus.broadcast({
        "type": "sfx",
        "action": "loop-start",
        **_name_or_url(name_or_url),
    })

async def loop_stop(bus: OverlayBus) -> None:
    """Stop looping playback. Matches overlay_sfx.html action 'loop-stop'."""
    await bus.broadcast({
        "type": "sfx",
        "action": "loop-stop",
    })
