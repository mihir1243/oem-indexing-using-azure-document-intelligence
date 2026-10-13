from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import tiktoken
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from src.config import Settings, get_settings
from src.extraction.extractor import page_for_offset
from src.chunking.metadata import manual_id_prefix
from src.models import Chunk, ExtractedDocument

_HEADER_SPLITS = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]

_TABLE_ROW_PATTERN = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")
_HTML_TABLE_OPEN_PATTERN = re.compile(r"<table\b", re.IGNORECASE)
_HTML_TABLE_CLOSE_PATTERN = re.compile(r"</table\s*>", re.IGNORECASE)
_HTML_TR_PATTERN = re.compile(r"<tr\b[^>]*>.*?</tr>", re.DOTALL | re.IGNORECASE)
_HTML_TABLE_TAG_PATTERN = re.compile(r"<table\b[^>]*>", re.IGNORECASE)


@dataclass
class _SectionContext:
    chapter_title: str
    section_title: str
    section_path: str


class HierarchicalChunker:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._encoding = tiktoken.get_encoding("cl100k_base")
        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=_HEADER_SPLITS,
            strip_headers=False,
        )
        self._recursive_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",
            chunk_size=self._settings.chunk_max_tokens,
            chunk_overlap=self._settings.chunk_overlap_tokens,
            separators=["\n\n", "\n- ", "\n* ", "\n1. ", ". ", "\n"],
        )

    def chunk(self, document: ExtractedDocument) -> list[Chunk]:
        prefix = manual_id_prefix(document.source_file)
        sections = self._header_splitter.split_text(document.markdown_content)
        chunks: list[Chunk] = []
        search_from = 0
        chunk_index = 0

        for section in sections:
            meta = section.metadata or {}
            context = _section_context_from_metadata(meta)
            segments = _split_table_and_text(section.page_content)

            for segment_text, is_table in segments:
                if not segment_text.strip():
                    continue

                if is_table:
                    pieces = _split_table(segment_text, self._encoding, self._settings.chunk_max_tokens)
                elif self._token_count(segment_text) > self._settings.chunk_max_tokens:
                    pieces = self._recursive_splitter.split_text(segment_text)
                else:
                    pieces = [segment_text]

                for piece in pieces:
                    raw_text = piece.strip()
                    if not raw_text:
                        continue
                    char_offset, search_from = _find_offset(
                        document.markdown_content, raw_text, search_from
                    )
                    enriched = (
                        f"{context.section_path}\n{raw_text}"
                        if context.section_path
                        else raw_text
                    )
                    chunk_id = _chunk_id(prefix, context.section_path, chunk_index, raw_text)
                    chunks.append(
                        Chunk(
                            id=chunk_id,
                            chunk_content=enriched,
                            raw_text=raw_text,
                            chapter_title=context.chapter_title,
                            section_title=context.section_title,
                            section_path=context.section_path,
                            page_number=page_for_offset(document.page_map, char_offset),
                            char_offset=char_offset,
                            metadata=document.metadata,
                        )
                    )
                    chunk_index += 1

        return chunks

    def _token_count(self, text: str) -> int:
        return len(self._encoding.encode(text))


def _section_context_from_metadata(meta: dict) -> _SectionContext:
    h1 = meta.get("h1", "") or ""
    h2 = meta.get("h2", "") or ""
    h3 = meta.get("h3", "") or ""
    h4 = meta.get("h4", "") or ""
    path_parts = [p for p in (h1, h2, h3, h4) if p]
    section_title = h4 or h3 or h2 or h1 or ""
    return _SectionContext(
        chapter_title=h1,
        section_title=section_title,
        section_path=" > ".join(path_parts),
    )


def _split_table_and_text(content: str) -> list[tuple[str, bool]]:
    lines = content.splitlines(keepends=True)
    segments: list[tuple[str, bool]] = []
    buffer: list[str] = []
    in_markdown_table = False
    in_html_table = False

    def flush(is_table: bool) -> None:
        nonlocal buffer
        if buffer:
            segments.append(("".join(buffer), is_table))
            buffer = []

    for line in lines:
        if in_html_table:
            buffer.append(line)
            if _HTML_TABLE_CLOSE_PATTERN.search(line):
                flush(True)
                in_html_table = False
            continue

        is_markdown_table_line = bool(_TABLE_ROW_PATTERN.match(line))
        if is_markdown_table_line:
            if buffer and not in_markdown_table:
                flush(False)
            in_markdown_table = True
            buffer.append(line)
            continue

        if in_markdown_table:
            flush(True)
            in_markdown_table = False

        if _HTML_TABLE_OPEN_PATTERN.search(line.lstrip()):
            if buffer:
                flush(False)
            in_html_table = True
            buffer.append(line)
            if _HTML_TABLE_CLOSE_PATTERN.search(line):
                flush(True)
                in_html_table = False
            continue

        buffer.append(line)

    if buffer:
        flush(in_markdown_table or in_html_table)

    return segments


def _split_table(text: str, encoding, max_tokens: int) -> list[str]:
    if _HTML_TABLE_OPEN_PATTERN.search(text.lstrip()):
        return _split_html_table(text, encoding, max_tokens)
    return _split_markdown_table(text, encoding, max_tokens)


def _split_html_table(text: str, encoding, max_tokens: int) -> list[str]:
    text = text.strip()
    if len(encoding.encode(text)) <= max_tokens:
        return [text]

    rows = _HTML_TR_PATTERN.findall(text)
    if len(rows) < 2:
        return [text]

    open_match = _HTML_TABLE_TAG_PATTERN.search(text)
    table_open = f"{open_match.group(0)}\n" if open_match else "<table>\n"

    header_count = 0
    for row in rows:
        if re.search(r"<th\b", row, re.IGNORECASE):
            header_count += 1
        else:
            break
    if header_count == 0:
        header_count = 1

    header_rows = rows[:header_count]
    data_rows = rows[header_count:]
    if not data_rows:
        return [text]

    prefix = table_open + "\n".join(header_rows) + "\n"
    suffix = "</table>"
    prefix_tokens = len(encoding.encode(prefix + suffix))

    target_body_tokens = max(200, max_tokens - prefix_tokens - 16)
    chunks: list[str] = []
    current_rows: list[str] = []

    def row_group_tokens(body_rows: list[str]) -> int:
        body = "\n".join(body_rows)
        return len(encoding.encode(f"{prefix}{body}\n{suffix}"))

    for row in data_rows:
        trial = current_rows + [row]
        if current_rows and row_group_tokens(trial) > target_body_tokens:
            body = "\n".join(current_rows)
            chunks.append(f"{prefix}{body}\n{suffix}")
            current_rows = [row]
        else:
            current_rows = trial

    if current_rows:
        body = "\n".join(current_rows)
        chunks.append(f"{prefix}{body}\n{suffix}")

    return [c.strip() for c in chunks if c.strip()]


def _split_markdown_table(text: str, encoding, max_tokens: int) -> list[str]:
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return [text.strip()]

    header = lines[0]
    separator = lines[1] if _TABLE_SEPARATOR_PATTERN.match(lines[1]) else None
    data_start = 2 if separator else 1
    data_rows = lines[data_start:]

    prefix_lines = [header]
    if separator:
        prefix_lines.append(separator)
    prefix = "\n".join(prefix_lines) + "\n"
    prefix_tokens = len(encoding.encode(prefix))

    if len(encoding.encode(text)) <= max_tokens:
        return [text.strip()]

    target_body_tokens = max(200, max_tokens - prefix_tokens - 16)
    chunks: list[str] = []
    current_rows: list[str] = []

    def row_group_tokens(rows: list[str]) -> int:
        body = "\n".join(rows)
        return len(encoding.encode(prefix + body))

    for row in data_rows:
        trial = current_rows + [row]
        if current_rows and row_group_tokens(trial) > target_body_tokens:
            chunks.append(prefix + "\n".join(current_rows))
            current_rows = [row]
        else:
            current_rows = trial

    if current_rows:
        chunks.append(prefix + "\n".join(current_rows))

    return [c.strip() for c in chunks if c.strip()]


def _find_offset(full_text: str, needle: str, start: int) -> tuple[int, int]:
    idx = full_text.find(needle, start)
    if idx == -1:
        idx = full_text.find(needle)
    if idx == -1:
        idx = start
    return idx, idx + max(len(needle), 1)


def _chunk_id(prefix: str, section_path: str, chunk_index: int, raw_text: str) -> str:
    digest = hashlib.sha256(f"{section_path}:{chunk_index}:{raw_text[:256]}".encode()).hexdigest()[
        :8
    ]
    return f"{prefix}_{chunk_index:06d}_{digest}"
