from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Server
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8080

    # Admin security (optional)
    ADMIN_TOKEN: str = ""

    # Media / Overlay
    SOUNDS_DIR: str = "./sounds"

    # Joystick
    JOYSTICK_TOKEN: str = ""
    JOYSTICK_ROOM_ID: str = ""   # set if your integration needs it

    # Rotating notices
    ROTATE_NOTICE_SECONDS: int = 300

    # Tip tiers (inclusive upper bounds)
    TIP_LOW_MAX: int = 14
    TIP_MEDIUM_MAX: int = 100
    TIP_HIGH_MAX: int = 500
    TIP_EXTREME_MAX: int = 1000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sounds_path(self) -> Path:
        return Path(self.SOUNDS_DIR).resolve()