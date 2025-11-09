from __future__ import annotations
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Depends, Request, status
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import Settings
from app.core.db import bootstrap
from app.core.overlay_bus import OverlayBus, overlay_ws_router
from app.core.sfx import list_sound_files, validate_sound_file, play_sfx


def _admin_auth(settings: Settings, request: Request) -> None:
    # If ADMIN_TOKEN is set, enforce X-Admin-Token for mutations.
    token = settings.ADMIN_TOKEN.strip()
    if not token:
        return
    provided = request.headers.get("X-Admin-Token", "").strip()
    if provided != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Joystick Bot — v1.0.0")

    # Bootstrap DB and folders
    bootstrap()
    settings.sounds_path.mkdir(parents=True, exist_ok=True)

    # Shared overlay bus
    bus = OverlayBus()

    # Templates & Static
    templates_dir = Path(__file__).parent / "templates"
    static_dir = Path(__file__).parent / "static"
    templates = Jinja2Templates(directory=str(templates_dir))

    # Static routes
    app.mount("/admin/static", StaticFiles(directory=str(static_dir)), name="admin_static")

    # Serve sounds as static files to overlay
    app.mount("/media/sounds", StaticFiles(directory=str(settings.sounds_path)), name="sounds")

    # Overlay: SFX page (OBS browser source)
    @app.get("/overlay/sfx.html", response_class=HTMLResponse)
    async def overlay_sfx_page(request: Request):
        return templates.TemplateResponse("overlay_sfx.html", {"request": request})

    # WebSocket endpoint for overlays
    app.include_router(overlay_ws_router(bus))

    # ---------- Admin Web UI ----------
    admin_router = APIRouter()

    @admin_router.get("/", response_class=HTMLResponse)
    async def admin_index(request: Request):
        sounds = list_sound_files(settings)
        return templates.TemplateResponse("admin_index.html", {"request": request, "sounds": sounds})

    @admin_router.post("/api/play-test")
    async def api_play_test(request: Request):
        _admin_auth(settings, request)
        # Pick a default file if present, else 404
        sounds = list_sound_files(settings)
        if not sounds:
            raise HTTPException(status_code=404, detail="No sound files found in SOUNDS_DIR")
        await play_sfx(bus, sounds[0])
        return JSONResponse({"ok": True, "played": sounds[0]})

    @admin_router.post("/api/play")
    async def api_play_named(request: Request, name: str):
        _admin_auth(settings, request)
        final = validate_sound_file(settings, name)
        await play_sfx(bus, final)
        return JSONResponse({"ok": True, "played": final})

    @admin_router.get("/api/sounds")
    async def api_list_sounds():
        return JSONResponse({"files": list_sound_files(settings)})

    app.include_router(admin_router, prefix="/admin", tags=["admin"])

    # Root redirect to admin
    @app.get("/")
    async def root():
        return RedirectResponse(url="/admin")

    return app