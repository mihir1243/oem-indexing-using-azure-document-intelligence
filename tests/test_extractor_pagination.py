from src.extraction.extractor import _split_paginated_markdown, page_for_offset
from src.models import PageSpan


def _page_sep(page_idx: int) -> str:
    return f"\n\n{{{page_idx}}}" + ("-" * 48) + "\n\n"


def test_split_paginated_markdown_builds_page_map_and_offsets():
    raw = _page_sep(0) + "Alpha line" + _page_sep(1) + "Beta line"
    markdown, page_map = _split_paginated_markdown(raw)

    assert markdown == "Alpha line\n\nBeta line"
    assert len(page_map) == 2
    assert page_map[0] == PageSpan(start=0, end=10, page_number=1)
    assert page_map[1].start == 12
    assert page_map[1].end == 21
    assert page_map[1].page_number == 2

    assert page_for_offset(page_map, 0) == 1
    assert page_for_offset(page_map, 9) == 1
    assert page_for_offset(page_map, 12) == 2
    assert page_for_offset(page_map, 20) == 2


def test_split_paginated_markdown_without_separators_single_page():
    markdown, page_map = _split_paginated_markdown("Only one page")
    assert markdown == "Only one page"
    assert page_map == [PageSpan(start=0, end=13, page_number=1)]
    assert page_for_offset(page_map, 5) == 1
