from pathlib import Path

import pymupdf as fitz

from medrag.chunking import ChunkOptions, chunk_docir
from medrag.io import stable_doc_id
from medrag.parsers import parse_pdf_to_docir
from medrag.retrieval import search_chunks


def _make_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Clinical Trial Results", fontsize=18)
    page.insert_textbox(
        fitz.Rect(72, 110, 520, 300),
        "A randomized trial reported lower mortality and no increase in serious adverse events. " * 8,
        fontsize=11,
    )
    doc.save(path)


def test_pdf_to_traceable_search_hit(tmp_path: Path) -> None:
    pdf = tmp_path / "trial.pdf"
    _make_pdf(pdf)

    docir = parse_pdf_to_docir(pdf)
    chunks = chunk_docir(docir, options=ChunkOptions(max_chars=500, min_chars=20))
    hits = search_chunks(chunks, "mortality adverse events", top_k=1)

    assert docir.title == "Clinical Trial Results"
    assert chunks
    assert hits
    assert hits[0].chunk.citations[0].page == 1
    assert "outcome:clinical" in hits[0].chunk.clinical_tags


def test_document_id_depends_on_content_not_timestamp(tmp_path: Path) -> None:
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    _make_pdf(first)
    second.write_bytes(first.read_bytes())

    assert stable_doc_id(str(first)).split("__", 1)[1] == stable_doc_id(str(second)).split("__", 1)[1]
