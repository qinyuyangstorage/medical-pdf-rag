# Medical PDF RAG: Traceable Ingestion and Retrieval

A traceable ingestion and retrieval baseline for turning medical PDFs into citation-ready JSONL chunks. The project preserves page numbers and bounding boxes so every retrieved passage can be traced back to its source page.

## What it demonstrates

- PDF layout extraction with PyMuPDF
- A typed intermediate representation (`DocIR`)
- Section-aware chunking with lightweight clinical tags
- MinerU cloud-output adapter for OCR-heavy documents
- Dependency-free lexical retrieval baseline
- Deterministic content-based document identifiers
- Automated end-to-end tests and GitHub Actions

This is a document-engineering prototype, not a clinical decision-support system. It does not provide medical advice and the repository contains no patient data.

## Quick start

Requires Python 3.10 or newer.

```bash
git clone https://github.com/qinyuyangstorage/medical-pdf-rag.git
cd medical-pdf-rag
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Put one or more PDFs in `samples/`, then run:

```bash
medrag ingest --input_dir samples --out_dir out
medrag stats --chunk_dir out/chunks
medrag search --chunk_dir out/chunks --query "adverse events mortality" --top_k 3
```

Generated artifacts:

```text
out/
├── docir/   # typed document blocks with page coordinates
└── chunks/  # JSONL chunks with section paths, tags, and citations
```

## MinerU route

For scanned or layout-heavy PDFs, place the MinerU token in the ignored file `secrets/mineru_token.env`, following `secrets/README.md`.

```bash
python scripts/mineru_cloud_batch.py \
  --input_dir ./samples \
  --out_dir ./mineru_cloud_out \
  --model vlm --language ch --ocr --formula --table

medrag ingest-mineru-cloud \
  --mineru_out_dir ./mineru_cloud_out \
  --out_dir ./out_mineru
```

Tokens, source PDFs, extracted text, generated chunks, and virtual environments are excluded from version control. The MinerU route sends documents to an external service; use it only when the document owner and applicable data rules permit external processing.

## Privacy behavior

- Generated document IDs are derived only from a SHA-256 content fingerprint; input filenames are not embedded in IDs.
- Source filenames and absolute local paths are omitted from `DocIR` by default.
- Generated `out/` and `mineru_cloud_out/` directories are ignored by Git.
- Treat extracted text and chunks as sensitive whenever the source document is sensitive, even though the repository itself contains only synthetic tests.

## Architecture

```text
PDF / MinerU output
        |
        v
     DocIR blocks  -- page + bounding box provenance
        |
        v
 section-aware chunks -- clinical tags + citation spans
        |
        v
 lexical retrieval baseline -- ranked, page-cited excerpts
```

## Quality checks

```bash
pytest -q
python -m compileall -q src scripts
python scripts/benchmark_demo.py
```

The end-to-end test generates a synthetic PDF, parses it, chunks it, retrieves a clinical passage, and verifies the page citation. No external medical document or restricted dataset is required.

`results/benchmark.json` records local engineering latency for a 10-page synthetic text-layer PDF. It is not a clinical retrieval-quality claim.

## Current limitations

- The built-in search is a transparent lexical baseline, not an embedding model.
- Native PDF reading order remains heuristic for complex multi-column layouts.
- Tables and figures need stronger structure recovery and evaluation.
- The live MinerU service integration requires a separately obtained token and is not exercised by CI; CI covers the output adapter with synthetic JSON.

## Repository map

- `src/medrag/parsers/`: native PDF and MinerU adapters
- `src/medrag/chunking/`: heuristic section-aware chunking
- `src/medrag/retrieval.py`: lexical baseline
- `src/medrag/schema.py`: typed provenance schema
- `tests/`: synthetic end-to-end verification
- `scripts/`: optional MinerU batch integration

## License

MIT. See `LICENSE`.
