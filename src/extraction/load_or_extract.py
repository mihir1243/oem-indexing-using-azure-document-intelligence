from __future__ import annotations

from pathlib import Path

from src.config import Settings
from src.extraction.extractor import DocumentExtractor
from src.extraction.markdown_store import (
    load_cached_extraction,
    markdown_path_for,
    save_extracted_markdown,
)
from src.models import ExtractedDocument, ManualMetadata


def load_or_extract(
    pdf_path: Path,
    metadata: ManualMetadata,
    settings: Settings,
    *,
    force_reextract: bool = False,
) -> tuple[ExtractedDocument, Path | None, bool]:
    """
    Return (document, markdown_path, used_cache).

    When cache is used, markdown_path points at the existing .md file.
    """
    pdf_path = pdf_path.resolve()
    output_dir_str = settings.markdown_output_dir.strip()
    markdown_path: Path | None = None

    if output_dir_str and settings.skip_extraction_if_markdown_exists and not force_reextract:
        output_dir = Path(output_dir_str)
        cached = load_cached_extraction(pdf_path.name, output_dir, metadata)
        if cached is not None:
            return cached, markdown_path_for(pdf_path.name, output_dir), True

    extractor = DocumentExtractor(settings)
    extracted = extractor.extract(pdf_path, metadata)

    if output_dir_str:
        markdown_path = save_extracted_markdown(extracted, Path(output_dir_str))

    return extracted, markdown_path, False
