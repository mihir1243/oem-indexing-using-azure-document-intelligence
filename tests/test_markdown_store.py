from pathlib import Path

from src.extraction.markdown_store import (
    load_cached_extraction,
    page_map_path_for,
    save_extracted_markdown,
)
from src.models import ExtractedDocument, ManualMetadata, PageSpan


def test_save_and_load_cached_markdown(tmp_path: Path):
    meta = ManualMetadata(
        manufacturer="Caterpiller",
        model_series=["2C3000"],
        manual_type="service",
    )
    doc = ExtractedDocument(
        source_file="caterpiller manual.pdf",
        markdown_content="# Chapter 1\n\nSample text.",
        page_map=[PageSpan(start=0, end=10, page_number=1)],
        metadata=meta,
    )
    out_dir = tmp_path / "markdown"
    path = save_extracted_markdown(doc, out_dir)
    assert path.name == "caterpiller manual.md"
    assert path.read_text(encoding="utf-8") == doc.markdown_content
    assert page_map_path_for(doc.source_file, out_dir).is_file()

    loaded = load_cached_extraction(doc.source_file, out_dir, meta)
    assert loaded is not None
    assert loaded.markdown_content == doc.markdown_content
    assert loaded.page_map[0].page_number == 1
