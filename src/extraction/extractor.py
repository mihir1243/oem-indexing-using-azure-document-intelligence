from __future__ import annotations

from pathlib import Path

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentContentFormat
from azure.core.credentials import AzureKeyCredential

from src.config import Settings, get_settings
from src.models import ExtractedDocument, ManualMetadata, PageSpan


class DocumentExtractor:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = DocumentIntelligenceClient(
            endpoint=self._settings.azure_doc_intelligence_endpoint,
            credential=AzureKeyCredential(self._settings.azure_doc_intelligence_key),
        )

    def extract(
        self,
        pdf_path: Path,
        metadata: ManualMetadata,
    ) -> ExtractedDocument:
        pdf_path = pdf_path.resolve()
        with pdf_path.open("rb") as document:
            poller = self._client.begin_analyze_document(
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
