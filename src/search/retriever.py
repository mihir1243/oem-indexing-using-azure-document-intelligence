from __future__ import annotations

import logging
import time

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from src.config import Settings, get_settings
from src.embedding.embedder import Embedder
from src.models import SearchResult
from src.search.filters import build_filter
from src.search.scoring_params import build_tag_scoring_parameters, parse_boost_tags

logger = logging.getLogger("oem_manuals.search")


class ManualRetriever:
    def __init__(
        self,
        settings: Settings | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._embedder = embedder or Embedder(self._settings)
        self._client = SearchClient(
            endpoint=self._settings.azure_search_endpoint,
            index_name=self._settings.azure_search_index_name,
            credential=AzureKeyCredential(self._settings.azure_search_key),
        )

    def search(
        self,
        query: str,
        filters: dict | None = None,
        top_k: int = 10,
    ) -> list[SearchResult]:
        search_start = time.perf_counter()

        embed_start = time.perf_counter()
        query_vector = self._embedder.embed_query(query)
        logger.info(
            "Search step finished: embed_query in %.2fs",
            time.perf_counter() - embed_start,
        )

        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=max(top_k, 50),
            fields="content_vector",
        )

        filter_expr = build_filter(filters or {})
        search_kwargs: dict = {
            "search_text": query,
            "vector_queries": [vector_query],
            "filter": filter_expr,
            "top": top_k,
            "select": [
                "id",
                "chunk_content",
                "raw_text",
                "section_path",
                "chapter_title",
                "section_title",
                "page_number",
                "manufacturer",
                "model_series",
                "manual_type",
            ],
        }
        if self._settings.use_semantic_search:
            search_kwargs["query_type"] = "semantic"
            search_kwargs["semantic_configuration_name"] = (
                self._settings.semantic_configuration_name
            )

        scoring_params = _resolve_scoring_parameters(self._settings)
        if self._settings.use_scoring_profile:
            search_kwargs["scoring_profile"] = self._settings.scoring_profile_name
        if scoring_params:
            search_kwargs["scoring_parameters"] = scoring_params

        azure_start = time.perf_counter()
        results = self._client.search(**search_kwargs)

        parsed: list[SearchResult] = []
        for item in results:
            parsed.append(
                SearchResult(
                    id=item.get("id", ""),
                    chunk_content=item.get("chunk_content", ""),
                    raw_text=item.get("raw_text", ""),
                    section_path=item.get("section_path", ""),
                    chapter_title=item.get("chapter_title", ""),
                    section_title=item.get("section_title", ""),
                    page_number=int(item.get("page_number") or 0),
                    manufacturer=item.get("manufacturer", ""),
                    model_series=list(item.get("model_series") or []),
                    manual_type=item.get("manual_type", ""),
                    score=float(item.get("@search.reranker_score") or item.get("@search.score") or 0.0),
                )
            )
        logger.info(
            "Search step finished: azure_search in %.2fs (%d results)",
            time.perf_counter() - azure_start,
            len(parsed),
        )
        logger.info("Search complete in %.2fs", time.perf_counter() - search_start)
        return parsed


def _resolve_scoring_parameters(settings: Settings) -> list[str]:
    if not settings.use_scoring_profile and not settings.send_scoring_parameters:
        return []

    boost_tags = parse_boost_tags(settings.scoring_boost_tags)
    if not boost_tags:
        boost_tags = ["troubleshooting"]

    return build_tag_scoring_parameters(
        settings.scoring_boost_parameter_name,
        boost_tags,
    )
