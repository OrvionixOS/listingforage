"""Etsy Listing AI Studio — API entrypoint."""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .routes import (auth_routes, billing_routes, etsy_routes, growth_routes,
                     listing_routes, workspace_routes)

logging.basicConfig(level=logging.INFO)
settings = get_settings()

app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.env == "development" else [
        os.getenv("LF_ALLOWED_ORIGIN", "https://app.etsylistingaistudio.com")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(growth_routes.router)
app.include_router(listing_routes.router)
app.include_router(billing_routes.router)
app.include_router(etsy_routes.router)
app.include_router(workspace_routes.router)


@app.on_event("startup")
def _start_job_workers():
    from .database import init_db
    from .jobs import recover_and_start
    init_db()          # tables must exist before recovery scans them
    recover_and_start()


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}


# --- Serve the built frontend (single-service deploy) -----------------------
# Build with `npm run build` in /frontend; dist is mounted here if present.
# SPA fallback: unknown non-API paths (client-side routes like /dashboard)
# serve index.html so deep links and refreshes work.
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException


class SpaStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and not path.startswith("api"):
                return await super().get_response("index.html", scope)
            raise


_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():
    app.mount("/", SpaStaticFiles(directory=str(_dist), html=True), name="frontend")
