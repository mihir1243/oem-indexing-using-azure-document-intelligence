from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    HeadingHierarchyOptions,
    OcrOptions,
    PdfPipelineOptions,
    TableFormerMode,
    TableStructureOptions,
    TesseractCliOcrOptions,
)
from docling.datamodel.progress import ConversionProgressEvent
from docling.document_converter import DocumentConverter, PdfFormatOption

from src.config import DoclingSettings, Settings, get_settings
from src.extraction.docling_export import build_markdown_and_page_map
from src.models import ExtractedDocument, ManualMetadata, PageSpan

logger = logging.getLogger("oem_manuals.extraction")


class DocumentExtractor:
    def __init__(self, settings: DoclingSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._converter = _build_converter(self._settings)

    def extract(
        self,
        pdf_path: Path,
        metadata: ManualMetadata,
        *,
        on_progress: Callable[[ConversionProgressEvent], None] | None = None,
    ) -> ExtractedDocument:
        pdf_path = pdf_path.resolve()
        logger.info("Docling convert started: %s", pdf_path.name)
        result = self._converter.convert(str(pdf_path), progress_callback=on_progress)
        doc = result.document

        logger.info("Docling convert finished: %s — building markdown", pdf_path.name)
        markdown_content, page_map = build_markdown_and_page_map(doc)

        return ExtractedDocument(
            source_file=pdf_path.name,
            markdown_content=markdown_content,
            page_map=page_map,
            metadata=metadata,
        )


def _parse_tesseract_langs(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def build_ocr_options(settings: DoclingSettings) -> OcrOptions:
    if settings.docling_ocr_engine == "rapidocr":
        from docling.datamodel.pipeline_options import RapidOcrOptions

        return RapidOcrOptions()
    langs = _parse_tesseract_langs(settings.docling_tesseract_langs) or ["eng"]
    return TesseractCliOcrOptions(lang=langs)


def build_pdf_pipeline_options(settings: DoclingSettings) -> PdfPipelineOptions:
    table_mode = (
        TableFormerMode.FAST
        if settings.docling_table_mode.lower() == "fast"
        else TableFormerMode.ACCURATE
    )
    infer_headings = settings.docling_heading_hierarchy
    return PdfPipelineOptions(
        do_table_structure=True,
        do_ocr=settings.docling_do_ocr,
        ocr_options=build_ocr_options(settings),
        generate_parsed_pages=infer_headings,
        heading_hierarchy_options=HeadingHierarchyOptions(enabled=infer_headings),
        table_structure_options=TableStructureOptions(mode=table_mode),
    )


def _build_converter(settings: DoclingSettings) -> DocumentConverter:
    pipeline_options = build_pdf_pipeline_options(settings)
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )


def page_for_offset(page_map: list[PageSpan], offset: int) -> int:
    if not page_map:
        return 1
    for span in page_map:
        if span.start <= offset < span.end:
            return span.page_number
    for span in reversed(page_map):
        if offset >= span.start:
            return span.page_number
    return page_map[0].page_number
