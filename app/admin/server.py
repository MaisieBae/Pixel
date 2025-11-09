from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Depends, Request, status, Form
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
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
from app.core.redeems import RedeemsService
from app.core.cooldowns import CooldownService
from app.core.queue import QueueService
from app.core.joystick import JoystickClient, JoystickCallbacks
from app.core.router import handle_chat


# Globals tied to app lifecycle
_bus: OverlayBus | None = None
_js: JoystickClient | None = None
_settings: Settings | None = None
_bg_tasks: list[asyncio.Task] = []


def _admin_auth(settings: Settings, request: Request) -> None:
    token = settings.ADMIN_TOKEN.strip()
    if not token:
        return
    provided = request.headers.get("X-Admin-Token", "").strip()
    if provided != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


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


async def _on_chat(user: str, text: str):
    global _settings
    with SessionLocal() as db:
        result = handle_chat(db, _settings, user, text)
        say = result.get("say")
        if say:
            await _post_chat(f"@{user} {say}")


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
        # Map tokens to tiers — values configurable in .env
        amt = 25
        if tokens <= _settings.TIP_LOW_MAX:
            amt = 25
            tier = "low"
        elif tokens <= _settings.TIP_MEDIUM_MAX:
            amt = 150
            tier = "medium"
        elif tokens <= _settings.TIP_HIGH_MAX:
            amt = 500
            tier = "high"
        else:
            amt = 1500
            tier = "extreme"
        ps.grant(u.id, amount=amt, reason=f"tip:{tokens}:{tier}")
        await _post_chat(f"Thanks @{user} for the tip ({tokens})! +{amt} points")


async def _on_dropin(user: str):
    with SessionLocal() as db:
        ps = PointsService(db)
        u = ps.ensure_user(user)
        ps.grant(u.id, amount=5, reason="dropin")
        await _post_chat(f"Hello @{user}! (+5 points)")


async def _rotate_notices():
    global _js, _settings
    while True:
        await asyncio.sleep(max(30, _settings.ROTATE_NOTICE_SECONDS))
        await _post_chat("Try !help — TTS, Pixel, Sound, Spin, Clip!")


def create_app(settings: Settings) -> FastAPI:
    global _bus, _js, _settings, _bg_tasks
    _settings = settings

    app = FastAPI(title="Joystick Bot — v1.2.0")

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

    app.include_router(overlay_ws_router(_bus))

    # ---------- Admin Web UI ----------
    admin = APIRouter()

    @admin.get("/", response_class=HTMLResponse)
    async def admin_index(request: Request, db: Session = Depends(get_db)):
        sounds = list_sound_files(settings)
        users = list(db.scalars(select(User).order_by(User.last_seen.desc()).limit(10)))
        redeems = RedeemsService(db)
        redeems.seed_defaults()
        return templates.TemplateResponse("admin_index_v120.html", {
            "request": request,
            "sounds": sounds,
            "users": users,
            "redeems": redeems.list(),
            "sim_mode": (settings.JOYSTICK_TOKEN.strip() == ""),
        })

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
        return RedirectResponse(url="/admin", status_code=303)

    @admin.post("/api/sim/event")
    async def api_sim_event(request: Request, kind: str = Form(...), user: str = Form("Tester"), tokens: int = Form(0), months: int = Form(1)):
        _admin_auth(settings, request)
        if not _js:
            return RedirectResponse(url="/admin", status_code=303)
        if kind == "follow":
            await _js.sim_push_follow(user)
        elif kind == "sub":
            await _js.sim_push_sub(user, months)
        elif kind == "tip":
            await _js.sim_push_tip(user, tokens)
        elif kind == "dropin":
            await _js.sim_push_dropin(user)
        return RedirectResponse(url="/admin", status_code=303)

    app.include_router(admin, prefix="/admin", tags=["admin"])

    @app.get("/")
    async def root():
        return RedirectResponse(url="/admin")

    # --- Startup tasks ---
    @app.on_event("startup")
    async def _on_startup():
        global _js, _bg_tasks
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

    @app.on_event("shutdown")
    async def _on_shutdown():
        global _js, _bg_tasks
        for t in _bg_tasks:
            t.cancel()
        _bg_tasks.clear()
        if _js:
            await _js.stop()

    return app
