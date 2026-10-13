from __future__ import annotations

import json
from pathlib import Path

from src.models import ExtractedDocument, ManualMetadata, PageSpan


def markdown_path_for(source_file: str, output_dir: Path) -> Path:
    output_dir = output_dir.resolve()
    stem = Path(source_file).stem
    return output_dir / f"{stem}.md"


def page_map_path_for(source_file: str, output_dir: Path) -> Path:
    output_dir = output_dir.resolve()
    stem = Path(source_file).stem
    return output_dir / f"{stem}.page_map.json"


def save_extracted_markdown(extracted: ExtractedDocument, output_dir: Path) -> Path:
    """Write Azure Document Intelligence markdown output and page map to disk."""
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = markdown_path_for(extracted.source_file, output_dir)
    md_path.write_text(extracted.markdown_content, encoding="utf-8")

    map_path = page_map_path_for(extracted.source_file, output_dir)
    map_path.write_text(
        json.dumps(_serialize_page_map(extracted.page_map), indent=2),
        encoding="utf-8",
    )
    return md_path


def load_cached_extraction(
    source_file: str,
    output_dir: Path,
    metadata: ManualMetadata,
) -> ExtractedDocument | None:
    """Load a prior extraction from disk when markdown cache exists."""
    md_path = markdown_path_for(source_file, output_dir)
    if not md_path.is_file():
        return None

    markdown_content = md_path.read_text(encoding="utf-8")
    page_map = _load_page_map(page_map_path_for(source_file, output_dir))

    return ExtractedDocument(
        source_file=source_file,
        markdown_content=markdown_content,
        page_map=page_map,
        metadata=metadata,
    )


def _serialize_page_map(page_map: list[PageSpan]) -> list[dict[str, int]]:
    return [
        {"start": span.start, "end": span.end, "page_number": span.page_number}
        for span in page_map
    ]


def _load_page_map(path: Path) -> list[PageSpan]:
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        PageSpan(
            start=int(item["start"]),
            end=int(item["end"]),
            page_number=int(item["page_number"]),
        )
        for item in raw
    ]
