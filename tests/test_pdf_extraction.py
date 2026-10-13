from pathlib import Path

import pymupdf as fitz

from src.extraction.extractor import page_for_offset
from src.extraction.pdf_probe import is_text_extractable
from src.extraction.pymupdf_extractor import extract_with_pymupdf
from src.models import ManualMetadata


def _meta() -> ManualMetadata:
    return ManualMetadata(
        manufacturer="Test",
        model_series=["X"],
        manual_type="service",
    )


def test_is_text_extractable_digital_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "digital.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Engine maintenance schedule and torque specifications.")
    doc.save(pdf_path)
    doc.close()

    with fitz.open(pdf_path) as reopened:
        assert is_text_extractable(
            reopened,
            min_chars_per_page=20,
            min_text_page_fraction=0.5,
        )


def test_is_text_extractable_blank_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    with fitz.open(pdf_path) as reopened:
        assert not is_text_extractable(
            reopened,
            min_chars_per_page=20,
            min_text_page_fraction=0.5,
        )


def test_pymupdf_extractor_page_map(tmp_path: Path) -> None:
    pdf_path = tmp_path / "two_page.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Page one content.")
    doc.new_page().insert_text((72, 72), "Page two content.")
    doc.save(pdf_path)
    doc.close()

    with fitz.open(pdf_path) as reopened:
        extracted = extract_with_pymupdf(reopened, pdf_path.name, _meta())

    assert "Page one content." in extracted.markdown_content
    assert "Page two content." in extracted.markdown_content
    assert len(extracted.page_map) == 2
    assert page_for_offset(extracted.page_map, 0) == 1
    page_two_offset = extracted.markdown_content.index("Page two")
    assert page_for_offset(extracted.page_map, page_two_offset) == 2
