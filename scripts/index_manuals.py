from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.pipeline import index_folder, index_manual
from src.timing import configure_logging

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index OEM manual PDFs into Azure AI Search.")
    parser.add_argument("--folder", type=Path, required=True, help="Folder containing PDF files")
    parser.add_argument("--manifest", type=Path, help="Manifest JSON mapping PDFs to metadata")
    parser.add_argument("--file", type=str, help="Single PDF file name inside --folder")
    parser.add_argument("--manufacturer", type=str, help="Manufacturer for single-file indexing")
    parser.add_argument(
        "--model-series",
        nargs="+",
        dest="model_series",
        help="Model series list for single-file indexing",
    )
    parser.add_argument("--manual-type", type=str, help="Manual type for single-file indexing")
    parser.add_argument(
        "--force-extract",
        action="store_true",
        help="Re-run LiteParse extraction even if cached markdown exists",
    )
    return parser.parse_args()


async def _run() -> int:
    configure_logging()
    args = parse_args()
    folder = args.folder.resolve()

    if args.manifest:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Indexing manuals from manifest...", total=None)
            batch = await index_folder(
                folder,
                args.manifest.resolve(),
                force_reextract=args.force_extract,
            )

        for result in batch.results:
            line = (
                f"[green]Indexed[/green] {result.source_file}: "
                f"{result.chunks_indexed} chunks"
            )
            if result.extraction_from_cache:
                line += " | extraction: cached markdown"
            elif result.markdown_path:
                line += f" | markdown: {result.markdown_path}"
            console.print(line)
        for error in batch.errors:
            console.print(f"[red]Error[/red] {error}")
        return 1 if batch.errors else 0

    if not args.file or not args.manufacturer or not args.model_series or not args.manual_type:
        console.print(
            "[red]Provide --manifest or all single-file args: "
            "--file --manufacturer --model-series --manual-type[/red]"
        )
        return 2

    pdf_path = folder / args.file
    result = await index_manual(
        pdf_path=pdf_path,
        manufacturer=args.manufacturer,
        model_series=args.model_series,
        manual_type=args.manual_type,
        force_reextract=args.force_extract,
    )
    line = f"[green]Indexed[/green] {result.source_file}: {result.chunks_indexed} chunks"
    if result.extraction_from_cache:
        line += " | extraction: cached markdown"
    elif result.markdown_path:
        line += f" | markdown: {result.markdown_path}"
    console.print(line)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
