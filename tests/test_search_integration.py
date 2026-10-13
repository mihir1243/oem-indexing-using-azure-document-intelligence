import os

import pytest

from src.search.filters import build_filter
from src.search.retriever import ManualRetriever


@pytest.mark.integration
def test_live_search_requires_env():
    required = [
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_KEY",
        "OPENAI_API_KEY",
    ]
    if not all(os.getenv(key) for key in required):
        pytest.skip("Azure/OpenAI env vars not configured for integration test")

    retriever = ManualRetriever()
    results = retriever.search("engine overheating troubleshooting", top_k=3)
    assert isinstance(results, list)


def test_build_filter_composes_clauses():
    expr = build_filter(
        {
            "manufacturer": "GE Healthcare",
            "manual_type": "service",
            "model": "Voluson E10",
        }
    )
    assert expr is not None
    assert "manufacturer eq 'GE Healthcare'" in expr
    assert "manual_type eq 'service'" in expr
    assert "model_series/any(m: m eq 'Voluson E10')" in expr
