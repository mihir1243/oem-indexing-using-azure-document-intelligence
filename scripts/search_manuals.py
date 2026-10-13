from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rich.console import Console
from rich.table import Table

from src.pipeline import search
from src.timing import configure_logging

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search indexed OEM manual chunks.")
    parser.add_argument("--query", required=True, type=str, help="Search query")
    parser.add_argument("--manufacturer", type=str, help="Filter by manufacturer")
    parser.add_argument("--model", type=str, help="Filter by model series")
    parser.add_argument("--type", dest="manual_type", type=str, help="Filter by manual type")
    parser.add_argument("--top-k", type=int, default=50, help="Number of results")
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()
    filters = {}
    if args.manufacturer:
        filters["manufacturer"] = args.manufacturer
    if args.model:
        filters["model"] = args.model
    if args.manual_type:
        filters["manual_type"] = args.manual_type

    results = search(query=args.query, filters=filters or None, top_k=args.top_k)

    table = Table(title="Search Results (Top 10)")
    table.add_column("Score", justify="right")
    table.add_column("Section")
    table.add_column("Page", justify="right")
    table.add_column("Preview")

    for item in results[:10]:
        preview = item.raw_text.replace("\n", " ")[:160]
        table.add_row(
            f"{item.score:.3f}",
            item.section_path or item.section_title,
            str(item.page_number),
            preview,
        )

    if not results and filters:
        console.print(
            "[yellow]No results.[/yellow] Check filter values match the index exactly "
            "(manufacturer, manual type, model); try a broader query or remove filters."
        )
    console.print(table)


if __name__ == "__main__":
    main()
