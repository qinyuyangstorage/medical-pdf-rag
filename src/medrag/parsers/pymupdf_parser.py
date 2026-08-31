from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf as fitz

from medrag.io import stable_doc_id
from medrag.schema import BBox, DocBlock, DocIR


@dataclass(frozen=True)
class ParseOptions:
    # heuristics
    header_footer_margin: float = 0.06  # fraction of page height
    min_block_chars: int = 20
    max_title_chars: int = 200
    include_source_name: bool = False


def _bbox_from_rect(r: fitz.Rect) -> BBox:
    return BBox(x0=float(r.x0), y0=float(r.y0), x1=float(r.x1), y1=float(r.y1))


def parse_pdf_to_docir(pdf_path: str | Path, *, options: ParseOptions | None = None) -> DocIR:
    options = options or ParseOptions()
    pdf_path = str(pdf_path)
    doc_id = stable_doc_id(pdf_path)

    blocks: list[DocBlock] = []
    order = 0
    candidate_titles: list[tuple[float, str]] = []  # (font_size, text)

    with fitz.open(pdf_path) as doc:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_no = page_idx + 1
            page_rect = page.rect
            page_h = float(page_rect.height) if page_rect else 1.0
            top_y = float(page_rect.y0) + options.header_footer_margin * page_h
            bot_y = float(page_rect.y1) - options.header_footer_margin * page_h

            # dict keeps line/spans with size; blocks gives reading-ish order.
            d = page.get_text("dict")
            for b_i, b in enumerate(d.get("blocks", [])):
                if b.get("type") != 0:  # 0 = text
                    continue
                bbox = fitz.Rect(b.get("bbox"))
                if bbox.y1 < top_y or bbox.y0 > bot_y:
                    # likely header/footer noise
                    continue

                # reconstruct text and estimate dominant font size
                texts: list[str] = []
                sizes: list[float] = []
                for line in b.get("lines", []):
                    line_texts: list[str] = []
                    for span in line.get("spans", []):
                        t = (span.get("text") or "").strip("\n")
                        if t:
                            line_texts.append(t)
                            if isinstance(span.get("size"), (int, float)):
                                sizes.append(float(span["size"]))
                    if line_texts:
                        texts.append(" ".join(line_texts))
                text = "\n".join(texts).strip()
                if len(text) < options.min_block_chars:
                    continue

                dom_size = max(sizes) if sizes else 0.0
                block_type = "paragraph"

                # heuristic heading/title detection: large font and short text
                if dom_size >= 13 and len(text) <= 120 and "\n" not in text:
                    block_type = "heading"
                if dom_size >= 16 and len(text) <= options.max_title_chars and page_no == 1:
                    candidate_titles.append((dom_size, text))

                blocks.append(
                    DocBlock(
                        id=f"p{page_no}_b{b_i}",
                        type=block_type,
                        text=text,
                        page=page_no,
                        bbox=_bbox_from_rect(bbox),
                        order=order,
                        meta={"font_size_max": dom_size},
                    )
                )
                order += 1

    title = None
    if candidate_titles:
        candidate_titles.sort(key=lambda x: (-x[0], len(x[1])))
        title = candidate_titles[0][1]

    source_path = Path(pdf_path).name if options.include_source_name else ""
    return DocIR(doc_id=doc_id, source_path=source_path, title=title, blocks=blocks, meta={"parser": "pymupdf"})
