from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from paper_wiki.discovery.exceptions import DiscoveryError, RecommendError
from paper_wiki.publishing.exceptions import PublishingError
from paper_wiki.web.services.job_manager import JobNotFoundError
from paper_wiki.web.services.paper_repository import (
    PaperConflictError,
    PaperNotFoundError,
    PaperValidationError,
)

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PaperNotFoundError)
    async def paper_not_found_handler(request: Request, exc: PaperNotFoundError) -> JSONResponse:
        logger.warning("paper not found: %s", exc)
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(JobNotFoundError)
    async def job_not_found_handler(request: Request, exc: JobNotFoundError) -> JSONResponse:
        logger.warning("job not found: %s", exc)
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(PaperConflictError)
    async def paper_conflict_handler(request: Request, exc: PaperConflictError) -> JSONResponse:
        logger.warning("paper conflict: %s", exc)
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(PaperValidationError)
    async def paper_validation_handler(request: Request, exc: PaperValidationError) -> JSONResponse:
        logger.warning("paper validation error: %s", exc)
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        logger.warning("bad request: %s", exc)
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(PublishingError)
    async def publishing_error_handler(request: Request, exc: PublishingError) -> JSONResponse:
        logger.warning("publishing error: %s", exc)
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(DiscoveryError)
    async def discovery_error_handler(request: Request, exc: DiscoveryError) -> JSONResponse:
        logger.warning("discovery error: %s", exc)
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(RecommendError)
    async def recommend_error_handler(request: Request, exc: RecommendError) -> JSONResponse:
        logger.warning("recommend error: %s", exc)
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled web error")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
