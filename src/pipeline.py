from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from src.chunking.hierarchical import HierarchicalChunker
from src.chunking.metadata import chunks_to_index_documents, manual_id_prefix
from src.embedding.embedder import Embedder
from src.config import get_settings
from src.extraction.load_or_extract import load_or_extract
from src.indexing.indexer import SearchIndexer
from src.models import BatchResult, IndexResult, ManualMetadata, SearchResult
from src.search.retriever import ManualRetriever

logger = logging.getLogger("oem_manuals.pipeline")


@dataclass
class ManifestEntry:
    file: str
    manufacturer: str
    model_series: list[str]
    manual_type: str


async def index_manual(
    pdf_path: Path,
    manufacturer: str,
    model_series: list[str],
    manual_type: str,
    *,
    delete_strategy: str = "manual_prefix",
    force_reextract: bool | None = None,
) -> IndexResult:
    metadata = ManualMetadata(
        manufacturer=manufacturer,
        model_series=model_series,
        manual_type=manual_type,
    )
    prefix = manual_id_prefix(pdf_path.name)
    manual_start = time.perf_counter()
    logger.info("Indexing manual: %s", pdf_path.name)

    chunker = HierarchicalChunker()
    embedder = Embedder()
    indexer = SearchIndexer()
    settings = get_settings()
    reextract = (
        settings.force_reextract if force_reextract is None else force_reextract
    )

    extracted, markdown_path, from_cache = await _run_step(
        "load_or_extract",
        load_or_extract,
        pdf_path,
        metadata,
        settings,
        force_reextract=reextract,
    )
    logger.info(
        "Extraction source: %s",
        "cached markdown" if from_cache else "liteparse",
    )

    chunks = await _run_step("chunking", chunker.chunk, extracted)
    logger.info("Chunk count: %d", len(chunks))
    vectors = await _run_step("openai_embeddings", embedder.embed_chunks, chunks)
    documents = await _run_step(
        "build_index_documents",
        chunks_to_index_documents,
        chunks,
        vectors,
    )

    if delete_strategy == "manufacturer_type":
        await _run_step(
            "azure_search_delete",
            indexer.delete_by_manufacturer_and_type,
            manufacturer,
            manual_type,
        )
    else:
        await _run_step(
            "azure_search_delete",
            indexer.delete_manual_chunks,
            prefix,
            manufacturer,
            manual_type,
        )

    uploaded = await _run_step("azure_search_upload", indexer.upload_documents, documents)

    logger.info(
        "Manual index complete: %s | %d chunks uploaded | total %.2fs",
        pdf_path.name,
        uploaded,
        time.perf_counter() - manual_start,
    )

    return IndexResult(
        source_file=pdf_path.name,
        chunks_indexed=uploaded,
        manual_id_prefix=prefix,
        markdown_path=str(markdown_path) if markdown_path else None,
        extraction_from_cache=from_cache,
    )


async def index_folder(
    folder: Path,
    manifest_path: Path,
    *,
    force_reextract: bool = False,
) -> BatchResult:
    folder = folder.resolve()
    manifest_path = manifest_path.resolve()
    entries = _load_manifest(manifest_path)
    batch_start = time.perf_counter()
    logger.info("Batch index started: %d manifest entries", len(entries))

    results: list[IndexResult] = []
    errors: list[str] = []

    for entry in entries:
        pdf_path = folder / entry.file
        if not pdf_path.exists():
            errors.append(f"Missing PDF: {pdf_path}")
            continue
        try:
            result = await index_manual(
                pdf_path=pdf_path,
                manufacturer=entry.manufacturer,
                model_series=entry.model_series,
                manual_type=entry.manual_type,
                force_reextract=force_reextract,
            )
            results.append(result)
        except Exception as exc:  # noqa: BLE001 - collect per-file failures for batch reporting
            errors.append(f"{entry.file}: {_format_error(exc)}")

    logger.info(
        "Batch index finished: %d succeeded, %d failed in %.2fs",
        len(results),
        len(errors),
        time.perf_counter() - batch_start,
    )
    return BatchResult(results=results, errors=errors)


def search(query: str, filters: dict | None = None, top_k: int = 10) -> list[SearchResult]:
    retriever = ManualRetriever()
    return retriever.search(query=query, filters=filters, top_k=top_k)


async def _run_step(step: str, func, /, *args, **kwargs):
    start = time.perf_counter()
    logger.info("Step started: %s", step)
    try:
        result = await asyncio.to_thread(func, *args, **kwargs)
    except Exception as exc:
        logger.error("Step failed: %s after %.2fs", step, time.perf_counter() - start)
        raise RuntimeError(f"{step}: {exc}") from exc
    logger.info("Step finished: %s in %.2fs", step, time.perf_counter() - start)
    return result


def _format_error(exc: BaseException) -> str:
    from tenacity import RetryError

    if isinstance(exc, RetryError) and exc.last_attempt.failed:
        cause = exc.last_attempt.exception()
        if cause is not None:
            return str(cause)
    cause = exc.__cause__
    if cause is not None:
        return str(cause)
    return str(exc)


def _load_manifest(manifest_path: Path) -> list[ManifestEntry]:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries: list[ManifestEntry] = []
    for item in raw:
        entries.append(
            ManifestEntry(
                file=item["file"],
                manufacturer=item["manufacturer"],
                model_series=list(item["model_series"]),
                manual_type=item["manual_type"],
            )
        )
    return entries
