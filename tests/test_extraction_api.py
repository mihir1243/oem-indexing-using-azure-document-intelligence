from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.job_store import JOB_META, OUTPUT_MD
from src.api.schemas import JobStatus
from src.models import ExtractedDocument, ManualMetadata, PageSpan


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_JOBS_DIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("API_KEY", "test-secret")
    get_api_settings = __import__("src.config", fromlist=["get_api_settings"]).get_api_settings
    get_api_settings.cache_clear()

    with TestClient(app) as client:
        yield client

    get_api_settings.cache_clear()


def _headers() -> dict[str, str]:
    return {"X-API-Key": "test-secret"}


def test_health_without_api_key(api_client: TestClient):
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_poll_download_flow(api_client: TestClient, tmp_path: Path):
    fake_doc = ExtractedDocument(
        source_file="input.pdf",
        markdown_content="# Title\n\nBody",
        page_map=[PageSpan(start=0, end=20, page_number=1)],
        metadata=ManualMetadata("api", [], "upload"),
    )
    mock_extractor = MagicMock()
    mock_extractor.extract.return_value = fake_doc

    with patch("src.api.job_store.DocumentExtractor", return_value=mock_extractor):
        upload = api_client.post(
            "/api/v1/extractions",
            headers=_headers(),
            files={"file": ("manual.pdf", b"%PDF-1.4 minimal", "application/pdf")},
        )
        assert upload.status_code == 200
        job_id = upload.json()["job_id"]

        poll = None
        for _ in range(50):
            poll = api_client.get(f"/api/v1/extractions/{job_id}", headers=_headers())
            assert poll.status_code == 200
            if poll.json()["status"] == JobStatus.completed.value:
                break

        assert poll is not None
        assert poll.json()["status"] == JobStatus.completed.value
        assert poll.json()["markdown_url"] == f"/api/v1/extractions/{job_id}/markdown"

        download = api_client.get(
            f"/api/v1/extractions/{job_id}/markdown",
            headers=_headers(),
        )
        assert download.status_code == 200
        assert "Title" in download.text

    meta = json.loads((tmp_path / "jobs" / job_id / JOB_META).read_text(encoding="utf-8"))
    assert meta["status"] == JobStatus.completed.value
    assert (tmp_path / "jobs" / job_id / OUTPUT_MD).is_file()


def test_rejects_missing_api_key(api_client: TestClient):
    response = api_client.post(
        "/api/v1/extractions",
        files={"file": ("x.pdf", b"%PDF", "application/pdf")},
    )
    assert response.status_code == 401
