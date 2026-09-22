from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.districts import router as districts_router
from app.api.exports import router as exports_router
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.media import router as media_router
from app.api.results import router as results_router
from app.api.settings import router as settings_router
from app.api.system import router as system_router
from app.api.users import router as users_router
from app.api.videos import router as videos_router
from app.api.ws import router as ws_router
from app.config import get_settings
from app.core.errors import AppError, app_error_handler, http_error_handler
from app.core.logging import setup_logging
from app.database.session import get_engine, get_session_factory
from app.security.bootstrap import bootstrap_admin

settings = get_settings()
setup_logging(settings.log_level, service="api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.validate_runtime()
    # Local SQLite: ensure ORM schema (including auth tables) exists without a manual migrate.
    if settings.resolved_database_url.startswith("sqlite"):
        import app.models  # noqa: F401
        from app.database.sqlite_migrate import ensure_sqlite_auth_schema
        from packages.db.base import Base

        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        ensure_sqlite_auth_schema(engine)
    factory = get_session_factory()
    db = factory()
    try:
        from app.security.districts import seed_west_bengal_districts

        seed_west_bengal_districts(db)
        bootstrap_admin(db)
    finally:
        db.close()
    yield


_docs_url = None if settings.is_production else "/docs"
_redoc_url = None if settings.is_production else "/redoc"
_openapi_url = None if settings.is_production else "/openapi.json"

app = FastAPI(
    title="RoadVision API",
    description="Vehicle Intelligence & ANPR HTTP API with session authentication and RBAC.",
    version=settings.app_version,
    contact={"name": "RoadVision"},
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(districts_router)
app.include_router(system_router)
app.include_router(videos_router)
app.include_router(jobs_router)
app.include_router(results_router)
app.include_router(exports_router)
app.include_router(media_router)
app.include_router(dashboard_router)
app.include_router(settings_router)
app.include_router(ws_router)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"name": settings.app_name, "version": settings.app_version}
