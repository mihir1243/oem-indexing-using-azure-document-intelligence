from __future__ import annotations

import logging

import pymupdf as fitz
import pymupdf4llm

from src.config import Settings, get_settings
from src.models import ExtractedDocument, ManualMetadata, PageSpan

logger = logging.getLogger("oem_manuals.extraction")

_PAGE_SEPARATOR = "\n\n"


def extract_with_pymupdf(
    doc: fitz.Document,
    source_file: str,
    metadata: ManualMetadata,
    settings: Settings | None = None,
) -> ExtractedDocument:
    """
    Extract GitHub-flavored markdown via pymupdf4llm (headings, tables, lists).

    Uses layout analysis and font-size hierarchy for ``#`` … ``######`` headings so
    hierarchical chunking can split on the same markers as Azure DI markdown.
    """
    settings = settings or get_settings()

    include_margin_text = not settings.pymupdf_strip_page_header_footer
    markdown_kwargs: dict = {
        "page_chunks": True,
        "header": include_margin_text,
        "footer": include_margin_text,
        "show_progress": False,
    }
    if settings.pymupdf_table_output == "html":
        markdown_kwargs["table_output"] = "html"

    page_chunks = pymupdf4llm.to_markdown(doc, **markdown_kwargs)

    if isinstance(page_chunks, str):
        # Unexpected when page_chunks=True; keep pipeline usable.
        logger.warning("pymupdf4llm returned a single string; page map will be empty")
        return ExtractedDocument(
            source_file=source_file,
            markdown_content=page_chunks,
            page_map=[],
            metadata=metadata,
        )

    parts: list[str] = []
    page_map: list[PageSpan] = []
    offset = 0

    for index, chunk in enumerate(page_chunks):
        page_text = (chunk.get("text") or "").strip()
        if index > 0 and parts:
            parts.append(_PAGE_SEPARATOR)
            offset += len(_PAGE_SEPARATOR)

        start = offset
        parts.append(page_text)
        offset += len(page_text)

        page_number = int(chunk.get("metadata", {}).get("page_number") or (index + 1))
        page_map.append(PageSpan(start=start, end=offset, page_number=page_number))

    return ExtractedDocument(
        source_file=source_file,
        markdown_content="".join(parts),
        page_map=page_map,
        metadata=metadata,
    )
