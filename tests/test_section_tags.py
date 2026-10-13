from src.chunking.section_tags import derive_section_tags


def test_troubleshooting_tag():
    tags = derive_section_tags(
        "Chapter 10 TROUBLESHOOTING",
        "10.4 Water temperature",
        "Chapter 10 TROUBLESHOOTING > 10.4 Water temperature",
    )
    assert "troubleshooting" in tags


def test_general_fallback():
    tags = derive_section_tags("Introduction", "Overview", "Introduction > Overview")
    assert tags == ["general"]
