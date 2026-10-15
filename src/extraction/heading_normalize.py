from __future__ import annotations

import re

from src.models import PageSpan

# Standalone safety callouts — not document structure.
_SAFETY_HEADING = re.compile(
    r"^#{1,6}\s+\*\*(WARNING|DANGER|CAUTION|NOTE:?)\*\*\s*$",
    re.IGNORECASE,
)

_CHAPTER_ALL_CAPS = re.compile(
    r"^#{1,6}\s+\*\*((?:CHAPTER)\s+\d+.+?)\*\*\s*$",
)

_CHAPTER_BODY = re.compile(
    r"^#{1,6}\s+\*\*((?:Chapter)\s+\d+.+?)\*\*\s*$",
)

_TOC_START = re.compile(r"^#{1,6}\s+\*\*TABLE OF CONTENTS\*\*\s*$", re.IGNORECASE)

_NUMBERED_SECTION = re.compile(
    r"^#{1,6}\s+\*\*((\d+(?:\.\d+)+)\s+.+?)\*\*\s*$",
)


def normalize_marker_headings(markdown: str) -> str:
    """Normalize a full markdown document (single pass, no page boundaries)."""
    normalized, _ = _normalize_lines(markdown.splitlines(), in_toc=False)
    return "\n".join(normalized)


def normalize_marker_headings_with_page_map(
    markdown: str,
    page_map: list[PageSpan],
) -> tuple[str, list[PageSpan]]:
    """Normalize headings page-by-page so page_map offsets stay aligned."""
    if not page_map:
        return normalize_marker_headings(markdown), page_map

    in_toc = False
    parts: list[str] = []
    new_map: list[PageSpan] = []
    offset = 0

    for span in page_map:
        chunk = markdown[span.start : span.end]
        lines, in_toc = _normalize_lines(chunk.splitlines(), in_toc=in_toc)
        norm = "\n".join(lines)
        if parts:
            offset += 2
        start = offset
        offset += len(norm)
        parts.append(norm)
        new_map.append(PageSpan(start=start, end=offset, page_number=span.page_number))

    return "\n\n".join(parts), new_map


def _normalize_lines(lines: list[str], *, in_toc: bool) -> tuple[list[str], bool]:
    out: list[str] = []

    for line in lines:
        if _TOC_START.match(line):
            in_toc = True
            out.append(line)
            continue

        if in_toc and _CHAPTER_ALL_CAPS.match(line):
            title = _CHAPTER_ALL_CAPS.match(line).group(1)
            out.append(f"- **{title}**")
            continue

        if in_toc and _CHAPTER_BODY.match(line):
            in_toc = False
            out.append(_to_heading(1, _CHAPTER_BODY.match(line).group(1)))
            continue

        safety = _SAFETY_HEADING.match(line)
        if safety:
            label = safety.group(1)
            if label.upper() == "NOTE" and not label.endswith(":"):
                label = "NOTE:"
            out.append(f"**{label}**")
            continue

        chapter = _CHAPTER_BODY.match(line)
        if chapter:
            out.append(_to_heading(1, chapter.group(1)))
            continue

        numbered = _NUMBERED_SECTION.match(line)
        if numbered:
            title = numbered.group(1)
            section_id = numbered.group(2)
            level = min(section_id.count(".") + 1, 4)
            out.append(_to_heading(level, title))
            continue

        if line.startswith("# ") and not line.startswith("## "):
            text = _strip_heading_markup(line)
            if _is_front_matter_h1(text):
                out.append(line)
            else:
                out.append(_to_heading(2, text.strip("*")))
            continue

        out.append(line)

    return out, in_toc


def _to_heading(level: int, title: str) -> str:
    level = max(1, min(level, 4))
    hashes = "#" * level
    clean = title.strip()
    if not clean.startswith("**"):
        clean = f"**{clean}**"
    return f"{hashes} {clean}"


def _strip_heading_markup(line: str) -> str:
    return re.sub(r"^#{1,6}\s+", "", line).strip()


def _is_front_matter_h1(text: str) -> bool:
    plain = re.sub(r"\*+", "", text).strip().upper()
    front_matter = {
        "OPERATION & MAINTENANCE MANUAL",
        "FOREWORD",
        "HOW TO USE THIS MANUAL",
        "MODELS COVERED IN THIS MANUAL",
        "LOCKOUT/TAGOUT",
        "TABLE OF CONTENTS",
        "INDEX",
    }
    return plain in front_matter or plain.startswith("OPERATION & MAINTENANCE MANUAL")
