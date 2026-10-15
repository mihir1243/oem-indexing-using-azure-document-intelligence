from __future__ import annotations

import re
from pathlib import Path

from src.config import Settings, get_settings
from src.extraction.heading_normalize import normalize_marker_headings_with_page_map
from src.models import ExtractedDocument, ManualMetadata, PageSpan

# Marker paginate_output: \n\n{page_idx}\n{48 dashes}\n\n (page_idx starts at 0)
_PAGE_SEPARATOR_PATTERN = re.compile(r"\n*\{(\d+)\}-{48}\n*", re.MULTILINE)


class DocumentExtractor:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._converter = _get_pdf_converter(self._settings)

    def extract(
        self,
        pdf_path: Path,
        metadata: ManualMetadata,
    ) -> ExtractedDocument:
        pdf_path = pdf_path.resolve()
        from marker.output import text_from_rendered

        rendered = self._converter(str(pdf_path))
        raw_markdown, _, _ = text_from_rendered(rendered)
        markdown_content, page_map = _split_paginated_markdown(raw_markdown or "")
        if self._settings.marker_normalize_headings:
            markdown_content, page_map = normalize_marker_headings_with_page_map(
                markdown_content, page_map
            )

        return ExtractedDocument(
            source_file=pdf_path.name,
            markdown_content=markdown_content,
            page_map=page_map,
            metadata=metadata,
        )


_converter_cache: object | None = None
_converter_cache_key: tuple[str, bool, str, str, bool, bool] | None = None


def _get_pdf_converter(settings: Settings):
    from marker.config.parser import ConfigParser
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict

    global _converter_cache, _converter_cache_key
    key = (
        settings.marker_torch_device.strip(),
        settings.marker_force_ocr,
        settings.marker_page_range.strip(),
        settings.marker_mode.strip().lower(),
        settings.marker_disable_ocr,
        settings.marker_html_tables,
    )
    if _converter_cache is not None and _converter_cache_key == key:
        return _converter_cache

    disable_ocr = settings.marker_disable_ocr and not settings.marker_force_ocr
    config: dict[str, object] = {
        "output_format": "markdown",
        "paginate_output": True,
        "disable_image_extraction": True,
        "force_ocr": settings.marker_force_ocr,
        "disable_ocr": disable_ocr,
        "html_tables_in_markdown": settings.marker_html_tables,
    }
    if settings.marker_torch_device.strip():
        config["TORCH_DEVICE"] = settings.marker_torch_device.strip()
    page_range = settings.marker_page_range.strip()
    if page_range:
        config["page_range"] = page_range
    mode = settings.marker_mode.strip().lower()
    if mode in ("balanced", "fast"):
        config["mode"] = mode

    config_parser = ConfigParser(config)
    _converter_cache = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service(),
    )
    _converter_cache_key = key
    return _converter_cache


def _split_paginated_markdown(text: str) -> tuple[str, list[PageSpan]]:
    """Strip Marker page separators and build char-offset page spans (1-based pages)."""
    if not text:
        return "", []

    parts = _PAGE_SEPARATOR_PATTERN.split(text)
    if len(parts) == 1:
        content = text.strip()
        if not content:
            return "", []
        end = len(content)
        return content, [PageSpan(start=0, end=end, page_number=1)]

    pages: list[tuple[int, str]] = []
    i = 0
    while i < len(parts):
        segment = parts[i]
        if segment.isdigit():
            page_idx = int(segment)
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            pages.append((page_idx, body))
            i += 2
        else:
            leading = segment.strip()
            if leading:
                pages.append((0, leading))
            i += 1

    if not pages:
        content = _PAGE_SEPARATOR_PATTERN.sub("", text).strip()
        if not content:
            return "", []
        end = len(content)
        return content, [PageSpan(start=0, end=end, page_number=1)]

    page_map: list[PageSpan] = []
    chunks: list[str] = []
    offset = 0
    for page_idx, body in pages:
        if not body:
            continue
        if chunks:
            offset += 2
        start = offset
        offset += len(body)
        page_map.append(PageSpan(start=start, end=offset, page_number=page_idx + 1))
        chunks.append(body)

    markdown_content = "\n\n".join(chunks)
    return markdown_content, page_map


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
