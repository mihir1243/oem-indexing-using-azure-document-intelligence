from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class ExtractionJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    source_filename: str
    created_at: datetime
    updated_at: datetime
    error: str | None = None
    poll_url: str
    markdown_url: str | None = None
    progress_message: str | None = Field(
        default=None,
        description="Human-readable step while status is running",
    )
    progress_percent: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Approximate completion 0–100 while running",
    )
    completed_pages: int | None = Field(
        default=None,
        description="Docling pages finished so far (when known)",
    )
    total_pages: int | None = Field(
        default=None,
        description="Total PDF pages being converted (when known)",
    )


class CreateExtractionResponse(BaseModel):
    job_id: str
    status: JobStatus
    poll_url: str
