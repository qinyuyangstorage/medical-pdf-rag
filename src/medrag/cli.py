from __future__ import annotations

import argparse
from pathlib import Path

from tqdm import tqdm

from medrag.chunking import ChunkOptions, chunk_docir
from medrag.io import dump_json, ensure_dir, write_jsonl
from medrag.parsers import ParseOptions, parse_mineru_cloud_dir, parse_pdf_to_docir
from medrag.retrieval import load_chunks, search_chunks


def _iter_pdfs(input_dir: Path) -> list[Path]:
    pdfs = sorted([p for p in input_dir.rglob("*.pdf") if p.is_file()])
    return pdfs


def cmd_ingest(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)
    docir_dir = ensure_dir(out_dir / "docir")
    chunk_dir = ensure_dir(out_dir / "chunks")

    pdfs = _iter_pdfs(input_dir)
    if not pdfs:
        print(f"未找到 PDF：{input_dir}")
        return 2

    p_opts = ParseOptions()
    c_opts = ChunkOptions(max_chars=args.max_chars, min_chars=args.min_chars)

    for pdf in tqdm(pdfs, desc="ingest"):
        doc = parse_pdf_to_docir(pdf, options=p_opts)
        dump_json(docir_dir / f"{doc.doc_id}.json", doc.model_dump())

        chunks = chunk_docir(doc, options=c_opts)
        write_jsonl(chunk_dir / f"{doc.doc_id}.jsonl", (c.model_dump() for c in chunks))

    print(f"完成：{len(pdfs)} 篇 PDF")
    print(f"DocIR：{docir_dir}")
    print(f"Chunks：{chunk_dir}")
    return 0


def cmd_ingest_mineru_cloud(args: argparse.Namespace) -> int:
    """
    Convert MinerU cloud outputs (per-PDF folders) -> DocIR -> Chunks.

    Expected structure:
      mineru_out_dir/
        <pdf-name>.pdf/
          content_list_v2.json
          ...
    """
    mineru_out_dir = Path(args.mineru_out_dir)
    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)
    docir_dir = ensure_dir(out_dir / "docir")
    chunk_dir = ensure_dir(out_dir / "chunks")

    doc_dirs = sorted([p for p in mineru_out_dir.iterdir() if p.is_dir()])
    doc_dirs = [p for p in doc_dirs if (p / "content_list_v2.json").exists()]
    if not doc_dirs:
        print(f"未找到 MinerU 云端输出目录（需包含 content_list_v2.json）：{mineru_out_dir}")
        return 2

    c_opts = ChunkOptions(max_chars=args.max_chars, min_chars=args.min_chars)

    for d in tqdm(doc_dirs, desc="ingest-mineru-cloud"):
        doc = parse_mineru_cloud_dir(d)
        dump_json(docir_dir / f"{doc.doc_id}.json", doc.model_dump())

        chunks = chunk_docir(doc, options=c_opts)
        write_jsonl(chunk_dir / f"{doc.doc_id}.jsonl", (c.model_dump() for c in chunks))

    print(f"完成：{len(doc_dirs)} 篇文献（MinerU 云端输出）")
    print(f"DocIR：{docir_dir}")
    print(f"Chunks：{chunk_dir}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    chunks = load_chunks(args.chunk_dir)
    hits = search_chunks(chunks, args.query, top_k=args.top_k)
    if not hits:
        print("No matching chunks found.")
        return 1

    for rank, hit in enumerate(hits, start=1):
        pages = sorted({citation.page for citation in hit.chunk.citations})
        section = " > ".join(hit.chunk.section_path) or "(unsectioned)"
        excerpt = " ".join(hit.chunk.text.split())[: args.excerpt_chars]
        print(f"[{rank}] score={hit.score:.6f} pages={pages} section={section}")
        print(excerpt)
        print()
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    chunks = load_chunks(args.chunk_dir)
    documents = {chunk.doc_id for chunk in chunks}
    pages = {(chunk.doc_id, citation.page) for chunk in chunks for citation in chunk.citations}
    total_chars = sum(len(chunk.text) for chunk in chunks)
    print(f"documents={len(documents)}")
    print(f"chunks={len(chunks)}")
    print(f"cited_pages={len(pages)}")
    print(f"characters={total_chars}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="medrag", description="医疗 PDF → DocIR → 语义切片（原型）")
    sub = p.add_subparsers(dest="cmd", required=True)

    ing = sub.add_parser("ingest", help="批量解析 PDF 并生成 DocIR/Chunks")
    ing.add_argument("--input_dir", required=True, help="包含 PDF 的目录")
    ing.add_argument("--out_dir", required=True, help="输出目录")
    ing.add_argument("--max_chars", type=int, default=1400, help="chunk 最大字符数")
    ing.add_argument("--min_chars", type=int, default=300, help="chunk 最小字符数（过小会合并到上一块）")
    ing.set_defaults(func=cmd_ingest)

    ing2 = sub.add_parser("ingest-mineru-cloud", help="从 MinerU 云端输出目录生成 DocIR/Chunks")
    ing2.add_argument("--mineru_out_dir", required=True, help="MinerU 云端输出根目录（每篇文献一个子目录）")
    ing2.add_argument("--out_dir", required=True, help="输出目录")
    ing2.add_argument("--max_chars", type=int, default=1400, help="chunk 最大字符数")
    ing2.add_argument("--min_chars", type=int, default=300, help="chunk 最小字符数（过小会合并到上一块）")
    ing2.set_defaults(func=cmd_ingest_mineru_cloud)

    search = sub.add_parser("search", help="Search generated chunks with a dependency-free lexical baseline")
    search.add_argument("--chunk_dir", required=True, help="Directory containing chunk JSONL files")
    search.add_argument("--query", required=True, help="Search query")
    search.add_argument("--top_k", type=int, default=5, help="Number of results")
    search.add_argument("--excerpt_chars", type=int, default=320, help="Maximum excerpt length")
    search.set_defaults(func=cmd_search)

    stats = sub.add_parser("stats", help="Summarise a generated chunk collection")
    stats.add_argument("--chunk_dir", required=True, help="Directory containing chunk JSONL files")
    stats.set_defaults(func=cmd_stats)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
