from __future__ import annotations
import uvicorn
from app.admin.server import create_app
from app.core.config import Settings
from app.core.db import bootstrap


def main() -> None:
    settings = Settings()  # loads from env/.env
    bootstrap()
    app = create_app(settings)
    uvicorn.run(
        app,
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
