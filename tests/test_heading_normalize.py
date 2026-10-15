from pathlib import Path

from src.extraction.heading_normalize import (
    normalize_marker_headings,
    normalize_marker_headings_with_page_map,
)
from src.models import PageSpan


def test_safety_callouts_are_not_headings():
    md = "# **Chapter 1 Foo**\n\n# **WARNING**\n\nStay alert.\n"
    out = normalize_marker_headings(md)
    assert "# **WARNING**" not in out
    assert "**WARNING**" in out
    assert out.startswith("# **Chapter 1 Foo**")


def test_toc_chapter_lines_become_list_items():
    md = (
        "# **TABLE OF CONTENTS**\n\n"
        "# **CHAPTER 1 SAFETY**\n\n"
        "# **CHAPTER 2 OPERATION**\n\n"
        "# **Chapter 1 SAFETY**\n\n"
        "Body text.\n"
    )
    out = normalize_marker_headings(md)
    assert "- **CHAPTER 1 SAFETY**" in out
    assert "- **CHAPTER 2 OPERATION**" in out
    assert "# **Chapter 1 SAFETY**" in out


def test_numbered_sections_get_depth():
    md = "## **1.1 GENERAL**\n\n### **1.1.1 Detail**\n"
    out = normalize_marker_headings(md)
    assert "## **1.1 GENERAL**" in out
    assert "### **1.1.1 Detail**" in out


def test_caterpillar_manual_h1_count_drops():
    path = Path("extracted/caterpiller manual.md")
    if not path.is_file():
        return
    raw = path.read_text(encoding="utf-8")
    out = normalize_marker_headings(raw)
    h1_before = sum(1 for line in raw.splitlines() if line.startswith("# ") and not line.startswith("## "))
    h1_after = sum(1 for line in out.splitlines() if line.startswith("# ") and not line.startswith("## "))
    assert h1_before > 100
    assert h1_after < 40


def test_page_map_preserved_after_normalize():
    md = "Page one\n\nPage two"
    page_map = [
        PageSpan(start=0, end=8, page_number=1),
        PageSpan(start=10, end=18, page_number=2),
    ]
    new_md, new_map = normalize_marker_headings_with_page_map(md, page_map)
    assert len(new_map) == 2
    assert new_map[0].page_number == 1
    assert new_map[1].page_number == 2
    assert new_md[new_map[0].start : new_map[0].end] == "Page one"
    assert new_md[new_map[1].start : new_map[1].end] == "Page two"
