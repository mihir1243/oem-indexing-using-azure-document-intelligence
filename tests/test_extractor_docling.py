from docling_core.types.doc import BoundingBox, DoclingDocument
from docling_core.types.doc.common.reference import ProvenanceItem
from docling_core.types.doc.items.table.table_data import TableCell, TableData

from src.config import Settings
from src.extraction.docling_export import build_markdown_and_page_map
from src.extraction.extractor import build_pdf_pipeline_options, page_for_offset


def _settings_base() -> dict[str, object]:
    return {
        "azure_search_endpoint": "https://example.search.windows.net",
        "azure_search_key": "k",
        "openai_api_key": "k",
    }


def _sample_table_data() -> TableData:
    cells = [
        TableCell(
            text="Col1",
            row_span=1,
            col_span=1,
            start_row_offset_idx=0,
            end_row_offset_idx=1,
            start_col_offset_idx=0,
            end_col_offset_idx=1,
            column_header=True,
        ),
        TableCell(
            text="Col2",
            row_span=1,
            col_span=1,
            start_row_offset_idx=0,
            end_row_offset_idx=1,
            start_col_offset_idx=1,
            end_col_offset_idx=2,
            column_header=True,
        ),
        TableCell(
            text="v1",
            row_span=1,
            col_span=1,
            start_row_offset_idx=1,
            end_row_offset_idx=2,
            start_col_offset_idx=0,
            end_col_offset_idx=1,
        ),
        TableCell(
            text="v2",
            row_span=1,
            col_span=1,
            start_row_offset_idx=1,
            end_row_offset_idx=2,
            start_col_offset_idx=1,
            end_col_offset_idx=2,
        ),
    ]
    return TableData(table_cells=cells, num_rows=2, num_cols=2)


def test_build_pdf_pipeline_options_enables_heading_hierarchy_by_default():
    opts = build_pdf_pipeline_options(Settings(**_settings_base()))
    assert opts.heading_hierarchy_options.enabled is True
    assert opts.generate_parsed_pages is True


def test_build_pdf_pipeline_options_can_disable_heading_hierarchy():
    opts = build_pdf_pipeline_options(
        Settings(**_settings_base(), docling_heading_hierarchy=False)
    )
    assert opts.heading_hierarchy_options.enabled is False
    assert opts.generate_parsed_pages is False


def test_build_markdown_emits_html_tables_and_page_spans():
    doc = DoclingDocument(name="fixture")
    doc.add_page(page_no=1, size={"width": 612, "height": 792})
    prov = ProvenanceItem(
        page_no=1,
        bbox=BoundingBox(l=0, t=0, r=100, b=100),
        charspan=(0, 0),
    )
    doc.add_table(data=_sample_table_data(), prov=prov)
    doc.add_page(page_no=2, size={"width": 612, "height": 792})

    markdown, page_map = build_markdown_and_page_map(doc)

    assert "<table" in markdown.lower()
    assert "</table>" in markdown.lower()
    assert "| Col1 |" not in markdown

    assert len(page_map) == 2
    assert page_map[0].start == 0
    assert page_map[0].page_number == 1
    assert page_map[1].page_number == 2
    assert page_map[0].end <= page_map[1].start
    assert page_map[-1].end == len(markdown)

    assert page_for_offset(page_map, 0) == 1
    assert page_for_offset(page_map, page_map[1].start) == 2
