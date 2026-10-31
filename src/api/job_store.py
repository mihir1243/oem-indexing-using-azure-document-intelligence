from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.api.schemas import JobStatus
from src.config import ApiSettings, get_api_settings
from src.extraction.docling_progress import snapshot_from_docling_event
from src.extraction.extractor import DocumentExtractor
from src.models import ManualMetadata

logger = logging.getLogger("oem_manuals.api.jobs")

JOB_META = "job.json"
INPUT_PDF = "input.pdf"
OUTPUT_MD = "output.md"
OUTPUT_PAGE_MAP = "output.page_map.json"


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus
    source_filename: str
    created_at: datetime
    updated_at: datetime
    error: str | None = None
    progress_message: str | None = None
    progress_percent: float | None = None
    completed_pages: int | None = None
    total_pages: int | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status.value
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> JobRecord:
        return cls(
            job_id=data["job_id"],
            status=JobStatus(data["status"]),
            source_filename=data["source_filename"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            error=data.get("error"),
            progress_message=data.get("progress_message"),
            progress_percent=data.get("progress_percent"),
            completed_pages=data.get("completed_pages"),
            total_pages=data.get("total_pages"),
        )


class ExtractionJobStore:
    def __init__(self, settings: ApiSettings | None = None) -> None:
        self._settings = settings or get_api_settings()
        self._root = Path(self._settings.api_jobs_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._sem = asyncio.Semaphore(max(1, self._settings.api_max_concurrent_extractions))

    @property
    def root(self) -> Path:
        return self._root

    def job_dir(self, job_id: str) -> Path:
        return self._root / job_id

    def create_job(self, source_filename: str, pdf_bytes: bytes) -> JobRecord:
        job_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        record = JobRecord(
            job_id=job_id,
            status=JobStatus.queued,
            source_filename=source_filename,
            created_at=now,
            updated_at=now,
        )
        job_path = self.job_dir(job_id)
        job_path.mkdir(parents=True, exist_ok=False)
        (job_path / INPUT_PDF).write_bytes(pdf_bytes)
        self._write_record(record)
        self._queue.put_nowait(job_id)
        logger.info("Queued extraction job %s (%s)", job_id, source_filename)
        return record

    def get_job(self, job_id: str) -> JobRecord | None:
        meta = self.job_dir(job_id) / JOB_META
        if not meta.is_file():
            return None
        return JobRecord.from_dict(json.loads(meta.read_text(encoding="utf-8")))

    def markdown_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / OUTPUT_MD

    def page_map_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / OUTPUT_PAGE_MAP

    async def worker_loop(self) -> None:
        while True:
            job_id = await self._queue.get()
            try:
                await self._run_job(job_id)
            finally:
                self._queue.task_done()

    def requeue_incomplete_jobs(self) -> None:
        for meta_path in self._root.glob(f"*/{JOB_META}"):
            record = JobRecord.from_dict(json.loads(meta_path.read_text(encoding="utf-8")))
            if record.status in (JobStatus.queued, JobStatus.running):
                record.status = JobStatus.queued
                record.updated_at = datetime.now(UTC)
                self._write_record(record)
                self._queue.put_nowait(record.job_id)
                logger.info("Re-queued job %s after restart", record.job_id)

    async def _run_job(self, job_id: str) -> None:
        async with self._sem:
            record = self.get_job(job_id)
            if record is None:
                return
            if record.status == JobStatus.completed:
                return

            record.status = JobStatus.running
            record.updated_at = datetime.now(UTC)
            record.error = None
            record.progress_message = "Starting extraction"
            record.progress_percent = 0.0
            record.completed_pages = None
            record.total_pages = None
            self._write_record(record)

            pdf_path = self.job_dir(job_id) / INPUT_PDF
            logger.info(
                "Running extraction job %s (%s, %s bytes)",
                job_id,
                record.source_filename,
                pdf_path.stat().st_size if pdf_path.is_file() else 0,
            )
            try:
                await asyncio.to_thread(self._extract_to_markdown, job_id, pdf_path, record)
            except Exception as exc:  # noqa: BLE001 - persist failure on the job record
                logger.exception("Job %s failed", job_id)
                record = self.get_job(job_id) or record
                record.status = JobStatus.failed
                record.error = str(exc)
                record.updated_at = datetime.now(UTC)
                self._write_record(record)

    def _extract_to_markdown(self, job_id: str, pdf_path: Path, record: JobRecord) -> None:
        metadata = ManualMetadata(
            manufacturer="api",
            model_series=[],
            manual_type="upload",
        )

        def on_progress(event) -> None:
            snapshot = snapshot_from_docling_event(event)
            if snapshot is None:
                return
            logger.info(
                "Job %s progress: %s%s",
                job_id,
                snapshot.message,
                f" ({snapshot.percent:.0f}%)" if snapshot.percent is not None else "",
            )
            self._update_progress(
                job_id,
                message=snapshot.message,
                percent=snapshot.percent,
                completed_pages=snapshot.completed_pages,
                total_pages=snapshot.total_pages,
            )

        extractor = DocumentExtractor(self._settings)
        extracted = extractor.extract(pdf_path, metadata, on_progress=on_progress)

        md_path = self.markdown_path(job_id)
        md_path.write_text(extracted.markdown_content, encoding="utf-8")

        from src.extraction.markdown_store import serialize_page_map

        self.page_map_path(job_id).write_text(
            json.dumps(serialize_page_map(extracted.page_map), indent=2),
            encoding="utf-8",
        )

        record.status = JobStatus.completed
        record.updated_at = datetime.now(UTC)
        record.error = None
        record.progress_message = None
        record.progress_percent = None
        record.completed_pages = None
        record.total_pages = None
        self._write_record(record)
        logger.info("Completed extraction job %s", job_id)

    def _update_progress(
        self,
        job_id: str,
        *,
        message: str,
        percent: float | None,
        completed_pages: int | None,
        total_pages: int | None,
    ) -> None:
        record = self.get_job(job_id)
        if record is None or record.status != JobStatus.running:
            return
        record.progress_message = message
        record.progress_percent = percent
        if completed_pages is not None:
            record.completed_pages = completed_pages
        if total_pages is not None:
            record.total_pages = total_pages
        record.updated_at = datetime.now(UTC)
        self._write_record(record)

    def _write_record(self, record: JobRecord) -> None:
        path = self.job_dir(record.job_id) / JOB_META
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(record.to_dict(), indent=2)
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
