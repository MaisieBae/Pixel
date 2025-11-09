from __future__ import annotations
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.models import QueueItem
from app.core.overlay_bus import OverlayBus
from app.core.sfx import play_sfx
from app.core.config import Settings


class TTSService:
    def __init__(self, db: Session, settings: Settings, bus: OverlayBus) -> None:
        self.db = db
        self.settings = settings
        self.bus = bus

    def pending_count(self) -> int:
        stmt = select(QueueItem).where(QueueItem.kind == 'tts', QueueItem.status == 'pending')
        return len(list(self.db.scalars(stmt)))

    def _build_text(self, payload: dict) -> str:
        # payload = { 'user': name, 'message': text, 'prefix': bool }
        msg = (payload.get('message') or '').strip()
        if not msg:
            return ''
        prefix = payload.get('prefix', False)
        user = (payload.get('user') or '').strip()
        if prefix and user:
            return f"{user} said: {msg}"
        return msg

    async def next_plain(self) -> str:
        """Return next TTS message (text/plain). Plays pre-roll first and marks done.
        Returns empty string if none available.
        """
        # FIFO pending
        item = self.db.scalar(
            select(QueueItem).where(QueueItem.kind == 'tts', QueueItem.status == 'pending').order_by(QueueItem.id.asc()).limit(1)
        )
        if not item:
            return ''

        # Build text and mark running -> done
        text = self._build_text(item.payload_json or {})
        item.status = 'running'
        item.started_at = datetime.utcnow()
        self.db.commit()

        # Pre-roll sound (best-effort)
        try:
            if self.settings.TTS_PRE_SOUND:
                await play_sfx(self.bus, self.settings.TTS_PRE_SOUND)
        except Exception:
            pass

        # Mark done immediately so the queue drains even if the bridge crashes mid-read
        item.status = 'done'
        item.finished_at = datetime.utcnow()
        self.db.commit()

        return text