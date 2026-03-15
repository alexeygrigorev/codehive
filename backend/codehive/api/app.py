"""FastAPI application factory."""

from fastapi import FastAPI

from codehive.__version__ import __version__
from codehive.api.routes.checkpoints import checkpoints_router, session_checkpoints_router
from codehive.api.routes.events import router as events_router
from codehive.api.routes.projects import router as projects_router
from codehive.api.routes.questions import questions_router
from codehive.api.routes.sessions import project_sessions_router, sessions_router
from codehive.api.routes.tasks import session_tasks_router, tasks_router
from codehive.api.ws import router as ws_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="codehive", version=__version__)

    app.include_router(projects_router)
    app.include_router(project_sessions_router)
    app.include_router(sessions_router)
    app.include_router(session_checkpoints_router)
    app.include_router(checkpoints_router)
    app.include_router(session_tasks_router)
    app.include_router(tasks_router)
    app.include_router(events_router)
    app.include_router(questions_router)
    app.include_router(ws_router)

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "version": __version__}

    return app
