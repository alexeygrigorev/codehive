"""FastAPI application factory."""

import contextlib
from collections.abc import AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from codehive.__version__ import __version__
from codehive.config import Settings
from codehive.api.deps import get_current_user
from codehive.core.first_run import print_credentials, seed_first_run
from codehive.db.session import async_session_factory
from codehive.api.routes.approvals import approvals_router
from codehive.api.routes.auth import auth_router
from codehive.api.routes.checkpoints import checkpoints_router, session_checkpoints_router
from codehive.api.routes.events import router as events_router
from codehive.api.routes.github import github_router
from codehive.api.routes.issues import issues_router, project_issues_router
from codehive.api.routes.knowledge import router as knowledge_router
from codehive.api.routes.logs import logs_router
from codehive.api.routes.notifications import router as push_router
from codehive.api.routes.projects import router as projects_router
from codehive.api.routes.remote import router as remote_router
from codehive.api.routes.tunnels import router as tunnels_router
from codehive.api.routes.replay import replay_router
from codehive.api.routes.search import search_router, session_history_router
from codehive.api.routes.webhooks import webhooks_router
from codehive.api.routes.questions import questions_router
from codehive.api.routes.questions_global import global_questions_router
from codehive.api.routes.system import system_router
from codehive.api.routes.archetypes import router as archetypes_router
from codehive.api.routes.roles import project_roles_router, router as roles_router
from codehive.api.routes.sessions import project_sessions_router, sessions_router
from codehive.api.routes.tasks import session_tasks_router, tasks_router
from codehive.api.routes.project_flow import router as project_flow_router
from codehive.api.routes.members import router as members_router
from codehive.api.routes.workspace import router as workspaces_router
from codehive.api.ws import router as ws_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Run first-run setup on startup."""
        session_maker = async_session_factory()
        async with session_maker() as db:
            credentials = await seed_first_run(db)
            if credentials is not None:
                print_credentials(credentials)
        yield

    app = FastAPI(title="codehive", version=__version__, lifespan=lifespan)

    settings = Settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- Public routes (no auth required) ----
    app.include_router(auth_router)

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "version": __version__}

    # ---- Protected routes (require valid access token) ----
    _auth = [Depends(get_current_user)]

    app.include_router(approvals_router, dependencies=_auth)
    app.include_router(workspaces_router, dependencies=_auth)
    app.include_router(members_router, dependencies=_auth)
    app.include_router(projects_router, dependencies=_auth)
    app.include_router(project_issues_router, dependencies=_auth)
    app.include_router(issues_router, dependencies=_auth)
    app.include_router(project_sessions_router, dependencies=_auth)
    app.include_router(sessions_router, dependencies=_auth)
    app.include_router(session_checkpoints_router, dependencies=_auth)
    app.include_router(checkpoints_router, dependencies=_auth)
    app.include_router(session_tasks_router, dependencies=_auth)
    app.include_router(tasks_router, dependencies=_auth)
    app.include_router(events_router, dependencies=_auth)
    app.include_router(logs_router, dependencies=_auth)
    app.include_router(questions_router, dependencies=_auth)
    app.include_router(global_questions_router, dependencies=_auth)
    app.include_router(system_router, dependencies=_auth)
    app.include_router(roles_router, dependencies=_auth)
    app.include_router(project_roles_router, dependencies=_auth)
    app.include_router(archetypes_router, dependencies=_auth)
    app.include_router(ws_router, dependencies=_auth)
    app.include_router(knowledge_router, dependencies=_auth)
    app.include_router(github_router, dependencies=_auth)
    app.include_router(remote_router, dependencies=_auth)
    app.include_router(tunnels_router, dependencies=_auth)
    app.include_router(webhooks_router, dependencies=_auth)
    app.include_router(replay_router, dependencies=_auth)
    app.include_router(push_router, dependencies=_auth)
    app.include_router(search_router, dependencies=_auth)
    app.include_router(session_history_router, dependencies=_auth)
    app.include_router(project_flow_router, dependencies=_auth)

    return app
