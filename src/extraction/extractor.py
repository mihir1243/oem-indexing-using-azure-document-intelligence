from __future__ import annotations

from pathlib import Path

from liteparse import LiteParse

from src.config import Settings, get_settings
from src.extraction.liteparse_render import render_pages
from src.models import ExtractedDocument, ManualMetadata, PageSpan


class DocumentExtractor:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._parser = LiteParse(
            output_format="json",
            extract_blocks=True,
            ocr_enabled=self._settings.liteparse_ocr_enabled,
            ocr_language=self._settings.liteparse_ocr_language,
            dpi=float(self._settings.liteparse_dpi),
            quiet=True,
        )

    def extract(
        self,
        pdf_path: Path,
        metadata: ManualMetadata,
    ) -> ExtractedDocument:
        pdf_path = pdf_path.resolve()
        result = self._parser.parse(str(pdf_path))
        markdown_content, page_map = render_pages(result.pages)

        return ExtractedDocument(
            source_file=pdf_path.name,
            markdown_content=markdown_content,
            page_map=page_map,
            metadata=metadata,
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
