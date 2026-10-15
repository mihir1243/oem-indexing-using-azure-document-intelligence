from __future__ import annotations

import logging

import pymupdf as fitz
import pymupdf4llm
from pymupdf4llm.helpers import document_layout

from src.config import Settings, get_settings
from src.extraction.heading_normalizer import Bookmark, normalize_headings
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

    With the pymupdf layout engine available, headings are re-levelled from the
    layout boxes (running headers, numbering, font size, optional bookmarks) so
    hierarchical chunking can split on ``#`` … ``######`` like Azure DI markdown.
    """
    settings = settings or get_settings()

    heading_inserts: dict[int, list[str]] = {}
    if settings.pymupdf_normalize_headings and getattr(pymupdf4llm, "_use_layout", False):
        page_chunks, heading_inserts = _layout_markdown_with_headings(doc, source_file, settings)
    else:
        if settings.pymupdf_normalize_headings:
            logger.warning("pymupdf layout engine unavailable; keeping pymupdf4llm headings")
        page_chunks = _plain_markdown(doc, settings)

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
        page_number = int(chunk.get("metadata", {}).get("page_number") or (index + 1))
        page_text = (chunk.get("text") or "").strip()
        page_text = "\n\n".join([*heading_inserts.get(page_number, []), page_text]).strip()
        if index > 0 and parts:
            parts.append(_PAGE_SEPARATOR)
            offset += len(_PAGE_SEPARATOR)

        start = offset
        parts.append(page_text)
        offset += len(page_text)

        page_map.append(PageSpan(start=start, end=offset, page_number=page_number))

    return ExtractedDocument(
        source_file=source_file,
        markdown_content="".join(parts),
        page_map=page_map,
        metadata=metadata,
    )


def _plain_markdown(doc: fitz.Document, settings: Settings):
    include_margin_text = not settings.pymupdf_strip_page_header_footer
    markdown_kwargs: dict = {
        "page_chunks": True,
        "header": include_margin_text,
        "footer": include_margin_text,
        "show_progress": False,
    }
    if settings.pymupdf_table_output == "html":
        markdown_kwargs["table_output"] = "html"
    return pymupdf4llm.to_markdown(doc, **markdown_kwargs)


def _layout_markdown_with_headings(
    doc: fitz.Document,
    source_file: str,
    settings: Settings,
) -> tuple[list[dict], dict[int, list[str]]]:
    # Same parse options pymupdf4llm.to_markdown uses on its layout path.
    parsed = document_layout.parse_document(
        doc,
        filename=source_file,
        force_text=True,
        use_ocr=True,
        show_progress=False,
        render_html_tables=True if settings.pymupdf_table_output == "html" else None,
    )
    bookmarks = _usable_bookmarks(doc, settings) if settings.pymupdf_use_bookmarks else None
    heading_inserts = normalize_headings(parsed, bookmarks)

    include_margin_text = not settings.pymupdf_strip_page_header_footer
    page_chunks = parsed.to_markdown(
        page_chunks=True,
        header=include_margin_text,
        footer=include_margin_text,
        show_progress=False,
    )
    return page_chunks, heading_inserts


def _usable_bookmarks(doc: fitz.Document, settings: Settings) -> list[Bookmark] | None:
    bookmarks = [
        (int(level), title.strip(), int(page))
        for level, title, page, *_ in doc.get_toc(simple=True)
        if title.strip() and 1 <= int(page) <= doc.page_count
    ]
    if len(bookmarks) < settings.pymupdf_bookmarks_min_entries:
        logger.info(
            "PDF outline has %d usable bookmarks (< %d); deriving hierarchy from layout",
            len(bookmarks),
            settings.pymupdf_bookmarks_min_entries,
        )
        return None

    logger.info("Found %d usable bookmarks", bookmarks)
    return bookmarks
