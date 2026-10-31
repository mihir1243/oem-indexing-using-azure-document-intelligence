from __future__ import annotations

from docling.datamodel.progress import (
    ConversionPhase,
    ConversionProgressKind,
    PageCompletedProgress,
    PhaseStartedProgress,
)

from src.extraction.docling_progress import snapshot_from_docling_event


def test_page_completed_progress_snapshot():
    event = PageCompletedProgress(
        document_index=1,
        document_name="manual.pdf",
        page_no=3,
        success=True,
        completed_pages=3,
        total_pages=10,
    )
    snap = snapshot_from_docling_event(event)
    assert snap is not None
    assert snap.message == "Processed pages 3/10"
    assert snap.completed_pages == 3
    assert snap.total_pages == 10
    assert snap.percent is not None
    assert 5.0 < snap.percent < 30.0


def test_phase_started_snapshot():
    event = PhaseStartedProgress(
        document_index=1,
        document_name="manual.pdf",
        phase=ConversionPhase.INITIALIZE,
        kind=ConversionProgressKind.PHASE_STARTED,
    )
    snap = snapshot_from_docling_event(event)
    assert snap is not None
    assert "models" in snap.message.lower()
