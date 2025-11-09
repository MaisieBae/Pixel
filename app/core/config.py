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
    JOYSTICK_ROOM_ID: str = ""

    # Rotating notices
    ROTATE_NOTICE_SECONDS: int = 300

    # Tip tiers
    TIP_LOW_MAX: int = 14
    TIP_MEDIUM_MAX: int = 100
    TIP_HIGH_MAX: int = 500
    TIP_EXTREME_MAX: int = 1000

    # TTS
    TTS_PRE_SOUND: str = "announcement.wav"
    TTS_QUEUE_MAX: int = 5
    TTS_COOLDOWN_SECONDS: int = 10
    TTS_PREFIX_USERNAME: bool = True
    TTS_PRE_DELAY_MS: int = 1200

    # Perplexity
    PPLX_API_KEY: str = ""
    PPLX_MODEL: str = "sonar-small-online"
    PPLX_RANDOM_REPLY_PROB: float = 0.08
    PPLX_MAX_TOKENS: int = 200
    PPLX_TIMEOUT: int = 12
    # Pixel reply limits
    PIXEL_MAX_CHARS: int = 220
    PIXEL_MAX_SENTENCES: int = 2

    # Prize wheel
    PRIZES_FILE: str = "./data/prizes.json"
    SPIN_LINES_FILE: str = "./data/spin_lines.txt"
    PRIZE_LINES_FILE: str = "./data/prize_lines.txt"

    WHEEL_SFX_START: str = "wheel_start.wav"
    WHEEL_SFX_LOOP: str = "wheel_loop.wav"
    WHEEL_SFX_WIN: str = "wheel_win.wav"

    WHEEL_SPIN_MIN: int = 2
    WHEEL_SPIN_MAX: int = 10
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sounds_path(self) -> Path:
        return Path(self.SOUNDS_DIR).resolve()