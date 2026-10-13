from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PageSpan:
    start: int
    end: int
    page_number: int


@dataclass
class ManualMetadata:
    manufacturer: str
    model_series: list[str]
    manual_type: str


@dataclass
class ExtractedDocument:
    source_file: str
    markdown_content: str
    page_map: list[PageSpan]
    metadata: ManualMetadata


@dataclass
class Chunk:
    id: str
    chunk_content: str
    raw_text: str
    chapter_title: str
    section_title: str
    section_path: str
    page_number: int
    char_offset: int
    metadata: ManualMetadata


@dataclass
class IndexDocument:
    id: str
    manufacturer: str
    model_series: list[str]
    manual_type: str
    page_number: int
    chapter_title: str
    section_title: str
    section_path: str
    chunk_content: str
    raw_text: str
    section_tags: list[str] = field(default_factory=list)
    content_vector: list[float] = field(default_factory=list)

    def to_search_dict(self) -> dict:
        payload = {
            "id": self.id,
            "manufacturer": self.manufacturer,
            "model_series": self.model_series,
            "manual_type": self.manual_type,
            "page_number": self.page_number,
            "chapter_title": self.chapter_title,
            "section_title": self.section_title,
            "section_path": self.section_path,
            "chunk_content": self.chunk_content,
            "raw_text": self.raw_text,
            "content_vector": self.content_vector,
        }
        if self.section_tags:
            payload["section_tags"] = self.section_tags
        return payload


@dataclass
class IndexResult:
    source_file: str
    chunks_indexed: int
    manual_id_prefix: str
    markdown_path: str | None = None
    extraction_from_cache: bool = False


@dataclass
class BatchResult:
    results: list[IndexResult]
    errors: list[str]


@dataclass
class SearchResult:
    id: str
    chunk_content: str
    raw_text: str
    section_path: str
    chapter_title: str
    section_title: str
    page_number: int
    manufacturer: str
    model_series: list[str]
    manual_type: str
    score: float
