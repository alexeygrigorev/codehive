"""FastAPI application factory."""

from fastapi import FastAPI

from codehive.__version__ import __version__
from codehive.api.routes.projects import router as projects_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="codehive", version=__version__)

    app.include_router(projects_router)

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "version": __version__}

    return app
