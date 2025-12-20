from __future__ import annotations

"""Admin + app factory.

Important project rule: never remove existing wiring "to simplify".
This module intentionally contains:
  - Admin UI routes
  - Overlay websocket router
  - TTS endpoints
  - Joystick callbacks + sim console
  - QueueWorker startup/shutdown
"""

import asyncio
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.consumers import QueueWorker
from app.core.db import SessionLocal
from app.core.items import ItemsService
from app.core.joystick import JoystickCallbacks, JoystickClient
from app.core.models import QueueItem, User
from app.core.overlay_bus import OverlayBus, overlay_ws_router
from app.core.points import PointsService
from app.core.queue import QueueService
from app.core.redeems import RedeemsService
from app.core.router import handle_chat
from app.core.tts import TTSService


# -----------------
# Globals (kept simple)
# -----------------
_bus: OverlayBus | None = None
_js: JoystickClient | None = None
_worker: QueueWorker | None = None
_bg_tasks: list[asyncio.Task[Any]] = []


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _admin_auth(settings: Settings, request: Request) -> None:
    """Optional admin token gate."""
    token = request.headers.get("x-admin-token") or request.query_params.get("token") or ""
    expected = getattr(settings, "ADMIN_TOKEN", "") or ""
    if expected and token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def mount_admin(app: FastAPI, settings: Settings) -> None:
    admin = APIRouter(prefix="/admin")
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

    # ---------- Admin Index ----------
    @admin.get("", response_class=HTMLResponse)
    async def admin_index(request: Request, db: Session = Depends(get_db)):
        rs = RedeemsService(db)
        rs.seed_defaults()

        users = list(db.scalars(select(User).order_by(User.last_seen.desc()).limit(25)))
        redeems = rs.list()
        items = ItemsService(db).list_items()

        return templates.TemplateResponse(
            "admin_index_v120.html",
            {"request": request, "users": users, "redeems": redeems, "items": items},
        )

    # ---------- TTS Lines Editor (Spin/Prize) ----------
    def _tts_paths() -> tuple[Path, Path, Path]:
        data_dir = Path("./data")
        spin_path = data_dir / "spin_lines.txt"
        prize_path = data_dir / "prize_lines.txt"
        backups_dir = data_dir / "backups"
        return spin_path, prize_path, backups_dir

    @admin.get("/api/tts-lines/get")
    async def api_tts_lines_get(request: Request):
        _admin_auth(settings, request)
        from app.core.fileops import list_backups, read_text_file

        spin_path, prize_path, backups_dir = _tts_paths()
        return JSONResponse(
            {
                "ok": True,
                "spin_lines": read_text_file(spin_path),
                "prize_lines": read_text_file(prize_path),
                "spin_backups": [b.name for b in list_backups(backups_dir, "spin_lines")],
                "prize_backups": [b.name for b in list_backups(backups_dir, "prize_lines")],
            }
        )

    @admin.post("/api/tts-lines/save")
    async def api_tts_lines_save(
        request: Request,
        spin_lines: str = Form(""),
        prize_lines: str = Form(""),
    ):
        _admin_auth(settings, request)
        from app.core.fileops import make_backup, write_text_file

        spin_path, prize_path, backups_dir = _tts_paths()
        # backup current before overwrite
        make_backup(spin_path, backups_dir, "spin_lines")
        make_backup(prize_path, backups_dir, "prize_lines")
        write_text_file(spin_path, spin_lines)
        write_text_file(prize_path, prize_lines)
        return JSONResponse({"ok": True})

    @admin.post("/api/tts-lines/restore")
    async def api_tts_lines_restore(request: Request, which: str = Form(...), backup_name: str = Form(...)):
        _admin_auth(settings, request)
        from app.core.fileops import read_text_file, write_text_file

        spin_path, prize_path, backups_dir = _tts_paths()
        which = (which or "").strip().lower()
        if which not in ("spin", "prize"):
            raise HTTPException(status_code=400, detail="Invalid 'which'")

        target = spin_path if which == "spin" else prize_path
        prefix = "spin_lines" if which == "spin" else "prize_lines"
        bpath = backups_dir / Path(backup_name).name
        if not bpath.exists() or not bpath.name.startswith(prefix):
            raise HTTPException(status_code=400, detail="Invalid backup")
        write_text_file(target, read_text_file(bpath))
        return JSONResponse({"ok": True})

    # ---------- Sim Console ----------
    @admin.post("/api/sim/chat")
    async def api_sim_chat(
        request: Request,
        user: str = Form("Tester"),
        message: str = Form(""),
    ):
        _admin_auth(settings, request)
        global _js
        if _js:
            await _js.sim_push_chat(user, message)
        return JSONResponse({"ok": True})

    @admin.post("/api/sim/event")
    async def api_sim_event(
        request: Request,
        kind: str = Form(...),
        user: str = Form("Tester"),
        tokens: int = Form(0),
        months: int = Form(1),
    ):
        _admin_auth(settings, request)
        global _js
        k = (kind or "").strip().lower()
        if _js:
            if k == "follow":
                await _js.sim_push_follow(user)
            elif k == "dropin":
                await _js.sim_push_dropin(user)
            elif k == "sub":
                await _js.sim_push_sub(user, int(months))
            elif k == "tip":
                await _js.sim_push_tip(user, int(tokens))
        return JSONResponse({"ok": True})

    # ---------- Quick Spin Tester (no points/cooldown) ----------
    @admin.post("/api/spin/quick")
    async def api_spin_quick(request: Request, user: str = Form("Tester"), db: Session = Depends(get_db)):
        _admin_auth(settings, request)
        qs = QueueService(db)
        qid = qs.enqueue("spin", {"user": user, "quick": True})
        return JSONResponse({"ok": True, "queue_id": qid, "user": user})

    # ---------- Items ----------
    @admin.post("/api/items/upsert")
    async def api_items_upsert(
        request: Request,
        key: str = Form(...),
        name: str = Form(...),
        description: str = Form(""),
        enabled: int = Form(1),
        db: Session = Depends(get_db),
    ):
        _admin_auth(settings, request)
        svc = ItemsService(db)
        svc.upsert_item(key=key, name=name, description=description, enabled=bool(int(enabled)))
        return RedirectResponse(url="/admin", status_code=303)

    @admin.post("/api/items/grant")
    async def api_items_grant(
        request: Request,
        user: str = Form(...),
        item_key: str = Form(...),
        qty: int = Form(1),
        db: Session = Depends(get_db),
    ):
        _admin_auth(settings, request)
        ps = PointsService(db)
        isvc = ItemsService(db)
        u = ps.ensure_user(user)
        isvc.grant_item(u.id, item_key, qty=int(qty))
        return RedirectResponse(url="/admin", status_code=303)

    @admin.get("/api/items/inventory")
    async def api_items_inventory(user: str, db: Session = Depends(get_db)):
        svc = ItemsService(db)
        ps = PointsService(db)
        u = ps.ensure_user(user)
        inv = svc.get_inventory(u.id)
        out = [{"item_key": x.item_key, "qty": x.qty} for x in inv]
        return JSONResponse({"user": u.name, "items": out})

    # ---------- Users / Points ----------
    @admin.post("/api/users/create")
    async def api_users_create(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
        _admin_auth(settings, request)
        ps = PointsService(db)
        u = ps.ensure_user(name.strip())
        return JSONResponse({"ok": True, "user": {"id": u.id, "name": u.name}})

    @admin.post("/api/users/grant")
    async def api_users_grant(
        request: Request,
        user_id: int = Form(...),
        amount: int = Form(...),
        reason: str = Form("admin"),
        db: Session = Depends(get_db),
    ):
        _admin_auth(settings, request)
        u = db.get(User, int(user_id))
        if u is None:
            return JSONResponse({"ok": False, "error": "User not found"}, status_code=404)
        ps = PointsService(db)
        new_bal = ps.grant(u.id, amount=int(amount), reason=str(reason or "admin"))
        return JSONResponse({"ok": True, "user": {"id": u.id, "name": u.name}, "new_balance": new_bal})

    @admin.post("/api/users/adjust")
    async def api_users_adjust(
        request: Request,
        user_id: int = Form(...),
        delta: int = Form(...),
        reason: str = Form("admin_adjust"),
        db: Session = Depends(get_db),
    ):
        _admin_auth(settings, request)
        u = db.get(User, int(user_id))
        if u is None:
            return JSONResponse({"ok": False, "error": "User not found"}, status_code=404)
        ps = PointsService(db)
        new_bal = ps.adjust(u.id, delta=int(delta), reason=str(reason or "admin_adjust"), allow_negative_balance=False)
        return JSONResponse({"ok": True, "user": {"id": u.id, "name": u.name}, "delta": int(delta), "new_balance": new_bal})

    @admin.get("/api/users/transactions")
    async def api_users_transactions(
        request: Request,
        user_id: int,
        limit: int = 50,
        db: Session = Depends(get_db),
    ):
        _admin_auth(settings, request)
        u = db.get(User, int(user_id))
        if u is None:
            return JSONResponse({"ok": False, "error": "User not found"}, status_code=404)
        ps = PointsService(db)
        rows = ps.list_transactions(user_id=u.id, limit=int(limit))
        return JSONResponse(
            {
                "ok": True,
                "user": {"id": u.id, "name": u.name},
                "transactions": [
                    {
                        "id": r.id,
                        "type": r.type,
                        "delta": r.delta,
                        "reason": r.reason,
                        "created_at": r.created_at.isoformat() + "Z",
                    }
                    for r in rows
                ],
            }
        )

    # ---------- Redeems CRUD ----------
    @admin.post("/api/redeems/upsert")
    async def api_redeems_upsert(
        request: Request,
        key: str = Form(...),
        display_name: str = Form(...),
        cost: int = Form(...),
        enabled: bool = Form(True),
        cooldown_s: int = Form(0),
        db: Session = Depends(get_db),
    ):
        _admin_auth(settings, request)
        rs = RedeemsService(db)
        rs.seed_defaults()
        r = rs.upsert(key.strip(), display_name.strip(), int(cost), bool(enabled), cooldown_s=int(cooldown_s or 0))
        return JSONResponse(
            {
                "ok": True,
                "redeem": {
                    "key": r.key,
                    "display_name": r.display_name,
                    "cost": r.cost,
                    "enabled": r.enabled,
                    "cooldown_s": getattr(r, "cooldown_s", 0),
                },
            }
        )

    @admin.post("/api/redeems/toggle")
    async def api_redeems_toggle(
        request: Request,
        key: str = Form(...),
        enabled: bool = Form(...),
        db: Session = Depends(get_db),
    ):
        _admin_auth(settings, request)
        rs = RedeemsService(db)
        rs.seed_defaults()
        rs.toggle(key.strip(), bool(enabled))
        return JSONResponse({"ok": True, "key": key, "enabled": bool(enabled)})

    @admin.get("/api/redeems/list")
    async def api_redeems_list(request: Request, db: Session = Depends(get_db)):
        _admin_auth(settings, request)
        rs = RedeemsService(db)
        rs.seed_defaults()
        return JSONResponse({"ok": True, "redeems": rs.list()})

    app.include_router(admin)


def create_app(settings: Settings) -> FastAPI:
    """Create the full FastAPI app (wiring preserved)."""
    global _bus, _js, _worker, _bg_tasks

    app = FastAPI(title="Joystick Bot — v1.9.0")

    # Overlay bus + websocket router
    _bus = OverlayBus()
    app.include_router(overlay_ws_router(_bus))

    # Admin routes
    mount_admin(app, settings)

    # ---------- TTS endpoints ----------
    @app.get("/tts/plain-next", response_class=PlainTextResponse)
    async def tts_plain_next():
        assert _bus is not None
        with SessionLocal() as db:
            svc = TTSService(db, settings, _bus)
            text = await svc.next_plain()
            return text

    @app.get("/tts/text-next")
    async def tts_text_next():
        assert _bus is not None
        with SessionLocal() as db:
            svc = TTSService(db, settings, _bus)
            text = await svc.next_plain()
            return {"text": text}

    @app.get("/")
    async def root():
        return RedirectResponse(url="/admin")

    # ---------- Joystick callbacks ----------
    async def _on_chat(user: str, text: str) -> None:
        """Handle incoming chat.

        - Commands/redeems handled by handle_chat()
        - Random Pixel replies are handled here (probability in settings)
        """
        with SessionLocal() as db:
            result = handle_chat(db, settings, user, text)

            # Speak immediate system responses (help, errors, etc.)
            say = result.get("say")
            if say:
                db.add(
                    QueueItem(
                        kind="tts",
                        status="pending",
                        payload_json={
                            "user": user,
                            "message": str(say),
                            "prefix": False,
                            "source": "system",
                        },
                    )
                )
                db.commit()

            # Random Pixel response (missing in current repo before this fix)
            # Only for non-commands to avoid replying to !help, !spin, etc.
            if text.strip().startswith("!"):
                return

            p = float(getattr(settings, "PPLX_RANDOM_REPLY_PROB", 0.0) or 0.0)
            if p <= 0:
                return
            if random.random() >= p:
                return

            # Enqueue Pixel job (free; does not spend points)
            db.add(
                QueueItem(
                    kind="pixel",
                    status="pending",
                    payload_json={"user": user, "message": text, "source": "random"},
                )
            )
            db.commit()

    async def _on_follow(user: str) -> None:
        return

    async def _on_sub(user: str, months: int) -> None:
        return

    async def _on_tip(user: str, tokens: int) -> None:
        return

    async def _on_dropin(user: str) -> None:
        return

    # --- Startup tasks ---
    @app.on_event("startup")
    async def _on_startup():
        global _js, _worker, _bg_tasks
        assert _bus is not None

        _js = JoystickClient(settings.JOYSTICK_TOKEN, settings.JOYSTICK_ROOM_ID)
        _js.set_callbacks(
            JoystickCallbacks(
                on_chat=_on_chat,
                on_follow=_on_follow,
                on_sub=_on_sub,
                on_tip=_on_tip,
                on_dropin=_on_dropin,
            )
        )
        await _js.start()

        _worker = QueueWorker(_bus, settings)
        _bg_tasks.append(asyncio.create_task(_worker.start()))

    @app.on_event("shutdown")
    async def _on_shutdown():
        global _js, _worker, _bg_tasks
        for t in _bg_tasks:
            t.cancel()
        _bg_tasks.clear()
        if _js:
            await _js.stop()
        if _worker:
            _worker.stop()

    return app
