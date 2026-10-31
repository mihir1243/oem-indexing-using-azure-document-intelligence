from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src.api.job_store import ExtractionJobStore
from src.api.schemas import CreateExtractionResponse, ExtractionJobResponse, JobStatus
from src.config import ApiSettings, get_api_settings
from src.timing import configure_api_logging

_store: ExtractionJobStore | None = None
logger = logging.getLogger("oem_manuals.api")


def get_store() -> ExtractionJobStore:
    if _store is None:
        raise RuntimeError("Job store not initialized")
    return _store


def _require_api_key(
    settings: Annotated[ApiSettings, Depends(get_api_settings)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.api_key.strip()
    if not expected:
        return
    if not x_api_key or x_api_key.strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store
    from src.runtime_checks import verify_docling_runtime

    settings = get_api_settings()
    configure_api_logging(settings.api_log_level)
    logger.info(
        "Starting extraction API (jobs_dir=%s, max_concurrent=%s)",
        settings.api_jobs_dir,
        settings.api_max_concurrent_extractions,
    )

    verify_docling_runtime()
    _store = ExtractionJobStore(settings)
    _store.requeue_incomplete_jobs()
    worker = asyncio.create_task(_store.worker_loop())
    yield
    logger.info("Shutting down extraction API")
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass
    _store = None


app = FastAPI(
    title="OEM Manual Extraction API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def log_requests(request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s (%.0fms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _poll_url(job_id: str) -> str:
    return f"/api/v1/extractions/{job_id}"


def _markdown_url(job_id: str) -> str:
    return f"/api/v1/extractions/{job_id}/markdown"


def _job_response(record) -> ExtractionJobResponse:
    markdown_url = None
    if record.status == JobStatus.completed:
        markdown_url = _markdown_url(record.job_id)
    show_progress = record.status == JobStatus.running
    return ExtractionJobResponse(
        job_id=record.job_id,
        status=record.status,
        source_filename=record.source_filename,
        created_at=record.created_at,
        updated_at=record.updated_at,
        error=record.error,
        poll_url=_poll_url(record.job_id),
        markdown_url=markdown_url,
        progress_message=record.progress_message if show_progress else None,
        progress_percent=record.progress_percent if show_progress else None,
        completed_pages=record.completed_pages if show_progress else None,
        total_pages=record.total_pages if show_progress else None,
    )


@app.post(
    "/api/v1/extractions",
    response_model=CreateExtractionResponse,
    dependencies=[Depends(_require_api_key)],
)
async def create_extraction(
    file: Annotated[UploadFile, File(description="PDF manual to extract")],
    store: Annotated[ExtractionJobStore, Depends(get_store)],
    settings: Annotated[ApiSettings, Depends(get_api_settings)],
) -> CreateExtractionResponse:
    filename = (file.filename or "upload.pdf").strip()
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > settings.api_max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds API_MAX_UPLOAD_BYTES")

    record = store.create_job(filename, data)
    logger.info(
        "Created extraction job %s for upload %s (%s bytes)",
        record.job_id,
        filename,
        len(data),
    )
    return CreateExtractionResponse(
        job_id=record.job_id,
        status=record.status,
        poll_url=_poll_url(record.job_id),
    )


@app.get(
    "/api/v1/extractions/{job_id}",
    response_model=ExtractionJobResponse,
    dependencies=[Depends(_require_api_key)],
)
async def get_extraction(
    job_id: str,
    store: Annotated[ExtractionJobStore, Depends(get_store)],
) -> ExtractionJobResponse:
    record = store.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_response(record)


@app.get(
    "/api/v1/extractions/{job_id}/markdown",
    dependencies=[Depends(_require_api_key)],
)
async def download_markdown(
    job_id: str,
    store: Annotated[ExtractionJobStore, Depends(get_store)],
) -> FileResponse:
    record = store.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if record.status != JobStatus.completed:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not complete (status={record.status.value})",
        )
    md_path = store.markdown_path(job_id)
    if not md_path.is_file():
        raise HTTPException(status_code=404, detail="Markdown output missing")

    stem = md_path.stem
    return FileResponse(
        path=md_path,
        media_type="text/markdown; charset=utf-8",
        filename=f"{stem}.md",
    )


@app.get(
    "/api/v1/extractions/{job_id}/page-map",
    dependencies=[Depends(_require_api_key)],
)
async def download_page_map(
    job_id: str,
    store: Annotated[ExtractionJobStore, Depends(get_store)],
) -> FileResponse:
    record = store.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if record.status != JobStatus.completed:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not complete (status={record.status.value})",
        )
    map_path = store.page_map_path(job_id)
    if not map_path.is_file():
        raise HTTPException(status_code=404, detail="Page map missing")
    return FileResponse(
        path=map_path,
        media_type="application/json",
        filename=f"{job_id}.page_map.json",
    )


def run() -> None:
    import uvicorn

    settings = get_api_settings()
    port = int(os.environ.get("PORT", str(settings.api_port)))
    from src.timing import resolve_log_level

    uvicorn.run(
        "src.api.app:app",
        host=settings.api_host,
        port=port,
        log_level=logging.getLevelName(resolve_log_level(settings.api_log_level)).lower(),
    )


if __name__ == "__main__":
    run()
