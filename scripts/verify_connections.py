from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rich.console import Console

from src.config import get_settings
from src.embedding.embedder import Embedder
from src.indexing.indexer import SearchIndexer

console = Console()


def main() -> int:
    settings = get_settings()
    console.print(f"Search endpoint: {settings.azure_search_endpoint}")
    console.print(f"Search index: {settings.azure_search_index_name}")

    try:
        import torch
        from marker.converters.pdf import PdfConverter

        device = settings.marker_torch_device.strip() or "auto"
        console.print(f"Marker torch device setting: {device}")
        console.print(
            f"[green]Marker[/green]: import OK (torch {torch.__version__}, "
            f"cuda available={torch.cuda.is_available()})"
        )
        del PdfConverter
    except Exception as exc:
        console.print(f"[red]Marker[/red]: FAILED — {exc}")
        return 1

    try:
        SearchIndexer().validate_connection()
        console.print("[green]Azure AI Search[/green]: OK (admin/query key accepted)")
    except Exception as exc:
        console.print(f"[red]Azure AI Search[/red]: FAILED — {exc}")
        console.print(
            "Use the [bold]primary admin key[/bold] from Azure Portal → your Search service → "
            "Keys. Ensure AZURE_SEARCH_ENDPOINT matches that same service."
        )
        return 1

    try:
        Embedder().embed_query("connectivity test")
        console.print("[green]OpenAI embeddings[/green]: OK")
    except Exception as exc:
        console.print(f"[red]OpenAI embeddings[/red]: FAILED — {exc}")
        return 1

    console.print("[green]All checks passed.[/green]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
