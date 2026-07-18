from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from paper_wiki.core.config import Settings, get_settings
from paper_wiki.ingestion.pipeline import IngestPipeline
from paper_wiki.web.error_handlers import register_error_handlers
from paper_wiki.web.middleware import RequestIDMiddleware
from paper_wiki.web.routers import jobs, papers, publish, recommendations, search
from paper_wiki.web.services.job_manager import JobManager
from paper_wiki.web.services.paper_repository import PaperRepository


def create_app(
    *,
    settings: Settings | None = None,
    pipeline_factory: Callable[[], IngestPipeline] | None = None,
    job_manager: JobManager | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_job_manager = job_manager or JobManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        resolved_job_manager.shutdown()

    app = FastAPI(title="Paper-Wiki Web", version="0.1.0", lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.paper_repository = PaperRepository(resolved_settings)
    app.state.job_manager = resolved_job_manager
    app.state.pipeline_factory = pipeline_factory or (lambda: IngestPipeline(settings=resolved_settings))

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(papers.router)
    app.include_router(jobs.router)
    app.include_router(publish.router)
    app.include_router(recommendations.router)
    app.include_router(search.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
