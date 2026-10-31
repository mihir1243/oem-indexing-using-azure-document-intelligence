from __future__ import annotations

from dataclasses import dataclass

from docling.datamodel.progress import (
    ConversionPhase,
    ConversionProgressEvent,
    ConversionProgressKind,
    ENRICHMENT_STEP_LABELS,
    EnrichmentProgress,
    PageCompletedProgress,
    PhaseStartedProgress,
)

_PHASE_LABELS: dict[ConversionPhase, str] = {
    ConversionPhase.INITIALIZE: "Loading models and pipeline",
    ConversionPhase.BUILD: "Processing PDF pages",
    ConversionPhase.ASSEMBLE: "Assembling document",
    ConversionPhase.ENRICH: "Running enrichment",
}


@dataclass(frozen=True)
class ExtractionProgressSnapshot:
    message: str
    percent: float | None = None
    completed_pages: int | None = None
    total_pages: int | None = None


def snapshot_from_docling_event(event: ConversionProgressEvent) -> ExtractionProgressSnapshot | None:
    kind = event.kind

    if kind == ConversionProgressKind.DOCUMENT_STARTED:
        return ExtractionProgressSnapshot(message="Starting conversion", percent=0.0)

    if kind == ConversionProgressKind.PHASE_STARTED:
        assert isinstance(event, PhaseStartedProgress)
        label = _PHASE_LABELS.get(event.phase, event.phase.value)
        percent = {
            ConversionPhase.INITIALIZE: 1.0,
            ConversionPhase.BUILD: 5.0,
            ConversionPhase.ASSEMBLE: 88.0,
            ConversionPhase.ENRICH: 90.0,
        }.get(event.phase)
        return ExtractionProgressSnapshot(message=label, percent=percent)

    if kind == ConversionProgressKind.PAGE_COMPLETED:
        assert isinstance(event, PageCompletedProgress)
        total = event.total_pages
        done = event.completed_pages
        if total > 0:
            # Page work dominates runtime; reserve headroom for assemble/enrich.
            percent = 5.0 + (done / total) * 83.0
            message = f"Processed pages {done}/{total}"
        else:
            percent = None
            message = f"Processed page {event.page_no}"
        return ExtractionProgressSnapshot(
            message=message,
            percent=round(percent, 1) if percent is not None else None,
            completed_pages=done,
            total_pages=total if total > 0 else None,
        )

    if kind == ConversionProgressKind.ENRICHMENT_PROGRESS:
        assert isinstance(event, EnrichmentProgress)
        label = ENRICHMENT_STEP_LABELS.get(event.step, event.label)
        if event.total_items > 0:
            fraction = event.completed_items / event.total_items
            percent = 90.0 + fraction * 10.0
            message = f"{label}: {event.completed_items}/{event.total_items}"
        else:
            percent = 90.0
            message = label
        return ExtractionProgressSnapshot(
            message=message,
            percent=round(percent, 1),
        )

    if kind == ConversionProgressKind.DOCUMENT_COMPLETED:
        return ExtractionProgressSnapshot(message="Finalizing output", percent=99.0)

    return None
