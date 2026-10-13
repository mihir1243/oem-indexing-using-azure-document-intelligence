from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pymupdf as fitz


def is_text_extractable(
    doc: fitz.Document,
    *,
    min_chars_per_page: int,
    min_text_page_fraction: float,
) -> bool:
    """
    True when enough pages contain selectable text (typical born-digital PDF).

    Scanned/image-only manuals usually fail this check and should use Azure DI.
    """
    page_count = doc.page_count
    if page_count == 0:
        return False

    pages_with_text = 0
    for page in doc:
        if len(page.get_text().strip()) >= min_chars_per_page:
            pages_with_text += 1

    return (pages_with_text / page_count) >= min_text_page_fraction
