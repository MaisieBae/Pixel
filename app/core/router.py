from __future__ import annotations
from typing import Sequence
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.points import PointsService
from app.core.redeems import RedeemsService
from app.core.sfx import validate_sound_file
from app.core.config import Settings
from app.core.models import QueueItem
from app.core.xp import XpService


HELP_TEXT = (
    "Commands: !tts <msg>, !pixel <msg>, !sound <name>, !listsounds [page], !spin, !xp, !level, !clip"
)


def parse_words(text: str) -> list[str]:
    return [w for w in text.strip().split() if w]


def is_command(text: str) -> bool:
    return text.strip().startswith("!")


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
        pending = len(list(db.scalars(select(QueueItem).where(QueueItem.kind=='tts', QueueItem.status=='pending'))))
        if pending >= max(1, settings.TTS_QUEUE_MAX):
            return {"ok": False, "say": "TTS queue is full, try again shortly."}
        payload = {
            "user": user,
            "message": " ".join(args),
            "prefix": bool(settings.TTS_PREFIX_USERNAME),
        }
        result = rs.redeem(user, "tts", cooldown_s=None, queue_kind="tts", payload=payload)
        if not result.get("ok"):
            return {"ok": False, "say": result.get("error", "TTS failed")}
        return {"ok": True, "say": "Queued TTS."}

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
        # existing behavior unchanged
        return {"ok": True, "say": "See /static/sfx for available sounds."}

    if cmd == "!clip":
        # placeholder
        return {"ok": True, "say": "Clip requested."}

    return {"ok": False, "say": "Unknown command. Try !help"}
