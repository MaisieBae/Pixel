from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.models import QueueItem
from app.core.overlay_bus import OverlayBus
from app.core.sfx import play_sfx
from app.core.config import Settings
from app.core.text import sanitize_tts_text


class TTSService:
    def __init__(self, db: Session, settings: Settings, bus: OverlayBus) -> None:
        self.db = db
        self.settings = settings
        self.bus = bus

    def pending_count(self) -> int:
        stmt = select(QueueItem).where(QueueItem.kind == 'tts', QueueItem.status == 'pending')
        return len(list(self.db.scalars(stmt)))

    def _build_text(self, payload: dict) -> str:
        msg = (payload.get('message') or '').strip()
        if not msg:
            return ''
        prefix = payload.get('prefix', False)
        user = (payload.get('user') or '').strip()
        # Sanitize only for Pixel-sourced messages
        if (payload.get('source') or '').lower() == 'pixel':
            msg = sanitize_tts_text(msg)
        if prefix and user:
            return f"{user} said: {msg}"
        return msg

    async def next_plain(self) -> str:
        # v1.4.2 two-stage pre-roll flow (unchanged except for import path)
        now = datetime.utcnow()
        delay = max(0, int(self.settings.TTS_PRE_DELAY_MS)) / 1000.0

        running = self.db.scalar(
            select(QueueItem)
            .where(QueueItem.kind == 'tts', QueueItem.status == 'running')
            .order_by(QueueItem.id.asc())
            .limit(1)
        )
        if running:
            payload = running.payload_json or {}
            primed_at_str = payload.get('primed_at')
            if primed_at_str:
                try:
                    primed_at = datetime.fromisoformat(primed_at_str)
                except Exception:
                    primed_at = now
                if (now - primed_at).total_seconds() >= (int(self.settings.TTS_PRE_DELAY_MS)/1000.0):
                    text = self._build_text(payload)
                    running.status = 'done'
                    running.finished_at = now
                    self.db.commit()
                    return text
            return ''

        pending = self.db.scalar(
            select(QueueItem)
            .where(QueueItem.kind == 'tts', QueueItem.status == 'pending')
            .order_by(QueueItem.id.asc())
            .limit(1)
        )
        if not pending:
            return ''

        payload = dict(pending.payload_json or {})
        payload['primed_at'] = now.isoformat()
        pending.payload_json = payload
        pending.status = 'running'
        pending.started_at = now
        self.db.commit()

        try:
            if self.settings.TTS_PRE_SOUND:
                await play_sfx(self.bus, self.settings.TTS_PRE_SOUND)
        except Exception:
            pass

        return ''