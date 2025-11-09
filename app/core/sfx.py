from __future__ import annotations
from pathlib import Path
from fastapi import HTTPException
from app.core.overlay_bus import OverlayBus
from app.core.config import Settings


def list_sound_files(settings: Settings) -> list[str]:
    base: Path = settings.sounds_path
    if not base.exists():
        base.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    for ext in ("*.wav", "*.mp3", "*.ogg"):
        files.extend(sorted([p.name for p in base.glob(ext)]))
    return files


def validate_sound_file(settings: Settings, name: str) -> str:
    # name can be bare ("ding") or with extension ("ding.wav")
    p = Path(name)
    candidate = settings.sounds_path / (p.name)
    if candidate.exists() and candidate.is_file():
        return candidate.name  # return the final name to serve via /media/sounds/<name>

    # Try known extensions if none present
    if "." not in p.name:
        for ext in (".wav", ".mp3", ".ogg"):
            candidate2 = settings.sounds_path / (p.name + ext)
            if candidate2.exists() and candidate2.is_file():
                return candidate2.name
    raise HTTPException(status_code=404, detail=f"Sound not found: {name}")


async def play_sfx(bus: OverlayBus, filename: str) -> None:
    # Overlay will fetch from /media/sounds/<filename>
    await bus.broadcast({
        "type": "play_sfx",
        "file": f"/media/sounds/{filename}",
    })