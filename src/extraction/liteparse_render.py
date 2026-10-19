from __future__ import annotations

import html
from typing import Any

from src.models import PageSpan


def render_pages(pages: list[Any]) -> tuple[str, list[PageSpan]]:
    """Turn LiteParse pages (with layout blocks) into markdown with HTML tables."""
    page_texts: list[str] = []
    page_numbers: list[int] = []
    for page in pages:
        page_numbers.append(_page_number(page))
        blocks = _get(page, "blocks")
        if blocks:
            page_texts.append(_render_page_blocks(blocks))
        else:
            page_texts.append(_get(page, "text") or "")

    if not page_texts:
        return "", []

    markdown_parts: list[str] = []
    page_map: list[PageSpan] = []
    offset = 0
    for index, (page_number, page_text) in enumerate(zip(page_numbers, page_texts, strict=True)):
        if index > 0:
            markdown_parts.append("\n\n")
            offset += 2
        start = offset
        markdown_parts.append(page_text)
        offset += len(page_text)
        page_map.append(PageSpan(start=start, end=offset, page_number=page_number))

    return "".join(markdown_parts), page_map


def _render_page_blocks(blocks: list[Any]) -> str:
    rendered: list[str] = []
    for block in blocks:
        piece = _render_block(block)
        if piece:
            rendered.append(piece)
    return "\n".join(rendered)


def _render_block(block: Any) -> str | None:
    kind = _get(block, "kind")
    if kind == "rule":
        return None
    if kind == "figure":
        return None
    if kind == "heading":
        level = max(1, min(6, int(_get(block, "level") or 1)))
        text = (_get(block, "text") or "").strip()
        return f"{'#' * level} {text}".rstrip()
    if kind == "paragraph":
        return (_get(block, "text") or "").strip()
    if kind == "list_item":
        return _render_list_item(block)
    if kind == "code":
        return _render_code_block(block)
    if kind == "grid_fallback":
        return _render_grid_fallback(block)
    if kind == "table":
        return f"\n{_render_table_html(block)}\n"
    return (_get(block, "text") or "").strip() or None


def _render_list_item(block: Any) -> str:
    text = (_get(block, "text") or "").strip()
    level = max(1, int(_get(block, "level") or 1))
    indent = "  " * (level - 1)
    ordered = _get(block, "ordered")
    marker = _get(block, "marker")
    if marker:
        prefix = f"{marker} "
    elif ordered:
        prefix = "1. "
    else:
        prefix = "- "
    return f"{indent}{prefix}{text}".rstrip()


def _render_code_block(block: Any) -> str:
    lang = (_get(block, "lang") or "").strip()
    lines = _get(block, "lines") or []
    body = "\n".join(str(line) for line in lines)
    return f"```{lang}\n{body}\n```"


def _render_grid_fallback(block: Any) -> str:
    lines = _get(block, "lines") or []
    body = "\n".join(str(line) for line in lines)
    return f"```\n{body}\n```"


def _render_table_html(block: Any) -> str:
    header_cells = _get(block, "header") or []
    rows = _get(block, "rows") or []
    ncol = len(header_cells)
    for row in rows:
        ncol = max(ncol, len(row))

    parts = ["<table>"]
    if header_cells:
        parts.append("<thead><tr>")
        for cell in _pad_row(header_cells, ncol):
            parts.append(f"<th>{_cell_html(cell)}</th>")
        parts.append("</tr></thead>")

    parts.append("<tbody>")
    for row in rows:
        parts.append("<tr>")
        for cell in _pad_row(row, ncol):
            parts.append(f"<td>{_cell_html(cell)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _pad_row(row: list[Any], ncol: int) -> list[Any]:
    if len(row) >= ncol:
        return row
    return list(row) + [None] * (ncol - len(row))


def _cell_html(cell: Any) -> str:
    if cell is None:
        return ""
    text = _get(cell, "text") if not isinstance(cell, str) else cell
    text = text or ""
    return html.escape(str(text)).replace("\n", "<br>")


def _page_number(page: Any) -> int:
    return int(_get(page, "page_num") or _get(page, "page") or 1)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
