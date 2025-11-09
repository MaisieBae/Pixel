from __future__ import annotations
import asyncio
from datetime import datetime
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.models import QueueItem
from app.core.sfx import play_sfx
from app.core.config import Settings
from app.core.overlay_bus import OverlayBus


class QueueWorker:
    """Polls the DB for pending QueueItem records and processes them.

    Supported kinds:
      - 'sound': payload { 'sound': <filename> }

    IMPORTANT: We deliberately **exclude 'tts'** from this worker so that
    /tts/plain-next and /tts/text-next can consume TTS jobs via polling.
    """

    def __init__(self, bus: OverlayBus, settings: Settings, poll_interval: float = 0.25) -> None:
        self.bus = bus
        self.settings = settings
        self.poll_interval = poll_interval
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._stop.clear()
        while not self._stop.is_set():
            try:
                await self._tick_once()
            except Exception as e:
                print(f"[worker] error: {e}")
            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        self._stop.set()

    async def _tick_once(self) -> None:
        with SessionLocal() as db:
            item = self._next_pending(db)
            if not item:
                return
            item.status = 'running'
            item.started_at = datetime.utcnow()
            db.commit()

            try:
                await self._process_item(db, item)
                item.status = 'done'
            except Exception as e:
                item.status = 'error'
                payload = dict(item.payload_json or {})
                payload['error'] = str(e)
                item.payload_json = payload
            finally:
                item.finished_at = datetime.utcnow()
                db.commit()

    def _next_pending(self, db: Session) -> QueueItem | None:
        # Only pick jobs that are NOT TTS
        stmt = (
            select(QueueItem)
            .where(QueueItem.status == 'pending', QueueItem.kind != 'tts')
            .order_by(QueueItem.id.asc())
            .limit(1)
        )
        return db.scalar(stmt)

    async def _process_item(self, db: Session, item: QueueItem) -> None:
        kind = (item.kind or '').lower()
        payload = item.payload_json or {}

        if kind == 'sound':
            filename = payload.get('sound')
            if not filename:
                raise ValueError('sound payload missing filename')
            path = self.settings.sounds_path / filename
            if not path.exists() or not path.is_file():
                raise FileNotFoundError(f'sound file not found on server: {filename}')
            await play_sfx(self.bus, filename)
            return

        # Any other kinds are ignored here
        print(f"[worker] ignored kind: {kind}")