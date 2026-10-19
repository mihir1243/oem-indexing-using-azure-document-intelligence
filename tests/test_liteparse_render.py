from types import SimpleNamespace

from src.chunking.hierarchical import HierarchicalChunker
from src.extraction.extractor import page_for_offset
from src.extraction.liteparse_render import render_pages
from src.models import ExtractedDocument, ManualMetadata


def _page(page_num: int, blocks: list[dict] | None = None, text: str = "") -> SimpleNamespace:
    return SimpleNamespace(page_num=page_num, blocks=blocks, text=text)


def test_render_heading_list_and_html_table():
    pages = [
        _page(
            1,
            blocks=[
                {"kind": "heading", "level": 2, "text": "Specifications"},
                {"kind": "list_item", "level": 1, "ordered": False, "text": "Check oil"},
                {
                    "kind": "table",
                    "header": [{"text": "Part"}, {"text": "Qty"}],
                    "rows": [
                        [{"text": "Filter"}, {"text": "1"}],
                        [{"text": "A & B"}, {"text": "2\nlines"}],
                    ],
                },
            ],
        ),
        _page(2, text="Page two fallback"),
    ]
    markdown, page_map = render_pages(pages)

    assert "## Specifications" in markdown
    assert "- Check oil" in markdown
    assert "<table>" in markdown
    assert "<th>Part</th>" in markdown
    assert "<td>A &amp; B</td>" in markdown
    assert "<td>2<br>lines</td>" in markdown
    assert "Page two fallback" in markdown

    assert len(page_map) == 2
    assert page_map[0].page_number == 1
    assert page_map[1].page_number == 2
    assert page_map[0].start == 0
    assert page_map[0].end < page_map[1].start
    assert page_for_offset(page_map, page_map[1].start) == 2


def test_chunker_preserves_html_table():
    table_block = {
        "kind": "table",
        "header": [{"text": "Fault"}, {"text": "Action"}],
        "rows": [[{"text": "E01"}, {"text": "Reset"}]],
    }
    markdown, page_map = render_pages([_page(1, blocks=[table_block])])
    doc = ExtractedDocument(
        source_file="manual.pdf",
        markdown_content=markdown,
        page_map=page_map,
        metadata=ManualMetadata(
            manufacturer="Test",
            model_series=["X"],
            manual_type="service",
        ),
    )
    chunks = HierarchicalChunker().chunk(doc)
    assert chunks
    assert any("<table>" in chunk.chunk_content for chunk in chunks)
    assert any("E01" in chunk.chunk_content for chunk in chunks)
