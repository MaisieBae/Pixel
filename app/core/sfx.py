from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from app.core.overlay_bus import OverlayBus
from app.core.config import Settings

# Allowed audio extensions for sounds directory
ALLOWED_EXTS = {".wav", ".mp3", ".ogg", ".m4a", ".aac", ".flac"}

# ----------------------------
# Filesystem helpers (used by Admin)
# ----------------------------

def _sounds_dir(settings: Settings) -> Path:
    # Expect settings.SOUNDS_DIR to be configured already
    p = Path(getattr(settings, "SOUNDS_DIR", "./sounds")).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p

def list_sound_files(settings: Settings) -> List[str]:
    """
    Return a sorted list of file names (not full paths) in SOUNDS_DIR that match ALLOWED_EXTS.
    """
    base = _sounds_dir(settings)
    files: List[str] = []
    for f in base.iterdir():
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTS:
            files.append(f.name)
    files.sort(key=str.lower)
    return files

def validate_sound_file(settings: Settings, name: str) -> str:
    """
    Validate a requested sound by file name (with or without extension).

    Returns the *actual filename* (with extension) if found/valid.
    Raises ValueError if not found or extension not allowed.
    """
    base = _sounds_dir(settings)
    raw = (name or "").strip()
    if not raw:
        raise ValueError("Empty sound name")

    candidate = base / raw
    if candidate.exists() and candidate.is_file():
        if candidate.suffix.lower() not in ALLOWED_EXTS:
            raise ValueError(f"Unsupported extension: {candidate.suffix}")
        return candidate.name

    # If extension was omitted, match any allowed ext by stem
    stem = Path(raw).stem
    for ext in ALLOWED_EXTS:
        c = base / f"{stem}{ext}"
        if c.exists() and c.is_file():
            return c.name

    raise ValueError(f"Sound not found: {raw}")

# ----------------------------
# Overlay broadcast (SFX overlay protocol)
# ----------------------------

def _name_or_url(name_or_url: str) -> dict:
    s = (name_or_url or "").strip()
    # If it looks like a URL or absolute path, send as url; else send as name
    if s.startswith("http://") or s.startswith("https://") or s.startswith("/"):
        return {"url": s}
    return {"name": s}

async def play_sfx(bus: OverlayBus, name_or_url: str) -> None:
    """
    One-shot playback. SFX overlay expects:
      { type: 'sfx', action: 'play', url?: string, name?: string }
    """
    await bus.broadcast({
        "type": "sfx",
        "action": "play",
        **_name_or_url(name_or_url),
    })

async def loop_start(bus: OverlayBus, name_or_url: str) -> None:
    """
    Start looping playback. SFX overlay expects:
      { type: 'sfx', action: 'loop-start', url?: string, name?: string }
    """
    await bus.broadcast({
        "type": "sfx",
        "action": "loop-start",
        **_name_or_url(name_or_url),
    })

async def loop_stop(bus: OverlayBus) -> None:
    """Stop looping playback. SFX overlay expects { type:'sfx', action:'loop-stop' }."""
    await bus.broadcast({
        "type": "sfx",
        "action": "loop-stop",
    })
