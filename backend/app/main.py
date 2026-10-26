import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1 import matches, bets, bankroll, webhooks, admin
from backend.app.config import get_settings
from backend.app.database import get_engine
from backend.app.models import Base  # noqa: F401 — ensures all models are registered


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.getLogger().setLevel(settings.log_level.upper())
    logger.info("Football Prediction API starting up")

    # Ensure tables exist (Alembic handles migrations in production;
    # this is a safety net for local dev / first-run)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    yield

    logger.info("Football Prediction API shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Club Kelly API",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],   # tighten in production via env var
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(matches.router, prefix="/v1")
    app.include_router(bets.router, prefix="/v1")
    app.include_router(bankroll.router, prefix="/v1")
    app.include_router(webhooks.router, prefix="/v1")
    app.include_router(admin.router, prefix="/v1")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
