"""FastAPI application factory."""

import contextlib
import logging
from collections.abc import AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from codehive.__version__ import __version__
from codehive.config import Settings
from codehive.api.deps import get_current_user
from codehive.api.errors import register_error_handling
from codehive.logging import configure_logging
from codehive.core.first_run import print_credentials, seed_first_run
from codehive.core.session import mark_interrupted_sessions
from codehive.db.session import async_session_factory
from codehive.api.routes.approvals import approvals_router
from codehive.api.routes.auth import auth_router
from codehive.api.routes.checkpoints import checkpoints_router, session_checkpoints_router
from codehive.api.routes.events import router as events_router
from codehive.api.routes.github import github_router
from codehive.api.routes.github_repos import github_repos_router
from codehive.api.routes.issues import issues_router, project_issues_router
from codehive.api.routes.knowledge import router as knowledge_router
from codehive.api.routes.logs import logs_router
from codehive.api.routes.notifications import router as push_router
from codehive.api.routes.projects import router as projects_router
from codehive.api.routes.remote import router as remote_router
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
from codehive.api.routes.error_tracking import router as error_tracking_router
from codehive.api.routes.project_flow import router as project_flow_router
from codehive.api.routes.transcript import transcript_router
from codehive.api.routes.async_dispatch import async_dispatch_router
from codehive.api.routes.providers import providers_router
from codehive.api.routes.usage import session_usage_router, usage_router
from codehive.api.routes.orchestrator import orchestrator_router
from codehive.api.routes.agent import agent_router
from codehive.api.routes.team import router as team_router
from codehive.api.ws import router as ws_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Run first-run setup and session recovery on startup; mark sessions on shutdown."""
        from codehive.db.models import Base
        from codehive.db.session import create_async_engine_from_settings

        # Auto-create tables for SQLite (no Alembic needed for dev)
        settings = Settings()
        if settings.database_url.startswith("sqlite"):
            from codehive.db.sync_columns import sync_sqlite_columns

            engine = create_async_engine_from_settings(settings.database_url)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await conn.run_sync(sync_sqlite_columns)
            await engine.dispose()

        session_maker = async_session_factory()
        async with session_maker() as db:
            credentials = await seed_first_run(db)
            if credentials is not None:
                print_credentials(credentials)

        # Seed built-in pipeline roles (pm, swe, qa, oncall) into custom_roles table
        from codehive.core.roles import seed_builtin_roles

        async with session_maker() as db:
            seeded = await seed_builtin_roles(db)
            if seeded:
                logger.info("Seeded %d built-in pipeline role(s)", seeded)

        # Startup recovery: mark any sessions stuck in 'executing' as 'interrupted'
        async with session_maker() as db:
            count = await mark_interrupted_sessions(db)
            logger.info("Startup recovery: %d session(s) marked as interrupted", count)

        yield

        # Cancel any background engine tasks
        from codehive.api.routes.async_dispatch import get_running_tasks

        running = get_running_tasks()
        if running:
            logger.info("Shutdown: cancelling %d background engine task(s)", len(running))
            for task in running.values():
                task.cancel()
            running.clear()

        # Graceful shutdown: mark executing sessions as interrupted
        async with session_maker() as db:
            count = await mark_interrupted_sessions(db)
            if count:
                logger.info("Shutdown: marked %d executing session(s) as interrupted", count)

    settings = Settings()
    configure_logging(settings)

    app = FastAPI(title="codehive", version=__version__, lifespan=lifespan)

    register_error_handling(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- Public routes (no auth required) ----
    app.include_router(auth_router)
    # Agent API: authenticated by X-Session-Id header, not JWT
    app.include_router(agent_router)
    # WebSocket router handles its own JWT auth (query param or first message)
    app.include_router(ws_router)

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/api/auth/config")
    async def auth_config() -> dict:
        return {"auth_enabled": settings.auth_enabled}

    # ---- Protected routes (require valid access token) ----
    _auth = [Depends(get_current_user)]

    app.include_router(approvals_router, dependencies=_auth)
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
    app.include_router(knowledge_router, dependencies=_auth)
    app.include_router(github_router, dependencies=_auth)
    app.include_router(github_repos_router, dependencies=_auth)
    app.include_router(remote_router, dependencies=_auth)
    app.include_router(webhooks_router, dependencies=_auth)
    app.include_router(replay_router, dependencies=_auth)
    app.include_router(push_router, dependencies=_auth)
    app.include_router(search_router, dependencies=_auth)
    app.include_router(session_history_router, dependencies=_auth)
    app.include_router(project_flow_router, dependencies=_auth)
    app.include_router(transcript_router, dependencies=_auth)
    app.include_router(error_tracking_router, dependencies=_auth)
    app.include_router(async_dispatch_router, dependencies=_auth)
    app.include_router(providers_router, dependencies=_auth)
    app.include_router(usage_router, dependencies=_auth)
    app.include_router(session_usage_router, dependencies=_auth)
    app.include_router(orchestrator_router, dependencies=_auth)
    app.include_router(team_router, dependencies=_auth)

    return app
