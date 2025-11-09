from __future__ import annotations
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


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Joystick Bot — v1.1.0")

    bootstrap()
    settings.sounds_path.mkdir(parents=True, exist_ok=True)

    bus = OverlayBus()

    templates_dir = Path(__file__).parent / "templates"
    static_dir = Path(__file__).parent / "static"
    templates = Jinja2Templates(directory=str(templates_dir))

    app.mount("/admin/static", StaticFiles(directory=str(static_dir)), name="admin_static")
    app.mount("/media/sounds", StaticFiles(directory=str(settings.sounds_path)), name="sounds")

    # Overlay endpoints
    @app.get("/overlay/sfx.html", response_class=HTMLResponse)
    async def overlay_sfx_page(request: Request):
        return templates.TemplateResponse("overlay_sfx.html", {"request": request})

    app.include_router(overlay_ws_router(bus))

    # ---------- Admin Web UI ----------
    admin = APIRouter()

    @admin.get("/", response_class=HTMLResponse)
    async def admin_index(request: Request, db: Session = Depends(get_db)):
        sounds = list_sound_files(settings)
        users = list(db.scalars(select(User).order_by(User.last_seen.desc()).limit(10)))
        redeems = RedeemsService(db)
        redeems.seed_defaults()
        return templates.TemplateResponse("admin_index_v110.html", {
            "request": request,
            "sounds": sounds,
            "users": users,
            "redeems": redeems.list(),
        })

    # SFX test
    @admin.post("/api/play-test")
    async def api_play_test(request: Request):
        _admin_auth(settings, request)
        sounds = list_sound_files(settings)
        if not sounds:
            raise HTTPException(status_code=404, detail="No sound files found in SOUNDS_DIR")
        await play_sfx(bus, sounds[0])
        return JSONResponse({"ok": True, "played": sounds[0]})

    @admin.post("/api/play")
    async def api_play_named(request: Request, name: str):
        _admin_auth(settings, request)
        final = validate_sound_file(settings, name)
        await play_sfx(bus, final)
        return JSONResponse({"ok": True, "played": final})

    # Users
    @admin.post("/api/users/create")
    async def api_users_create(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
        _admin_auth(settings, request)
        ps = PointsService(db)
        u = ps.ensure_user(name=name)
        return RedirectResponse(url="/admin", status_code=303)

    @admin.post("/api/users/grant")
    async def api_users_grant(request: Request, user_id: int = Form(...), amount: int = Form(...), reason: str = Form("admin grant"), db: Session = Depends(get_db)):
        _admin_auth(settings, request)
        ps = PointsService(db)
        ps.grant(user_id=user_id, amount=amount, reason=reason)
        return RedirectResponse(url="/admin", status_code=303)

    # Redeems CRUD
    @admin.post("/api/redeems/upsert")
    async def api_redeems_upsert(request: Request, key: str = Form(...), display_name: str = Form(...), cost: int = Form(...), enabled: int = Form(1), db: Session = Depends(get_db)):
        _admin_auth(settings, request)
        rs = RedeemsService(db)
        rs.upsert(key=key.strip().lower(), display_name=display_name.strip(), cost=int(cost), enabled=bool(enabled))
        return RedirectResponse(url="/admin", status_code=303)

    @admin.post("/api/redeems/toggle")
    async def api_redeems_toggle(request: Request, key: str = Form(...), enabled: int = Form(...), db: Session = Depends(get_db)):
        _admin_auth(settings, request)
        rs = RedeemsService(db)
        rs.toggle(key, bool(enabled))
        return RedirectResponse(url="/admin", status_code=303)

    # Test a redeem (deduct points, set cooldown, enqueue)
    @admin.post("/api/redeems/test")
    async def api_redeems_test(request: Request, user_name: str = Form(...), key: str = Form(...), cooldown: int = Form(5), db: Session = Depends(get_db)):
        _admin_auth(settings, request)
        rs = RedeemsService(db)
        rs.seed_defaults()
        result = rs.redeem(user_name=user_name.strip(), key=key.strip(), cooldown_s=int(cooldown), queue_kind=key.strip(), payload={"source":"admin-test"})
        if not result.get("ok"):
            return JSONResponse(result, status_code=400)
        return RedirectResponse(url="/admin", status_code=303)

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

    app.include_router(admin, prefix="/admin", tags=["admin"])

    @app.get("/")
    async def root():
        return RedirectResponse(url="/admin")

    return app
