from __future__ import annotations
from typing import Sequence
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.points import PointsService
from app.core.redeems import RedeemsService
from app.core.sfx import validate_sound_file
from app.core.config import Settings
from app.core.models import QueueItem


HELP_TEXT = (
    "Commands: !tts <msg>, !pixel <msg>, !sound <name>, !listsounds [page], !spin, !clip"
)


def parse_words(text: str) -> list[str]:
    return [w for w in text.strip().split() if w]


def is_command(text: str) -> bool:
    return text.strip().startswith("!")


def handle_chat(db: Session, settings: Settings, user: str, text: str) -> dict:
    ps = PointsService(db)
    rs = RedeemsService(db)
    rs.seed_defaults()

    user = ps.ensure_user(user).name
    words = parse_words(text)
    if not words:
        return {"ok": True}

    cmd = words[0].lower()
    args = words[1:]

    if cmd == "!help":
        return {"ok": True, "say": HELP_TEXT}

    if cmd == "!tts":
        if not args:
            return {"ok": False, "say": "Usage: !tts <message>"}
        # Queue cap anti-spam
        pending = len(list(db.scalars(select(QueueItem).where(QueueItem.kind=='tts', QueueItem.status=='pending'))))
        if pending >= max(1, settings.TTS_QUEUE_MAX):
            return {"ok": False, "say": "TTS queue is full, try again shortly."}
        payload = {
            "user": user,
            "message": " ".join(args),
            "prefix": bool(settings.TTS_PREFIX_USERNAME),
        }
        result = rs.redeem(user, "tts", cooldown_s=max(1, settings.TTS_COOLDOWN_SECONDS), queue_kind="tts", payload=payload)
        if not result.get("ok"):
            return {"ok": False, "say": result.get("error", "TTS failed")}
        return {"ok": True, "say": "Queued TTS."}

    if cmd == "!pixel":
        # Perplexity integration comes later. For now, just explain.
        return {"ok": True, "say": "Pixel voice coming soon."}

    if cmd == "!sound":
        if not args:
            return {"ok": False, "say": "Usage: !sound <name>"}
        try:
            actual = validate_sound_file(settings, args[0])
        except Exception:
            return {"ok": False, "say": f"Sound not found: {args[0]}"}
        payload = {"user": user, "sound": actual}
        result = rs.redeem(user, "sound", cooldown_s=5, queue_kind="sound", payload=payload)
        if not result.get("ok"):
            return {"ok": False, "say": result.get("error", "Sound failed")}
        return {"ok": True, "say": f"Playing {actual}"}

    if cmd == "!listsounds":
        page = 1
        if args and args[0].isdigit():
            page = max(1, int(args[0]))
        names = [p.name for p in settings.sounds_path.glob("*") if p.is_file() and p.suffix.lower() in (".wav", ".mp3", ".ogg")]
        names.sort()
        per_page = 15
        start = (page - 1) * per_page
        end = start + per_page
        total_pages = max(1, (len(names) + per_page - 1) // per_page)
        page_items = names[start:end]
        if not page_items:
            return {"ok": True, "say": f"No sounds on page {page}. Try 1-{total_pages}."}
        joined = ", ".join([n.rsplit(".", 1)[0] for n in page_items])
        hint = f"Use !listsounds <page>. Page {page}/{total_pages}."
        return {"ok": True, "say": f"Sounds: {joined}. {hint}"}

    if cmd == "!spin":
        payload = {"user": user}
        result = rs.redeem(user, "spin", cooldown_s=60, queue_kind="spin", payload=payload)
        if not result.get("ok"):
            return {"ok": False, "say": result.get("error", "Spin failed")}
        return {"ok": True, "say": "Wheel is spinning!"}

    if cmd == "!clip":
        # Future: OBS remote clip. For now, enqueue for parity.
        rs.queue.enqueue("clip", {"user": user})
        return {"ok": True, "say": "Clip requested."}

    return {"ok": True, "say": HELP_TEXT}