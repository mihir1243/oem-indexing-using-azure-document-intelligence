from __future__ import annotations

import base64
import hashlib

from src.chunking.section_tags import derive_section_tags
from src.models import Chunk, IndexDocument, ManualMetadata


def chunks_to_index_documents(
    chunks: list[Chunk],
    vectors: dict[str, list[float]],
) -> list[IndexDocument]:
    documents: list[IndexDocument] = []
    for chunk in chunks:
        vector = vectors.get(chunk.id)
        if vector is None:
            raise ValueError(f"Missing embedding vector for chunk id={chunk.id}")

        meta: ManualMetadata = chunk.metadata
        documents.append(
            IndexDocument(
                id=chunk.id,
                manufacturer=meta.manufacturer,
                model_series=list(meta.model_series),
                manual_type=meta.manual_type,
                page_number=chunk.page_number,
                chapter_title=chunk.chapter_title,
                section_title=chunk.section_title,
                section_path=chunk.section_path,
                chunk_content=chunk.chunk_content,
                raw_text=chunk.raw_text,
                section_tags=derive_section_tags(
                    chunk.chapter_title,
                    chunk.section_title,
                    chunk.section_path,
                ),
                content_vector=vector,
            )
        )
    return documents


def manual_id_prefix(source_file: str) -> str:
    return hashlib.sha256(source_file.encode("utf-8")).hexdigest()[:16]


def azure_safe_id(raw_id: str) -> str:
    """Encode id for Azure Search if it contains characters outside allowed set."""
    if raw_id.replace("_", "").replace("-", "").isalnum():
        return raw_id
    digest = hashlib.sha256(raw_id.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
