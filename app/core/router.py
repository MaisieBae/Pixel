from __future__ import annotations
from typing import Sequence
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.points import PointsService
from app.core.redeems import RedeemsService
from app.core.sfx import validate_sound_file
from app.core.config import Settings
from app.core.models import QueueItem
from app.core.xp import XpService


HELP_TEXT = (
    "Commands: !points, !tts <msg>, !pixel <msg>, !sound <name>, !listsounds [page], !spin, !xp, !level, !clip"
)

# Sounds per page for !listsounds command
SOUNDS_PER_PAGE = 15


def parse_words(text: str) -> list[str]:
    return [w for w in text.strip().split() if w]


def is_command(text: str) -> bool:
    return text.strip().startswith("!")


def get_available_sounds(settings: Settings) -> list[str]:
    """Get list of all available sound files from the sounds directory."""
    sounds_path = Path(settings.SOUNDS_DIR).resolve()
    if not sounds_path.exists() or not sounds_path.is_dir():
        return []
    
    # Get all audio files (common formats)
    extensions = {'.wav', '.mp3', '.ogg', '.flac', '.m4a'}
    sounds = []
    
    for file in sounds_path.iterdir():
        if file.is_file() and file.suffix.lower() in extensions:
            sounds.append(file.name)
    
    return sorted(sounds)


def format_sounds_list(sounds: list[str], page: int = 1, per_page: int = SOUNDS_PER_PAGE) -> str:
    """Format sounds list with pagination info."""
    if not sounds:
        return "No sounds available."
    
    total = len(sounds)
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    
    # Validate page number
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    
    # Calculate slice indices
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total)
    
    # Get page of sounds
    page_sounds = sounds[start_idx:end_idx]
    
    # Format output
    sounds_str = ", ".join(page_sounds)
    footer = f" | Page {page}/{total_pages} ({total} total)"
    
    # If message would be too long for chat, truncate the list
    MAX_CHAT_LEN = 400
    if len(sounds_str) + len(footer) > MAX_CHAT_LEN:
        # Reduce list until it fits
        while page_sounds and len(", ".join(page_sounds)) + len(footer) > MAX_CHAT_LEN:
            page_sounds.pop()
        sounds_str = ", ".join(page_sounds)
        if len(page_sounds) < (end_idx - start_idx):
            sounds_str += "..."
    
    return f"Sounds: {sounds_str}{footer}"


def handle_chat(db: Session, settings: Settings, user: str, text: str) -> dict:
    ps = PointsService(db)
    rs = RedeemsService(db)
    rs.seed_defaults(settings)

    user = ps.ensure_user(user).name
    words = parse_words(text)
    if not words:
        return {"ok": True}

    cmd = words[0].lower()
    args = words[1:]

    if cmd == "!help":
        return {"ok": True, "say": HELP_TEXT}

    if cmd == "!xp":
        xs = XpService(db, settings)
        return {"ok": True, "say": xs.get_progress_text(user)}

    if cmd == "!level":
        xs = XpService(db, settings)
        u, xp = xs.ensure_user_xp(user)
        return {"ok": True, "say": f"@{u.name} — Level {xp.level} (XP {xp.total_xp})"}

    if cmd == "!tts":
        if not args:
            return {"ok": False, "say": "Usage: !tts <message>"}
        # FIX: Count both 'pending' AND 'running' items to prevent stuck items from blocking queue
        active_tts = len(list(db.scalars(
            select(QueueItem).where(
                QueueItem.kind == 'tts',
                QueueItem.status.in_(['pending'])
            )
        )))
        if active_tts >= max(1, settings.TTS_QUEUE_MAX):
            return {"ok": False, "say": "TTS queue is full, try again shortly."}
        payload = {
            "user": user,
            "message": " ".join(args),
            "prefix": bool(settings.TTS_PREFIX_USERNAME),
        }
        result = rs.redeem(user, "tts", cooldown_s=None, queue_kind="tts", payload=payload)
        if not result.get("ok"):
            return {"ok": False, "say": result.get("error", "TTS failed")}
        return {"ok": True, "say": "TTS sent!"}

    if cmd == "!pixel":
        if not args:
            return {"ok": False, "say": "Usage: !pixel <message>"}
        payload = {"user": user, "message": " ".join(args)}
        # Cooldown is controlled in admin via redeem.cooldown_s
        result = rs.redeem(user, "pixel", cooldown_s=None, queue_kind="pixel", payload=payload)
        if not result.get("ok"):
            return {"ok": False, "say": result.get("error", "Pixel failed")}
        return {"ok": True, "say": "Pixel is thinking…"}

    if cmd == "!sound":
        if not args:
            return {"ok": False, "say": "Usage: !sound <name>"}
        try:
            actual = validate_sound_file(settings, args[0])
        except Exception:
            return {"ok": False, "say": f"Sound not found: {args[0]}"}
        payload = {"user": user, "sound": actual}
        result = rs.redeem(user, "sound", cooldown_s=None, queue_kind="sound", payload=payload)
        if not result.get("ok"):
            return {"ok": False, "say": result.get("error", "Sound failed")}
        return {"ok": True, "say": f"Queued sound: {actual}"}

    if cmd == "!spin":
        payload = {"user": user}
        result = rs.redeem(user, "spin", cooldown_s=None, queue_kind="spin", payload=payload)
        if not result.get("ok"):
            return {"ok": False, "say": result.get("error", "Spin failed")}
        return {"ok": True, "say": "Spinning the wheel…"}

    if cmd == "!listsounds":
        # Parse page number from args
        page = 1
        if args:
            try:
                page = int(args[0])
            except ValueError:
                return {"ok": False, "say": "Usage: !listsounds [page_number]"}
        
        # Get available sounds and format response
        sounds = get_available_sounds(settings)
        message = format_sounds_list(sounds, page=page, per_page=SOUNDS_PER_PAGE)
        
        return {"ok": True, "say": message}

    if cmd == "!points" or cmd == "!balance":
        ps = PointsService(db)
        u = ps.ensure_user(user)
        balance = ps.get_balance(u.id)
        # Return whisper=True so the handler knows to whisper
        return {"ok": True, "say": f"@{u.name} has {balance} points.", "whisper": True}

    if cmd == "!clip":
        payload = {"user": user}
        result = rs.redeem(user, "clip", cooldown_s=None, queue_kind="clip", payload=payload)
        if not result.get("ok"):
            return {"ok": False, "say": result.get("error", "Clip failed")}
        return {"ok": True, "say": "Clip requested."}
        
    if cmd == "!buzz":
        # Just queue it like other redeems
        payload = {"user": user, "action": "click_tip"}
        result = rs.redeem(user, "remotetip", cooldown_s=None, queue_kind="extension", payload=payload)
        if not result.get("ok"):
            return {"ok": False, "say": result.get("error", "Buzzie failed!")}
        return {"ok": True, "say": "Sending a buzzie..."}
        
    return {"ok": False, "say": "Unknown command. Try !help"}
