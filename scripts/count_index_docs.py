from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rich.console import Console

from src.config import get_settings
from src.indexing.indexer import SearchIndexer
from src.search.filters import build_filter

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="Count documents in the Azure Search index.")
    parser.add_argument("--manufacturer", type=str)
    parser.add_argument("--manual-type", type=str)
    parser.add_argument("--model", type=str)
    args = parser.parse_args()

    settings = get_settings()
    indexer = SearchIndexer()
    filters = {}
    if args.manufacturer:
        filters["manufacturer"] = args.manufacturer
    if args.manual_type:
        filters["manual_type"] = args.manual_type
    if args.model:
        filters["model"] = args.model

    filter_expr = build_filter(filters)

    count = indexer.count_documents(filter_expr)

    console.print(f"Index: [bold]{settings.azure_search_index_name}[/bold]")
    if filter_expr:
        console.print(f"Filter: {filter_expr}")
    console.print(f"Document count: [green]{count}[/green]")


if __name__ == "__main__":
    main()
