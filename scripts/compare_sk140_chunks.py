"""Compare chunk counts for SK140: PyMuPDF vs Azure (writes progress to stdout)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pymupdf as fitz
import tiktoken

from src.chunking.hierarchical import HierarchicalChunker
from src.config import get_settings
from src.extraction.extractor import DocumentExtractor
from src.extraction.markdown_store import load_cached_extraction
from src.extraction.pymupdf_extractor import extract_with_pymupdf
from src.models import ManualMetadata


def heading_counts(md: str) -> dict[int, int]:
    counts = {i: 0 for i in range(1, 7)}
    for line in md.splitlines():
        if not line.startswith("#"):
            continue
        level = len(line) - len(line.lstrip("#"))
        if 1 <= level <= 6:
            counts[level] += 1
    return counts


def report(doc, label: str, chunker: HierarchicalChunker, enc) -> int:
    chunks = chunker.chunk(doc)
    md = doc.markdown_content
    hc = heading_counts(md)
    toks = [len(enc.encode(c.raw_text)) for c in chunks]
    split_at_h4 = sum(1 for c in chunks if c.section_path.count(" > ") >= 3)
    print(f"\n=== {label} ===", flush=True)
    print(f"  markdown chars: {len(md):,}", flush=True)
    print(f"  headings h1–h6: {hc}  (h1–h4 total: {sum(hc[i] for i in range(1, 5))})", flush=True)
    print(f"  chunks: {len(chunks)}", flush=True)
    print(
        f"  raw_text tokens — min/med/max: {min(toks)} / {sorted(toks)[len(toks) // 2]} / {max(toks)}",
        flush=True,
    )
    print(f"  chunks with >512 tokens: {sum(1 for t in toks if t > 512)}", flush=True)
    print(f"  chunks with section_path depth ≥3: {split_at_h4}", flush=True)
    return len(chunks)


def main() -> None:
    pdf = ROOT / "manuals" / "SK140-7 Ops Manual.pdf"
    meta = ManualMetadata(manufacturer="Kobelco", model_series=["SK140"], manual_type="ops")
    settings = get_settings()
    chunker = HierarchicalChunker(settings)
    enc = tiktoken.get_encoding("cl100k_base")

    cached = load_cached_extraction(pdf.name, Path(settings.markdown_output_dir), meta)
    if cached:
        report(cached, f"cached ({settings.markdown_output_dir})", chunker, enc)

    print("\nExtracting PyMuPDF (normalize=True)...", flush=True)
    with fitz.open(pdf) as doc:
        pym = extract_with_pymupdf(doc, pdf.name, meta, settings)
    report(pym, "PyMuPDF + heading normalizer", chunker, enc)

    if "--azure" in sys.argv:
        print("\nExtracting Azure DI...", flush=True)
        az_settings = settings.model_copy(update={"extraction_backend": "azure"})
        extracted, _ = DocumentExtractor(az_settings).extract(pdf, meta)
        report(extracted, "Azure Document Intelligence", chunker, enc)


if __name__ == "__main__":
    main()
