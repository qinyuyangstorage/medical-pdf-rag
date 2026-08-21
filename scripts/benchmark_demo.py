from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pymupdf as fitz

from medrag.chunking import ChunkOptions, chunk_docir
from medrag.parsers import parse_pdf_to_docir
from medrag.retrieval import search_chunks


def build_document(path: Path, pages: int = 10) -> None:
    document = fitz.open()
    for page_number in range(1, pages + 1):
        page = document.new_page()
        page.insert_text((72, 72), f"Clinical Evidence Section {page_number}", fontsize=16)
        page.insert_textbox(
            fitz.Rect(72, 110, 520, 700),
            ("This synthetic trial passage discusses mortality, safety, and adverse events. " * 35),
            fontsize=10,
        )
    document.save(path)


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        pdf = Path(directory) / "synthetic-medical-document.pdf"
        build_document(pdf)
        started = time.perf_counter()
        docir = parse_pdf_to_docir(pdf)
        chunks = chunk_docir(docir, options=ChunkOptions(max_chars=900, min_chars=100))
        ingest_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        hits = search_chunks(chunks, "mortality adverse events", top_k=5)
        search_ms = (time.perf_counter() - started) * 1000
    result = {
        "document": "10-page synthetic text-layer medical-style PDF",
        "pages": 10,
        "blocks": len(docir.blocks),
        "chunks": len(chunks),
        "top_k_hits": len(hits),
        "ingest_and_chunk_ms": ingest_ms,
        "search_ms": search_ms,
        "all_hits_have_page_citations": all(hit.chunk.citations for hit in hits),
        "note": "Local engineering benchmark; not a clinical retrieval-quality result.",
    }
    output = Path("results/benchmark.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
