from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
)
from rich.console import Console

from src.config import get_settings

console = Console()

REQUIRED_FIELDS = (
    "section_title",
    "chunk_content",
    "section_path",
    "manufacturer",
    "manual_type",
)


def build_semantic_search(config_name: str) -> SemanticSearch:
    return SemanticSearch(
        default_configuration_name=config_name,
        configurations=[
            SemanticConfiguration(
                name=config_name,
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="section_title"),
                    content_fields=[SemanticField(field_name="chunk_content")],
                    keywords_fields=[
                        SemanticField(field_name="section_path"),
                        SemanticField(field_name="manufacturer"),
                        SemanticField(field_name="manual_type"),
                    ],
                ),
            )
        ],
    )


def main() -> int:
    settings = get_settings()
    client = SearchIndexClient(
        endpoint=settings.azure_search_endpoint,
        credential=AzureKeyCredential(settings.azure_search_key),
    )

    index = client.get_index(settings.azure_search_index_name)
    field_names = {field.name for field in index.fields}
    missing = [name for name in REQUIRED_FIELDS if name not in field_names]
    if missing:
        console.print(f"[red]Index is missing fields required for semantic config:[/red] {missing}")
        return 1

    config_name = settings.semantic_configuration_name
    index.semantic_search = build_semantic_search(config_name)

    try:
        client.create_or_update_index(index)
    except HttpResponseError as exc:
        console.print(f"[red]Failed to update index semantic configuration:[/red] {exc}")
        console.print(
            "Semantic search requires a supported Azure AI Search SKU "
            "(Basic or higher with semantic ranking enabled on the service)."
        )
        return 1

    updated = client.get_index(settings.azure_search_index_name)
    configs = (updated.semantic_search.configurations or []) if updated.semantic_search else []
    names = [cfg.name for cfg in configs]
    console.print(
        f"[green]Semantic configuration enabled[/green] on index "
        f"[bold]{settings.azure_search_index_name}[/bold]: {names}"
    )
    console.print(
        "Set in `.env`:\n"
        f"  USE_SEMANTIC_SEARCH=true\n"
        f"  SEMANTIC_CONFIGURATION_NAME={config_name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
