from __future__ import annotations
import asyncio, random
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Depends, Request, status, Form
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import bootstrap, SessionLocal
from app.core.overlay_bus import OverlayBus, overlay_ws_router
from app.core.sfx import list_sound_files, validate_sound_file, play_sfx
from app.core.models import User, Points, Transaction, Redeem, QueueItem, Cooldown
from app.core.points import PointsService
from app.core.items import ItemsService
from app.core.redeems import RedeemsService
from app.core.cooldowns import CooldownService
from app.core.queue import QueueService
from app.core.joystick import JoystickClient, JoystickCallbacks
from app.core.router import handle_chat, is_command
from app.core.consumers import QueueWorker
from app.core.tts import TTSService


# Globals tied to app lifecycle
_bus: OverlayBus | None = None
_js: JoystickClient | None = None
_settings: Settings | None = None
_bg_tasks: list[asyncio.Task] = []
_worker: QueueWorker | None = None


def _admin_auth(settings: Settings, request: Request) -> None:
    token = settings.ADMIN_TOKEN.strip()
    if not token:
        return
    provided = request.headers.get("X-Admin-Token", "").strip()
    if not provided:
        provided = request.query_params.get("token", "").strip()
    if provided != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


def _admin_redirect(request: Request) -> RedirectResponse:
    """Redirect back to /admin, preserving ?token=... if present."""
    token = request.query_params.get("token", "").strip()
    url = "/admin"
    if token:
        url = f"{url}?token={token}"
    return RedirectResponse(url=url, status_code=303)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def _post_chat(text: str) -> None:
    global _js
    if _js:
        await _js.send_chat(text)
    else:
        print("[chat]", text)


async def _maybe_random_pixel(user: str, text: str) -> None:
    """Occasionally reply to normal chat (not commands), cost-free.
    Enqueues a 'pixel' job that flows into TTS. Probability controlled by env.
    """
    global _settings
    if not text or is_command(text):
        return
    prob = max(0.0, min(1.0, float(_settings.PPLX_RANDOM_REPLY_PROB)))
    if random.random() > prob:
        return
    with SessionLocal() as db:
        rs = RedeemsService(db)
        rs.seed_defaults()
        payload = {"user": user, "message": text}
        # Enqueue directly without point deduction or cooldown (random replies)
        rs.queue.enqueue("pixel", payload)


async def _on_chat(user: str, text: str):
    global _settings
    with SessionLocal() as db:
        result = handle_chat(db, _settings, user, text)
        say = result.get("say")
        if say:
            await _post_chat(f"@{user} {say}")
    # Try random Pixel after command handling so we don't respond to commands
    await _maybe_random_pixel(user, text)


async def _on_follow(user: str):
    with SessionLocal() as db:
        ps = PointsService(db)
        u = ps.ensure_user(user)
        ps.grant(u.id, amount=50, reason="follow")
        await _post_chat(f"Welcome @{user}! (+50 points)")


async def _on_sub(user: str, months: int):
    with SessionLocal() as db:
        ps = PointsService(db)
        u = ps.ensure_user(user)
        ps.grant(u.id, amount=200, reason=f"sub:{months}m")
        await _post_chat(f"Thanks for the sub @{user}! (+200 points)")


async def _on_tip(user: str, tokens: int):
    global _settings
    with SessionLocal() as db:
        ps = PointsService(db)
        u = ps.ensure_user(user)
        if tokens <= _settings.TIP_LOW_MAX:
            amt, tier = 25, 'low'
        elif tokens <= _settings.TIP_MEDIUM_MAX:
            amt, tier = 150, 'medium'
        elif tokens <= _settings.TIP_HIGH_MAX:
            amt, tier = 500, 'high'
        else:
            amt, tier = 1500, 'extreme'
        ps.grant(u.id, amount=amt, reason=f"tip:{tokens}:{tier}")
        await _post_chat(f"Thanks @{user} for the tip ({tokens})! +{amt} points")


async def _on_dropin(user: str):
    with SessionLocal() as db:
        ps = PointsService(db)
        u = ps.ensure_user(user)
        ps.grant(u.id, amount=5, reason="dropin")
        await _post_chat(f"Hello @{user}! (+5 points)")


async def _rotate_notices():
    global _settings
    while True:
        await asyncio.sleep(max(30, _settings.ROTATE_NOTICE_SECONDS))
        await _post_chat("Try !help — TTS, Pixel, Sound, Spin, Clip!")


def create_app(settings: Settings) -> FastAPI:
    global _bus, _js, _settings, _bg_tasks, _worker
    _settings = settings

    app = FastAPI(title="Joystick Bot — v1.9.0")

    bootstrap()
    settings.sounds_path.mkdir(parents=True, exist_ok=True)

    _bus = OverlayBus()

    templates_dir = Path(__file__).parent / "templates"
    static_dir = Path(__file__).parent / "static"
    templates = Jinja2Templates(directory=str(templates_dir))

    app.mount("/admin/static", StaticFiles(directory=str(static_dir)), name="admin_static")
    app.mount("/media/sounds", StaticFiles(directory=str(settings.sounds_path)), name="sounds")

    # Overlay endpoints
    @app.get("/overlay/sfx.html", response_class=HTMLResponse)
    async def overlay_sfx_page(request: Request):
        return templates.TemplateResponse("overlay_sfx.html", {"request": request})

    @app.get("/overlay/wheel.html", response_class=HTMLResponse)
    async def overlay_wheel_page(request: Request):
        return templates.TemplateResponse("overlay_wheel.html", {"request": request})

    app.include_router(overlay_ws_router(_bus))

    # ---------- Admin Web UI ----------
    admin = APIRouter()

    @admin.get("/", response_class=HTMLResponse)
    async def admin_index(request: Request, db: Session = Depends(get_db)):
        sounds = list_sound_files(settings)
        users = list(db.scalars(select(User).order_by(User.last_seen.desc()).limit(10)))
        redeems = RedeemsService(db)
        redeems.seed_defaults()
        # TTS lines (v1.8.0)
        from app.core.fileops import read_text, list_backups
        data_dir = Path("./data").resolve()
        backups_dir = data_dir / "backups"
        spin_path = Path(settings.SPIN_LINES_FILE)
        prize_path = Path(settings.PRIZE_LINES_FILE)

        spin_txt = read_text(spin_path)
        prize_txt = read_text(prize_path)

        spin_baks = list_backups(backups_dir, "spin_lines", limit=20)
        prize_baks = list_backups(backups_dir, "prize_lines", limit=20)

        # Audit log (v1.9.0)
        ps = PointsService(db)
        txns = ps.list_transactions(limit=50)

        return templates.TemplateResponse("admin_index_v120.html", {
            "request": request,
            "sounds": sounds,
            "users": users,
            "redeems": redeems.list(),
            "spin_lines_text": spin_txt,
            "prize_lines_text": prize_txt,
            "spin_line_backups": spin_baks,
            "prize_line_backups": prize_baks,
            "transactions": txns,
            "sim_mode": (settings.JOYSTICK_TOKEN.strip() == ""),
        })

    # ---------- Users & Points ----------
    @admin.post("/api/users/create")
    async def api_users_create(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
        _admin_auth(settings, request)
        ps = PointsService(db)
        ps.ensure_user(name.strip())
        return _admin_redirect(request)

    @admin.post("/api/users/grant")
    async def api_users_grant(
        request: Request,
        user_id: int = Form(...),
        amount: int = Form(...),
        reason: str = Form("admin"),
        db: Session = Depends(get_db),
    ):
        _admin_auth(settings, request)
        ps = PointsService(db)
        ps.grant(int(user_id), int(amount), reason or "admin")
        return _admin_redirect(request)

    @admin.post("/api/users/adjust")
    async def api_users_adjust(
        request: Request,
        user: str = Form(...),
        delta: int = Form(...),
        reason: str = Form("admin_adjust"),
        db: Session = Depends(get_db),
    ):
        _admin_auth(settings, request)
        ps = PointsService(db)
        u = ps.ensure_user(user.strip())
        ps.adjust(u.id, int(delta), reason or "admin_adjust")
        return _admin_redirect(request)

    @admin.get("/api/users/transactions")
    async def api_users_transactions(user: str | None = None, limit: int = 50, db: Session = Depends(get_db)):
        ps = PointsService(db)
        user_id = None
        if user:
            u = ps.ensure_user(user)
            user_id = u.id
        txns = ps.list_transactions(user_id=user_id, limit=limit)
        out = [
            {
                "id": t.id,
                "user_id": t.user_id,
                "type": t.type,
                "delta": t.delta,
                "reason": t.reason,
                "created_at": t.created_at.isoformat(timespec="seconds"),
            }
            for t in txns
        ]
        return JSONResponse({"items": out})

    # ---------- Redeems (v1.9.0) ----------
    @admin.post("/api/redeems/upsert")
    async def api_redeems_upsert(
        request: Request,
        key: str = Form(...),
        display_name: str = Form(...),
        cost: int = Form(0),
        cooldown_s: int = Form(0),
        enabled: list[str] = Form([]),
        db: Session = Depends(get_db),
    ):
        _admin_auth(settings, request)
        rs = RedeemsService(db)
        enabled_bool = any(str(v) == "1" for v in (enabled or []))
        rs.upsert(key=key.strip(), display_name=display_name.strip(), cost=int(cost), cooldown_s=int(cooldown_s), enabled=enabled_bool)
        return _admin_redirect(request)

    @admin.post("/api/redeems/toggle")
    async def api_redeems_toggle(request: Request, key: str = Form(...), enabled: int = Form(...), db: Session = Depends(get_db)):
        _admin_auth(settings, request)
        rs = RedeemsService(db)
        rs.toggle(key=key.strip(), enabled=bool(int(enabled)))
        return _admin_redirect(request)

    # ---------- TTS lines editor (v1.8.0) ----------
    @admin.post("/api/tts-lines/save")
    async def api_tts_lines_save(
        request: Request,
        kind: str = Form(...),
        content: str = Form(""),
    ):
        _admin_auth(settings, request)
        from app.core.fileops import write_text_with_backup

        kind = (kind or "").lower().strip()
        data_dir = Path("./data").resolve()
        backups_dir = data_dir / "backups"
        if kind == "spin":
            path = Path(settings.SPIN_LINES_FILE)
            prefix = "spin_lines"
        elif kind == "prize":
            path = Path(settings.PRIZE_LINES_FILE)
            prefix = "prize_lines"
        else:
            raise HTTPException(status_code=400, detail="Invalid kind")

        write_text_with_backup(path, content or "", backup_dir=backups_dir, prefix=prefix, keep=25)
        return _admin_redirect(request)

    @admin.post("/api/tts-lines/restore")
    async def api_tts_lines_restore(
        request: Request,
        kind: str = Form(...),
        backup_name: str = Form(...),
    ):
        _admin_auth(settings, request)
        from app.core.fileops import restore_backup

        kind = (kind or "").lower().strip()
        data_dir = Path("./data").resolve()
        backups_dir = data_dir / "backups"

        if kind == "spin":
            path = Path(settings.SPIN_LINES_FILE)
            prefix = "spin_lines"
        elif kind == "prize":
            path = Path(settings.PRIZE_LINES_FILE)
            prefix = "prize_lines"
        else:
            raise HTTPException(status_code=400, detail="Invalid kind")

        bfile = backups_dir / backup_name
        if not bfile.exists() or not bfile.name.startswith(prefix + "_"):
            raise HTTPException(status_code=404, detail="Backup not found")
        restore_backup(path, bfile)
        return _admin_redirect(request)

    # SFX test
    @admin.post("/api/play-test")
    async def api_play_test(request: Request):
        _admin_auth(settings, request)
        sounds = list_sound_files(settings)
        if not sounds:
            raise HTTPException(status_code=404, detail="No sound files found in SOUNDS_DIR")
        await play_sfx(_bus, sounds[0])
        return JSONResponse({"ok": True, "played": sounds[0]})

    @admin.post("/api/play")
    async def api_play_named(request: Request, name: str):
        _admin_auth(settings, request)
        final = validate_sound_file(settings, name)
        await play_sfx(_bus, final)
        return JSONResponse({"ok": True, "played": final})

    # Chat console (Dev/Sim)
    @admin.post("/api/sim/chat")
    async def api_sim_chat(request: Request, user: str = Form(...), text: str = Form(...)):
        _admin_auth(settings, request)
        if _js:
            await _js.sim_push_chat(user, text)
        return _admin_redirect(request)

    @admin.post("/api/sim/event")
    async def api_sim_event(request: Request, kind: str = Form(...), user: str = Form("Tester"), tokens: int = Form(0), months: int = Form(1)):
        _admin_auth(settings, request)
        if not _js:
            return _admin_redirect(request)
        if kind == "follow":
            await _js.sim_push_follow(user)
        elif kind == "sub":
            await _js.sim_push_sub(user, months)
        elif kind == "tip":
            await _js.sim_push_tip(user, tokens)
        elif kind == "dropin":
            await _js.sim_push_dropin(user)
        return _admin_redirect(request)

    # Queue listing API
    @admin.get("/api/queue")
    async def api_queue(db: Session = Depends(get_db)):
        qs = QueueService(db)
        items = [
            {
                "id": q.id,
                "kind": q.kind,
                "status": q.status,
                "created_at": q.created_at.isoformat(timespec="seconds"),
                "payload": q.payload_json,
            } for q in qs.list()
        ]
        return JSONResponse({"items": items})

    # ---------- Items (Admin-only) ----------
    @admin.post("/api/items/upsert")
    async def api_items_upsert(
        request: Request,
        key: str = Form(...),
        name: str = Form(...),
        description: str = Form(""),
        enabled: list[str] = Form([]),
        db: Session = Depends(get_db),
    ):
        _admin_auth(settings, request)
        svc = ItemsService(db)
        enabled_bool = any(str(v) == "1" for v in (enabled or []))
        svc.upsert_item(key=key, name=name, description=description, enabled=enabled_bool)
        return _admin_redirect(request)

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
        return _admin_redirect(request)

    @admin.get("/api/items/inventory")
    async def api_items_inventory(user: str, db: Session = Depends(get_db)):
        svc = ItemsService(db)
        ps = PointsService(db)
        u = ps.ensure_user(user)
        inv = svc.get_inventory(u.id)
        out = [{"item_key": x.item_key, "qty": x.qty} for x in inv]
        return JSONResponse({"user": u.name, "items": out})

    # ---------- Quick Spin Tester (no points/cooldown) ----------
    @admin.post("/api/spin/quick")
    async def api_spin_quick(request: Request, user: str = Form("Tester"), db: Session = Depends(get_db)):
        _admin_auth(settings, request)
        qs = QueueService(db)
        qid = qs.enqueue("spin", {"user": user, "quick": True})
        return JSONResponse({"ok": True, "queue_id": qid, "user": user})

    app.include_router(admin, prefix="/admin", tags=["admin"])

    # ---------- TTS endpoints ----------
    @app.get("/tts/plain-next", response_class=PlainTextResponse)
    async def tts_plain_next():
        with SessionLocal() as db:
            svc = TTSService(db, settings, _bus)
            text = await svc.next_plain()
            return text

    @app.get("/tts/text-next")
    async def tts_text_next():
        with SessionLocal() as db:
            svc = TTSService(db, settings, _bus)
            text = await svc.next_plain()
            return {"text": text}

    @app.get("/")
    async def root():
        return RedirectResponse(url="/admin")

    # --- Startup tasks ---
    @app.on_event("startup")
    async def _on_startup():
        global _js, _bg_tasks, _worker
        _js = JoystickClient(settings.JOYSTICK_TOKEN, settings.JOYSTICK_ROOM_ID)
        _js.set_callbacks(JoystickCallbacks(
            on_chat=_on_chat,
            on_follow=_on_follow,
            on_sub=_on_sub,
            on_tip=_on_tip,
            on_dropin=_on_dropin,
        ))
        await _js.start()

        _bg_tasks.append(asyncio.create_task(_rotate_notices()))
        _worker = QueueWorker(_bus, settings)
        _bg_tasks.append(asyncio.create_task(_worker.start()))

    @app.on_event("shutdown")
    async def _on_shutdown():
        global _js, _bg_tasks, _worker
        for t in _bg_tasks:
            t.cancel()
        _bg_tasks.clear()
        if _js:
            await _js.stop()
        if _worker:
            _worker.stop()

    return app
