from __future__ import annotations


def parse_boost_tags(raw: str) -> list[str]:
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def build_tag_scoring_parameters(param_name: str, tags: list[str]) -> list[str]:
    """
    Azure tag scoring profiles expose one query parameter (e.g. boostTags).

    Multiple tag values must be passed in a single scoringParameters entry:
    boostTags-maintenance,specifications,operation
    """
    if not tags:
        return []
    return [f"{param_name}-{','.join(tags)}"]
