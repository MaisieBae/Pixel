from __future__ import annotations
import asyncio
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.models import QueueItem
from app.core.sfx import play_sfx
from app.core.config import Settings
from app.core.overlay_bus import OverlayBus
from app.core.pixel import call_perplexity


class QueueWorker:
    """Processes non-TTS jobs. TTS remains consumed by /tts/*.

    Supported kinds:
      - 'sound': payload { 'sound': <filename> }
      - 'pixel': payload { 'user': <name>, 'message': <text> } → calls Perplexity, then enqueues TTS
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
            msg  = payload.get('message') or ''
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
            import asyncio, random
            from app.core.wheel import (
                load_prizes, weighted_choice_index,
                load_spin_lines, load_prize_lines
            )
            from app.core.text import clamp_reply, sanitize_tts_text
            from app.core.sfx import play_sfx, loop_start, loop_stop  # <-- use helpers

            user = (payload.get('user') or '').strip()
            prizes = load_prizes(self.settings)
            target_idx = weighted_choice_index(prizes)
            prize_obj = prizes[target_idx] if prizes and target_idx < len(prizes) else {}
            prize_name = str(prize_obj.get('name', 'Prize'))

            dur = random.randint(
                max(2, int(self.settings.WHEEL_SPIN_MIN)),
                max(int(self.settings.WHEEL_SPIN_MIN), int(self.settings.WHEEL_SPIN_MAX))
            )

            # (1) TTS pre-spin
            spin_lines = load_spin_lines(self.settings)
            if spin_lines and spin_lines[0]:
                pre = random.choice(spin_lines)
                pre = pre.replace('{user}', user)
                pre = clamp_reply(sanitize_tts_text(pre), 220, 2)
                db.add(QueueItem(kind='tts', status='pending', payload_json={
                    "user": user, "message": pre, "prefix": False, "source": "wheel"
                }))
                db.commit()

            # (2) small delay to let pre-roll land
            await asyncio.sleep(max(0, int(self.settings.WHEEL_PRE_TTS_DELAY_MS))/1000.0)

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
                await self.bus.broadcast({
                    'type':'wheel','action':'rain-start',
                    'image': self.settings.WHEEL_IMAGE_URL
                })
            except Exception:
                pass

            await asyncio.sleep(dur)

            # (4) stop rain + loop + win stinger
            try:
                await self.bus.broadcast({'type':'wheel','action':'rain-stop'})
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
                await self.bus.broadcast({
                    'type':'wheel','action':'reveal',
                    'image': self.settings.WHEEL_IMAGE_URL,
                    'prize': prize_name
                })
            except Exception:
                pass

            # (5.5) Award points/items and fire optional OSC events tied to the prize
            try:
                from app.core.points import PointsService
                from app.core.items import ItemsService
                ps = PointsService(db)
                isvc = ItemsService(db)

                # points: { "grant_points": 50 }
                gp = prize_obj.get("grant_points")
                if gp is not None:
                    amt = int(gp)
                    if amt != 0 and user:
                        urow = ps.ensure_user(user)
                        ps.grant(urow.id, amount=amt, reason=f"wheel:{prize_name}")

                # item: { "item_key": "confetti_token", "item_qty": 1 }
                ik = (prize_obj.get("item_key") or "").strip().lower()
                if ik and user:
                    qty = int(prize_obj.get("item_qty") or 1)
                    urow = ps.ensure_user(user)
                    isvc.grant_item(urow.id, ik, qty=qty)

                # osc: { "osc": { "address": "...", "type": "int|float|string|bool", "value": ... } }
                # or  { "osc": [ {..}, {..} ] }
                osc_spec = prize_obj.get("osc")
                if osc_spec and user:
                    from app.core.osc import OSCService, OscMessage
                    osc = OSCService(self.settings)
                    msgs = []
                    if isinstance(osc_spec, dict):
                        msgs.append(OscMessage(
                            address=str(osc_spec.get("address","")).strip(),
                            type=str(osc_spec.get("type","")).strip(),
                            value=osc_spec.get("value")
                        ))
                    elif isinstance(osc_spec, list):
                        for it in osc_spec:
                            if not isinstance(it, dict):
                                continue
                            msgs.append(OscMessage(
                                address=str(it.get("address","")).strip(),
                                type=str(it.get("type","")).strip(),
                                value=it.get("value")
                            ))
                    # Allow simple parameter style: { "param": "SpinWin", "value": 1 } => /avatar/parameters/SpinWin
                    if not msgs and isinstance(osc_spec, dict) and osc_spec.get("param"):
                        msgs.append(OscMessage(
                            address=f"/avatar/parameters/{osc_spec.get('param')}",
                            type=str(osc_spec.get("type","int")).strip(),
                            value=osc_spec.get("value", 1)
                        ))
                    if msgs:
                        osc.send_many(msgs)
            except Exception as e:
                print(f"[wheel] award/osc error: {e}")

            # (6) TTS prize line
            win_lines = load_prize_lines(self.settings)
            if win_lines and win_lines[0]:
                win = random.choice(win_lines)
                win = win.replace('{user}', user).replace('{prize}', prize_name)
                win = clamp_reply(sanitize_tts_text(win), 220, 2)
                db.add(QueueItem(kind='tts', status='pending', payload_json={
                    "user": user, "message": win, "prefix": False, "source": "wheel"
                }))

            db.commit()
            return

        # Ignore other kinds here
        print(f"[worker] ignored kind: {kind}")
