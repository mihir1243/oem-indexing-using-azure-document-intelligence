from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import pymupdf as fitz
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentContentFormat
from azure.core.credentials import AzureKeyCredential

from src.config import Settings, get_settings
from src.extraction.pdf_probe import is_text_extractable
from src.extraction.pymupdf_extractor import extract_with_pymupdf
from src.models import ExtractedDocument, ManualMetadata, PageSpan

logger = logging.getLogger("oem_manuals.extraction")

ExtractionBackend = Literal["pymupdf", "azure_document_intelligence"]


class DocumentExtractor:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._azure_client: DocumentIntelligenceClient | None = None

    def extract(
        self,
        pdf_path: Path,
        metadata: ManualMetadata,
    ) -> tuple[ExtractedDocument, ExtractionBackend]:
        pdf_path = pdf_path.resolve()
        mode = self._settings.extraction_backend.strip().lower()

        if mode == "azure":
            return self._extract_azure(pdf_path, metadata), "azure_document_intelligence"

        doc = fitz.open(pdf_path)
        try:
            if mode == "pymupdf" or self._should_use_pymupdf(doc):
                logger.info("Extracting %s with PyMuPDF", pdf_path.name)
                return (
                    extract_with_pymupdf(
                        doc,
                        pdf_path.name,
                        metadata,
                        self._settings,
                    ),
                    "pymupdf",
                )
        finally:
            doc.close()

        logger.info(
            "PDF appears scanned or low text; extracting %s with Azure Document Intelligence",
            pdf_path.name,
        )
        return self._extract_azure(pdf_path, metadata), "azure_document_intelligence"

    def _should_use_pymupdf(self, doc: fitz.Document) -> bool:
        return is_text_extractable(
            doc,
            min_chars_per_page=self._settings.pymupdf_min_chars_per_page,
            min_text_page_fraction=self._settings.pymupdf_min_text_page_fraction,
        )

    def _azure_client_instance(self) -> DocumentIntelligenceClient:
        if self._azure_client is None:
            self._azure_client = DocumentIntelligenceClient(
                endpoint=self._settings.azure_doc_intelligence_endpoint,
                credential=AzureKeyCredential(self._settings.azure_doc_intelligence_key),
            )
        return self._azure_client

    def _extract_azure(
        self,
        pdf_path: Path,
        metadata: ManualMetadata,
    ) -> ExtractedDocument:
        with pdf_path.open("rb") as document:
            poller = self._azure_client_instance().begin_analyze_document(
                "prebuilt-layout",
                AnalyzeDocumentRequest(bytes_source=document.read()),
                output_content_format=DocumentContentFormat.MARKDOWN,
            )
        result = poller.result()

        markdown_content = result.content or ""
        page_map = _build_page_map(result)

        return ExtractedDocument(
            source_file=pdf_path.name,
            markdown_content=markdown_content,
            page_map=page_map,
            metadata=metadata,
        )


def _build_page_map(result) -> list[PageSpan]:
    spans: list[PageSpan] = []
    if not result.pages:
        return spans

    for page in result.pages:
        page_number = page.page_number or 1
        if not page.spans:
            continue
        for span in page.spans:
            if span.offset is None or span.length is None:
                continue
            start = int(span.offset)
            end = start + int(span.length)
            spans.append(PageSpan(start=start, end=end, page_number=page_number))

    spans.sort(key=lambda s: s.start)
    return spans


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
