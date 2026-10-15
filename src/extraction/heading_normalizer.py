"""
Manual-agnostic heading hierarchy for pymupdf4llm layout output.

Works on the layout boxes of a ``ParsedDocument`` before markdown rendering:

1. Page margins: boxes classified (or positioned and repeated) as page
   headers/footers never become headings.
2. Top levels come from the PDF outline when supplied, otherwise from running
   page headers (e.g. "CHAPTER 2 ..." printed on every page of a chapter).
   Nested running headers (section above group) map to successive levels.
3. Numbered headings ("2.5", "2.5.1") get their level from the numbering depth.
4. Other headings nest by font size beneath the closest structural heading.
5. Text boxes that look like headings (short, larger or fully bold) are
   promoted; admonitions, captions, sentence-like "headings" and headings
   repeated on the following page are demoted to text.
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

import pymupdf as fitz

logger = logging.getLogger("oem_manuals.extraction")

Bookmark = tuple[int, str, int]  # (level, title, 1-based page number)

_MAX_LEVEL = 6
_HEADING_CLASSES = ("title", "section-header")
_MARGIN_CLASSES = ("page-header", "page-footer")
_TEXT_CLASSES = ("text", "title", "section-header", "page-header", "page-footer")
_MARGIN_BAND = 0.08
_BOILERPLATE_PAGE_FRACTION = 0.8
_RUN_GAP_PAGES = 3
_MAX_CONTEXT_LEVELS = 3
# Chapter title pages are often followed by pages without running headers
# (chapter TOC, cover art); the anchor search walks back across those.
_MAX_ANCHOR_LOOKBACK_PAGES = 40
_MAX_HEADING_CHARS = 150
_MAX_PROMOTED_CHARS = 100
_MIN_BOLD_FRACTION = 0.9

_NOT_HEADING = re.compile(
    r"^((warning|caution|danger|notes?|notice|important|tip|hint|yes|no)\b\W*"
    r"|(figure|fig\.|table|tab\.)\s*\d.*)$",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"[.,;:!?]$")
_MULTI_LEVEL_NUMBER = re.compile(r"^(\d{1,3}(?:\.\d{1,3})+)\.?\s+\S")
_SINGLE_LEVEL_NUMBER = re.compile(r"^\d{1,2}\.?\s+[A-Z]")
_NON_WORD = re.compile(r"[\W_]+")
_LETTER = re.compile(r"[^\W\d_]")


@dataclass
class _Heading:
    box: object
    key: str
    strength: float
    number_depth: int = 0
    single_numbered: bool = False
    # Fixed level for bookmark / running-header anchors; 0 = derive.
    level: int = 0


@dataclass
class _Run:
    key: str
    start: int
    end: int
    level: int = 1

    @property
    def length(self) -> int:
        return self.end - self.start


def normalize_headings(parsed, bookmarks: list[Bookmark] | None = None) -> dict[int, list[str]]:
    """
    Rewrite ``boxclass`` / ``header_level`` on ``parsed`` in place.

    Returns markdown heading lines to prepend per page number, for bookmarks
    whose title could not be matched to a box on their target page.
    """
    pages = parsed.pages or []
    texts = _BoxTexts()
    margin = _mark_margin_boxes(pages, texts)
    headings = _classify_headings(pages, margin, texts, _body_font_size(pages))

    inserts: dict[int, list[str]] = defaultdict(list)
    pending: dict[int, list[int]] = defaultdict(list)
    if bookmarks:
        base = _anchor_bookmarks(pages, margin, texts, headings, bookmarks, inserts, pending)
    else:
        base = _anchor_running_headers(pages, margin, texts, headings)

    _assign_levels(pages, headings, pending, base)
    return dict(inserts)


class _BoxTexts:
    def __init__(self) -> None:
        self._cache: dict[int, str] = {}

    def text(self, box) -> str:
        key = id(box)
        if key not in self._cache:
            self._cache[key] = " ".join(s["text"].strip() for s in _spans(box)).strip()
        return self._cache[key]


def _spans(box) -> list[dict]:
    return [s for line in (box.textlines or []) for s in line["spans"] if s["text"].strip()]


def _normalize(text: str) -> str:
    return _NON_WORD.sub(" ", text).strip().lower()


def _is_bold(span: dict) -> bool:
    return bool(
        span["flags"] & fitz.TEXT_FONT_BOLD
        or span.get("char_flags", 0) & fitz.mupdf.FZ_STEXT_BOLD
    )


def _bold_fraction(spans: list[dict]) -> float:
    total = sum(len(s["text"].strip()) for s in spans)
    bold = sum(len(s["text"].strip()) for s in spans if _is_bold(s))
    return bold / total if total else 0.0


def _body_font_size(pages) -> float:
    sizes: Counter[int] = Counter()
    for page in pages:
        for box in page.boxes:
            if box.boxclass in ("text", "list-item"):
                for span in _spans(box):
                    sizes[round(span["size"])] += len(span["text"])
    return sizes.most_common(1)[0][0] if sizes else 0.0


def _mark_margin_boxes(pages, texts: _BoxTexts) -> set[int]:
    """Classify running headers/footers, including ones the layout model mislabels."""
    zone_pages: Counter[str] = Counter()
    candidates: list[tuple[object, float, bool]] = []
    for page in pages:
        seen: set[str] = set()
        for box in page.boxes:
            if box.boxclass not in _TEXT_CLASSES or not texts.text(box):
                continue
            in_band = box.y1 <= page.height * _MARGIN_BAND or box.y0 >= page.height * (1 - _MARGIN_BAND)
            if box.boxclass in _MARGIN_CLASSES or in_band:
                candidates.append((box, page.height, box.boxclass in _MARGIN_CLASSES))
                seen.add(_normalize(texts.text(box)))
        zone_pages.update(seen)

    margin: set[int] = set()
    for box, height, classified in candidates:
        text = texts.text(box)
        if classified or not _LETTER.search(text) or zone_pages[_normalize(text)] >= 2:
            margin.add(id(box))
            box.boxclass = "page-header" if box.y0 < height / 2 else "page-footer"
            box.header_level = 0
    return margin


def _keeps_heading(text: str) -> bool:
    if not _LETTER.search(text) or len(text) > _MAX_HEADING_CHARS or _NOT_HEADING.match(text):
        return False
    return not (_SENTENCE_END.search(text) and not _MULTI_LEVEL_NUMBER.match(text))


def _looks_like_missed_heading(box, spans: list[dict], text: str, body_size: float) -> bool:
    if len(box.textlines) > 2 or not 3 <= len(text) <= _MAX_PROMOTED_CHARS:
        return False
    if not (text[0].isupper() or text[0].isdigit()) or not _keeps_heading(text):
        return False
    larger = max(s["size"] for s in spans) >= body_size + 1
    return larger or _bold_fraction(spans) >= _MIN_BOLD_FRACTION


def _classify_headings(pages, margin: set[int], texts: _BoxTexts, body_size: float) -> dict[int, _Heading]:
    headings: dict[int, _Heading] = {}
    for page in pages:
        for box in page.boxes:
            if id(box) in margin or box.boxclass not in ("text", *_HEADING_CLASSES):
                continue
            spans = _spans(box)
            text = texts.text(box)
            if not spans or not text:
                continue
            if box.boxclass in _HEADING_CLASSES:
                if not _keeps_heading(text):
                    box.boxclass = "text"
                    box.header_level = 0
                    continue
            elif not _looks_like_missed_heading(box, spans, text, body_size):
                continue
            headings[id(box)] = _make_heading(box, spans, text)
    return headings


def _make_heading(box, spans: list[dict], text: str, level: int = 0) -> _Heading:
    strength = round(max(s["size"] for s in spans))
    if _bold_fraction(spans) >= _MIN_BOLD_FRACTION:
        strength += 0.5
    if text.isupper():
        strength += 0.25
    numbered = _MULTI_LEVEL_NUMBER.match(text)
    return _Heading(
        box=box,
        key=_normalize(text),
        strength=strength,
        number_depth=numbered.group(1).count(".") + 1 if numbered else 0,
        single_numbered=not numbered and bool(_SINGLE_LEVEL_NUMBER.match(text)),
        level=level,
    )


def _anchor_bookmarks(
    pages,
    margin: set[int],
    texts: _BoxTexts,
    headings: dict[int, _Heading],
    bookmarks: list[Bookmark],
    inserts: dict[int, list[str]],
    pending: dict[int, list[int]],
) -> int:
    index_by_number = {page.page_number: i for i, page in enumerate(pages)}
    used: set[int] = set()
    depth = 0
    for level, title, page_number in bookmarks:
        index = index_by_number.get(page_number)
        if index is None:
            continue
        level = min(level, _MAX_LEVEL)
        depth = max(depth, level)
        target = _normalize(title)
        match = next(
            (
                box
                for box in pages[index].boxes
                if id(box) not in margin
                and id(box) not in used
                and box.boxclass in ("text", *_HEADING_CLASSES)
                and _normalize(texts.text(box)) == target
            ),
            None,
        )
        if match is None:
            inserts[page_number].append(f"{'#' * level} {title}")
            pending[index].append(level)
            continue
        used.add(id(match))
        heading = headings.get(id(match)) or _make_heading(match, _spans(match), texts.text(match))
        heading.level = level
        headings[id(match)] = heading
    return depth


def _anchor_running_headers(pages, margin: set[int], texts: _BoxTexts, headings: dict[int, _Heading]) -> int:
    occurrences: dict[str, list[int]] = defaultdict(list)
    first_box: dict[tuple[str, int], object] = {}
    for index, page in enumerate(pages):
        seen: set[str] = set()
        for box in page.boxes:
            if id(box) not in margin or box.boxclass != "page-header":
                continue
            text = texts.text(box)
            key = _normalize(text)
            if not _LETTER.search(text) or len(text) > _MAX_PROMOTED_CHARS or key in seen:
                continue
            seen.add(key)
            occurrences[key].append(index)
            first_box[(key, index)] = box

    boilerplate_limit = _BOILERPLATE_PAGE_FRACTION * len(pages)
    runs: list[_Run] = []
    for key, indices in occurrences.items():
        if len(indices) > boilerplate_limit:
            continue
        runs.extend(_split_runs(key, indices))

    header_pages = {index for indices in occurrences.values() for index in indices}
    used: set[int] = set()
    anchors: dict[int, tuple[_Heading | None, tuple[int, int]]] = {}
    for run in sorted(runs, key=lambda r: (r.start, -r.length)):
        anchor, position = _find_anchor(pages, headings, run, used, header_pages)
        if anchor is None:
            box = first_box[(run.key, run.start)]
            position = (run.start, pages[run.start].boxes.index(box))
        else:
            used.add(id(anchor.box))
        anchors[id(run)] = (anchor, position)

    def is_parent(other: _Run, run: _Run) -> bool:
        if other is run or other.start > run.start or other.end < run.end:
            return False
        if other.length != run.length:
            return other.length > run.length
        # Same span (e.g. a section with a single group): the earlier title is the parent.
        return anchors[id(other)][1] < anchors[id(run)][1]

    for run in runs:
        run.level = min(1 + sum(is_parent(other, run) for other in runs), _MAX_CONTEXT_LEVELS)
        anchor, _ = anchors[id(run)]
        if anchor is not None:
            anchor.level = run.level
        else:
            box = first_box[(run.key, run.start)]
            headings[id(box)] = _make_heading(box, _spans(box), texts.text(box), level=run.level)

    return max((run.level for run in runs), default=0)


def _split_runs(key: str, indices: list[int]) -> list[_Run]:
    runs: list[_Run] = []
    start = previous = indices[0]
    for index in indices[1:]:
        if index - previous > _RUN_GAP_PAGES:
            if previous > start:
                runs.append(_Run(key, start, previous))
            start = index
        previous = index
    if previous > start:
        runs.append(_Run(key, start, previous))
    return runs


def _find_anchor(
    pages,
    headings: dict[int, _Heading],
    run: _Run,
    used: set[int],
    header_pages: set[int],
) -> tuple[_Heading | None, tuple[int, int]]:
    """Body heading that introduces a running-header run (e.g. the chapter title page)."""
    first = run.start - 1
    while first > 0 and first not in header_pages and run.start - first < _MAX_ANCHOR_LOOKBACK_PAGES:
        first -= 1

    best: tuple[float, int, int] | None = None
    best_heading: _Heading | None = None
    for index in range(max(first, 0), run.start + 1):
        for order, box in enumerate(pages[index].boxes):
            heading = headings.get(id(box))
            if heading is None or heading.level or id(box) in used:
                continue
            if heading.key != run.key and not heading.key.endswith(f" {run.key}"):
                continue
            score = (heading.strength, index, -order)
            if best is None or score > best:
                best, best_heading = score, heading
    position = (best[1], -best[2]) if best else (run.start, 0)
    return best_heading, position


def _push_structural(stack: list[tuple[int, float | None]], level: int) -> int:
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, None))
    return level


def _push_plain(stack: list[tuple[int, float | None]], strength: float) -> int:
    while stack and stack[-1][1] is not None and stack[-1][1] <= strength:
        stack.pop()
    level = min((stack[-1][0] if stack else 0) + 1, _MAX_LEVEL)
    stack.append((level, strength))
    return level


def _assign_levels(pages, headings: dict[int, _Heading], pending: dict[int, list[int]], base: int) -> None:
    def numbering_depth(heading: _Heading) -> int:
        if heading.number_depth:
            return heading.number_depth
        return 1 if base == 0 and heading.single_numbered else 0

    depths = [numbering_depth(h) for h in headings.values() if not h.level and numbering_depth(h)]
    min_depth = min(depths, default=1)

    stack: list[tuple[int, float | None]] = []
    previous: tuple[str, int] | None = None
    for index, page in enumerate(pages):
        for level in pending.get(index, ()):
            _push_structural(stack, level)
        for box in page.boxes:
            heading = headings.get(id(box))
            if heading is None:
                continue
            repeated = previous is not None and previous[0] == heading.key and index - previous[1] == 1
            previous = (heading.key, index)
            if repeated and not heading.level:
                # Continuation heading such as "TABLE OF CONTENTS" on every TOC page.
                box.boxclass = "text"
                box.header_level = 0
                continue
            depth = numbering_depth(heading)
            if heading.level:
                level = _push_structural(stack, heading.level)
            elif depth:
                level = _push_structural(stack, min(base + depth - min_depth + 1, _MAX_LEVEL))
            else:
                level = _push_plain(stack, heading.strength)
            box.boxclass = "section-header"
            box.header_level = level
