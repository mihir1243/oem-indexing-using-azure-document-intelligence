from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rich.console import Console

from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption

from src.config import get_settings
from src.extraction.extractor import build_pdf_pipeline_options
from src.embedding.embedder import Embedder
from src.indexing.indexer import SearchIndexer

console = Console()


def main() -> int:
    settings = get_settings()
    console.print(f"Search endpoint: {settings.azure_search_endpoint}")
    console.print(f"Search index: {settings.azure_search_index_name}")
    console.print(
        f"Docling: OCR={settings.docling_do_ocr}, table_mode={settings.docling_table_mode}, "
        f"heading_hierarchy={settings.docling_heading_hierarchy}"
    )

    try:
        pipeline_options = build_pdf_pipeline_options(settings)
        DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )
        console.print("[green]Docling[/green]: converter initialized")
    except Exception as exc:
        console.print(f"[red]Docling[/red]: FAILED — {exc}")
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
