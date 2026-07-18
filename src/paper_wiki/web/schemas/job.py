from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class JobResponse(BaseModel):
    job_id: str
    slug: str
    target: str
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    result: Any | None = None
    progress: str | None = None
