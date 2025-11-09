from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Server
    APP_HOST: str = "0.0.0.0"           # LAN accessible
    APP_PORT: int = 8080

    # Admin security (optional)
    ADMIN_TOKEN: str = ""               # if non-empty, require X-Admin-Token on mutating endpoints

    # Media / Overlay
    SOUNDS_DIR: str = "./sounds"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sounds_path(self) -> Path:
        return Path(self.SOUNDS_DIR).resolve()