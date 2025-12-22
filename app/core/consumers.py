from __future__ import annotations

import asyncio
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.models import QueueItem
from app.core.overlay_bus import OverlayBus
from app.core.pixel import call_perplexity
from app.core.sfx import play_sfx



class QueueWorker:
    """Processes non-TTS jobs. TTS remains consumed by /tts/*.

    Supported kinds:
      - 'sound': payload { 'sound': <filename> }
      - 'pixel': payload { 'user': <name>, 'message': <text> } → calls Perplexity, then enqueues TTS
      - 'spin': payload { 'user': <name> } → spins wheel, broadcasts overlay, enqueues TTS
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
        # Only pick jobs that are NOT TTS (tts is consumed by endpoints)
        stmt = (
            select(QueueItem)
            .where(QueueItem.status == 'pending', QueueItem.kind != 'tts')
            .order_by(QueueItem.id.asc())
            .limit(1)
        )
        return db.scalar(stmt)
        
    async def _handle_extension(self, item: QueueItem) -> None:
        """Handle extension commands like remote button clicks."""
        from app.admin.server import _extension_ws  # <-- IMPORT IT INSTEAD
    
        payload = item.payload_json or {}
        action = payload.get("action", "")
    
        # Send to all connected extensions
        for ws in _extension_ws:
            try:
                await ws.send_text(json.dumps({"action": action}))
            except:
                pass

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

        if kind == 'pixel':
            user = payload.get('user') or ''
            msg = payload.get('message') or ''
            prompt = f"@{user}: {msg}" if user else msg
            reply = await call_perplexity(self.settings, prompt)

            # Final clamp using configured caps
            from app.core.text import clamp_reply

            reply = clamp_reply(reply, int(self.settings.PIXEL_MAX_CHARS), int(self.settings.PIXEL_MAX_SENTENCES))
            tts_payload = {"user": user, "message": reply, "prefix": False, "source": "pixel"}
            q = QueueItem(kind='tts', status='pending', payload_json=tts_payload)
            db.add(q)
            db.commit()
            return

        if kind == 'spin':
            import random

            from app.core.sfx import loop_start, loop_stop  # <-- use helpers
            from app.core.text import clamp_reply, sanitize_tts_text
            from app.core.wheel import load_prize_lines, load_prizes, load_spin_lines, weighted_choice_index

            user = (payload.get('user') or '').strip()
            prizes = load_prizes(self.settings)
            target_idx = weighted_choice_index(prizes)
            prize_obj = prizes[target_idx] if prizes and target_idx < len(prizes) else {}
            prize_name = str(prize_obj.get('name', 'Prize'))

            dur = random.randint(
                max(2, int(self.settings.WHEEL_SPIN_MIN)),
                max(int(self.settings.WHEEL_SPIN_MIN), int(self.settings.WHEEL_SPIN_MAX)),
            )

            # (1) TTS pre-spin
            spin_lines = load_spin_lines(self.settings)
            if spin_lines and spin_lines[0]:
                pre = random.choice(spin_lines)
                pre = pre.replace('{user}', user)
                pre = clamp_reply(sanitize_tts_text(pre), 220, 2)
                db.add(
                    QueueItem(
                        kind='tts',
                        status='pending',
                        payload_json={"user": user, "message": pre, "prefix": False, "source": "wheel"},
                    )
                )
                db.commit()

            # (2) small delay to let pre-roll land
            await asyncio.sleep(max(0, int(self.settings.WHEEL_PRE_TTS_DELAY_MS)) / 1000.0)

            # (3) start one-shot + loop (on SFX overlay), then rain visuals
            try:
                await play_sfx(self.bus, self.settings.WHEEL_SFX_START)
            except Exception:
                pass
            try:
                await loop_start(self.bus, f"/media/sounds/{self.settings.WHEEL_SFX_LOOP}")
            except Exception:
                pass
            try:
                await self.bus.broadcast({'type': 'wheel', 'action': 'rain-start', 'image': self.settings.WHEEL_IMAGE_URL})
            except Exception:
                pass

            await asyncio.sleep(dur)

            # (4) stop rain + loop + win stinger
            try:
                await self.bus.broadcast({'type': 'wheel', 'action': 'rain-stop'})
            except Exception:
                pass
            try:
                await loop_stop(self.bus)
            except Exception:
                pass
            try:
                await play_sfx(self.bus, self.settings.WHEEL_SFX_WIN)
            except Exception:
                pass

            # (5) reveal animation
            try:
                await self.bus.broadcast(
                    {'type': 'wheel', 'action': 'reveal', 'image': self.settings.WHEEL_IMAGE_URL, 'prize': prize_name}
                )
            except Exception:
                pass

            # (5.5) Apply effects (cleanly) via EffectEngine
            try:
                from app.core.effects.types import EffectContext
                from app.core.effects.engine import EffectEngine, effects_from_prize

                effects = effects_from_prize(prize_obj)
                engine = EffectEngine(db=db, settings=self.settings, bus=self.bus)
                ctx = EffectContext(
                    user=user, source="wheel", prize_name=prize_name, db=db, settings=self.settings, bus=self.bus
                )
                results = engine.apply_all(effects, ctx)

                # Store results on the queue item for audit/debug
                new_payload = dict(payload)
                new_payload['prize'] = prize_name
                new_payload['effect_results'] = [r.to_dict() for r in results]
                item.payload_json = new_payload
            except Exception as e:
                print(f"[wheel] effects error: {e}")

            # (6) TTS prize line
            win_lines = load_prize_lines(self.settings)
            if win_lines and win_lines[0]:
                win = random.choice(win_lines)
                win = win.replace('{user}', user).replace('{prize}', prize_name)
                win = clamp_reply(sanitize_tts_text(win), 220, 2)
                db.add(
                    QueueItem(
                        kind='tts',
                        status='pending',
                        payload_json={"user": user, "message": win, "prefix": False, "source": "wheel"},
                    )
                )

            db.commit()
            return
            
        if kind == 'clip':
            from app.core.signals.base import Signal
            from app.core.signals.bus import SignalBus
            
            # Get global signal bus if it exists
            signal_bus = getattr(self, '_signal_bus', None)
            if signal_bus:
                signal = Signal(
                    name="clip.requested",
                    user=payload.get('user', ''),
                    source="queue",
                    payload=payload
                )
                signal_bus.emit(signal)
            return
            
        if kind == 'extension':  # <-- ADD THIS BLOCK
            await self._handle_extension(item)
            return    
            
        # Ignore other kinds here
        print(f"[worker] ignored kind: {kind}")
