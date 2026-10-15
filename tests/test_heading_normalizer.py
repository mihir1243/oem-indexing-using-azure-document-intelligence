from pymupdf4llm.helpers.document_layout import LayoutBox, PageLayout, ParsedDocument

from src.extraction.heading_normalizer import normalize_headings

_BODY = "Body text paragraph."


def _box(boxclass: str, text: str, y0: float = 300, size: float = 10, bold: bool = False) -> LayoutBox:
    span = {
        "text": text,
        "size": size,
        "flags": 16 if bold else 0,
        "char_flags": 0,
        "block": 0,
        "line": 0,
    }
    return LayoutBox(
        x0=50,
        y0=y0,
        x1=500,
        y1=y0 + size + 2,
        boxclass=boxclass,
        textlines=[{"bbox": (50, y0, 500, y0 + size + 2), "spans": [span]}],
    )


def _header(text: str) -> LayoutBox:
    return _box("page-header", text, y0=30, bold=True)


def _page(number: int, *boxes: LayoutBox) -> PageLayout:
    return PageLayout(
        page_number=number,
        width=612,
        height=792,
        boxes=[*boxes, _box("text", _BODY, y0=600)],
    )


def _doc(*pages: PageLayout) -> ParsedDocument:
    return ParsedDocument(pages=list(pages), toc=[], metadata={}, page_count=len(pages))


def _level(box: LayoutBox) -> int:
    return box.header_level if box.boxclass == "section-header" else 0


def _filler_pages(start: int, count: int, header: str) -> list[PageLayout]:
    return [_page(n, _header(header)) for n in range(start, start + count)]


def test_running_header_anchors_chapter_and_numbering_sets_depth() -> None:
    chapter = _box("section-header", "Chapter 1 SAFETY RULES", y0=80, size=14, bold=True)
    section = _box("section-header", "1.1 GENERAL", y0=120, size=12, bold=True)
    subsection = _box("section-header", "1.1.1 DECALS", y0=80, size=11, bold=True)
    warning = _box("section-header", "WARNING", y0=120, size=12, bold=True)
    missed = _box("text", "HOW TO CLOSE", y0=160, bold=True)
    header_1 = _header("CHAPTER 1 SAFETY RULES")
    header_2 = _header("CHAPTER 1 SAFETY RULES")
    parsed = _doc(
        _page(1, header_1, chapter, section),
        _page(2, header_2, subsection, warning, missed),
        _page(3, _header("CHAPTER 1 SAFETY RULES")),
        *_filler_pages(4, 3, "CHAPTER 2 OPERATION"),
    )

    normalize_headings(parsed)

    assert [_level(b) for b in (chapter, section, subsection, missed)] == [1, 2, 3, 4]
    assert warning.boxclass == "text"
    assert header_1.boxclass == header_2.boxclass == "page-header"


def test_nested_running_headers_map_to_successive_levels() -> None:
    first_page_headers = [_header("Engine"), _header("Basics")]
    group_heading = _box("section-header", "Group 20 Electrical", y0=80, size=22, bold=True)
    topic = _box("section-header", "Battery Charging", y0=140, size=16, bold=True)
    parsed = _doc(
        _page(1, *first_page_headers),
        _page(2, _header("Engine"), _header("Basics")),
        _page(3, _header("Engine"), _header("Basics")),
        _page(4, _header("Engine"), _header("Electrical"), group_heading, topic),
        _page(5, _header("Engine"), _header("Electrical")),
        _page(6, _header("Engine"), _header("Electrical")),
        *_filler_pages(7, 4, "Hydraulics"),
    )

    normalize_headings(parsed)

    engine, basics = first_page_headers
    assert (_level(engine), _level(basics)) == (1, 2)
    assert _level(group_heading) == 2
    assert _level(topic) == 3


def test_same_span_running_headers_use_title_order_for_parent() -> None:
    section = _box("section-header", "SECTION 9010 DIAGNOSTICS", y0=80, size=22, bold=True)
    toc = _box("section-header", "TABLE OF CONTENTS", y0=150, size=14, bold=True)
    group = _box("section-header", "Group 05 Checkout", y0=80, size=22, bold=True)
    parsed = _doc(
        _page(1, section, toc),
        _page(2, _box("text", "Contents listing.")),
        _page(3, _header("Diagnostics"), _header("Checkout"), group),
        _page(4, _header("Diagnostics"), _header("Checkout")),
        _page(5, _header("Diagnostics"), _header("Checkout")),
        *_filler_pages(6, 4, "Engine"),
    )

    normalize_headings(parsed)

    assert (_level(section), _level(group)) == (1, 2)


def test_unstructured_headings_nest_by_font_size() -> None:
    big = _box("section-header", "Overview", y0=80, size=16, bold=True)
    small = _box("section-header", "Scope", y0=120, size=12, bold=True)
    sibling = _box("section-header", "Audience", y0=160, size=12, bold=True)
    big_again = _box("section-header", "Installation", y0=200, size=16, bold=True)
    parsed = _doc(_page(1, big, small, sibling, big_again))

    normalize_headings(parsed)

    assert [_level(b) for b in (big, small, sibling, big_again)] == [1, 2, 2, 1]


def test_promotes_larger_text_and_demotes_non_headings() -> None:
    larger = _box("text", "HOT PARTS", y0=80, size=11)
    sentence = _box("text", "Do not touch the engine.", y0=120, bold=True)
    caption = _box("section-header", "Figure 3-1. Venturi Effect", y0=160, size=12, bold=True)
    label = _box("section-header", "PROCEDURE OR ACTION:", y0=200, bold=True)
    parsed = _doc(_page(1, larger, sentence, caption, label))

    normalize_headings(parsed)

    assert larger.boxclass == "section-header"
    assert sentence.boxclass == caption.boxclass == label.boxclass == "text"


def test_heading_repeated_on_next_page_is_demoted() -> None:
    first = _box("section-header", "TABLE OF CONTENTS", y0=80, size=14, bold=True)
    repeat = _box("section-header", "TABLE OF CONTENTS", y0=80, size=14, bold=True)
    parsed = _doc(_page(1, first), _page(2, repeat))

    normalize_headings(parsed)

    assert first.boxclass == "section-header"
    assert repeat.boxclass == "text"


def test_mislabelled_repeated_top_band_box_becomes_page_header() -> None:
    boxes = [_box("section-header", "Diagnostic Trouble Codes", y0=38, bold=True) for _ in range(3)]
    parsed = _doc(*[_page(n, box) for n, box in enumerate(boxes, start=1)])

    normalize_headings(parsed)

    assert all(box.boxclass == "page-header" for box in boxes)


def test_single_mislabelled_running_header_matches_classified_ones() -> None:
    mislabelled = _box("section-header", "Diagnostic Trouble Codes", y0=38, bold=True)
    parsed = _doc(
        _page(1, _header("Diagnostic Trouble Codes")),
        _page(2, mislabelled),
    )

    normalize_headings(parsed)

    assert mislabelled.boxclass == "page-header"


def test_bookmarks_set_top_levels_and_insert_unmatched_titles() -> None:
    group = _box("section-header", "Group 10 Principles of Operation", y0=80, size=22, bold=True)
    topic = _box("section-header", "Engine Basics", y0=140, size=16, bold=True)
    header = _header("Engine")
    parsed = _doc(_page(1, _box("text", "Cover text.")), _page(2, header, group, topic), _page(3, _header("Engine")))

    inserts = normalize_headings(
        parsed,
        bookmarks=[(1, "SECTION 9020 Engine", 1), (2, "Group 10 - Principles of Operation", 2)],
    )

    assert inserts == {1: ["# SECTION 9020 Engine"]}
    assert (_level(group), _level(topic)) == (2, 3)
    assert header.boxclass == "page-header"
