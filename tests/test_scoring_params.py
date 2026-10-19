from src.config import Settings
from src.search.retriever import _resolve_scoring_parameters
from src.search.scoring_params import build_tag_scoring_parameters, parse_boost_tags


def test_build_tag_scoring_parameters_single_entry():
    tags = parse_boost_tags("maintenance,specifications,operation")
    assert build_tag_scoring_parameters("boostTags", tags) == [
        "boostTags-maintenance,specifications,operation"
    ]


def test_resolve_scoring_parameters_only_when_enabled():
    base = {
        "azure_search_endpoint": "https://example.search.windows.net",
        "azure_search_key": "k",
        "openai_api_key": "k",
        "scoring_boost_tags": "troubleshooting",
    }
    disabled = Settings(**base, use_scoring_profile=False, send_scoring_parameters=False)
    assert _resolve_scoring_parameters(disabled) == []

    enabled = Settings(**base, use_scoring_profile=True)
    assert _resolve_scoring_parameters(enabled) == ["boostTags-troubleshooting"]
