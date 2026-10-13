from src.chunking.hierarchical import HierarchicalChunker, _split_table, _split_table_and_text
from src.models import ExtractedDocument, ManualMetadata
import tiktoken


def _doc(markdown: str) -> ExtractedDocument:
    return ExtractedDocument(
        source_file="sample.pdf",
        markdown_content=markdown,
        page_map=[],
        metadata=ManualMetadata(
            manufacturer="Acme",
            model_series=["Model X"],
            manual_type="service",
        ),
    )


def test_header_split_creates_section_path():
    markdown = """# Chapter 1

Intro paragraph.

## Troubleshooting

Engine overheating may occur when coolant is low.
"""
    chunker = HierarchicalChunker()
    chunks = chunker.chunk(_doc(markdown))
    assert chunks
    assert any("Troubleshooting" in c.section_path for c in chunks)
    assert any("Engine overheating" in c.raw_text for c in chunks)


def test_table_is_atomic_block():
    text = "Before table\n\n| Code | Meaning |\n| --- | --- |\n| E01 | Fault |\n\nAfter table"
    segments = _split_table_and_text(text)
    assert len(segments) == 3
    assert segments[0][1] is False
    assert segments[1][1] is True
    assert segments[2][1] is False


def test_html_table_is_atomic_block():
    text = (
        "Before table\n\n<table>\n<tr>\n<td>A</td>\n</tr>\n</table>\n\nAfter table"
    )
    segments = _split_table_and_text(text)
    assert len(segments) == 3
    assert segments[0][1] is False
    assert segments[1][1] is True
    assert "<table>" in segments[1][0]
    assert "</table>" in segments[1][0]
    assert segments[2][1] is False


def test_large_html_table_splits_with_repeated_header():
    encoding = tiktoken.get_encoding("cl100k_base")
    header = "<table>\n<tr><th>Code</th><th>Description</th></tr>\n"
    data_rows = [
        f"<tr><td>E{i:03d}</td><td>{'detail ' * 30}</td></tr>" for i in range(50)
    ]
    table = header + "\n".join(data_rows) + "\n</table>"
    parts = _split_table(table, encoding, max_tokens=300)
    assert len(parts) > 1
    for part in parts:
        assert "<th>Code</th>" in part
        assert part.strip().endswith("</table>")


def test_large_table_splits_with_repeated_header():
    encoding = tiktoken.get_encoding("cl100k_base")
    rows = ["| Code | Description |", "| --- | --- |"]
    rows.extend([f"| E{i:03d} | {'detail ' * 20} |" for i in range(40)])
    table = "\n".join(rows)
    parts = _split_table(table, encoding, max_tokens=300)
    assert len(parts) > 1
    for part in parts:
        assert part.startswith("| Code | Description |")
        assert "| --- | --- |" in part


def test_recursive_split_for_large_section():
    body = "\n\n".join([f"Paragraph {i}. " + ("word " * 120) for i in range(8)])
    markdown = f"# Chapter\n\n## Large Section\n\n{body}"
    chunker = HierarchicalChunker()
    chunks = chunker.chunk(_doc(markdown))
    assert len(chunks) > 1
    assert all(c.section_path.endswith("Large Section") for c in chunks)
