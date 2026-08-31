from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import orjson

from medrag.io import stable_doc_id
from medrag.schema import BBox, DocBlock, DocIR

_SKIP_TYPES = {
    "page_header",
    "page_footer",
    "page_footnote",
    "page_number",
}


def _read_json(path: Path) -> Any:
    return orjson.loads(path.read_bytes())


def _bbox(b: list[float] | tuple[float, float, float, float] | None) -> BBox | None:
    if not b or len(b) != 4:
        return None
    x0, y0, x1, y1 = b
    return BBox(x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1))


def _iter_rich_text(nodes: Iterable[dict]) -> str:
    """
    MinerU content arrays contain items like:
    - {"type": "text", "content": "..."}
    - {"type": "equation_inline", "content": "..."}  (LaTeX)
    We linearize them into a single string.
    """
    parts: list[str] = []
    for n in nodes:
        t = (n.get("type") or "").strip()
        c = n.get("content")
        if not c:
            continue
        if t == "text":
            parts.append(str(c))
        elif "equation" in t:
            # keep equations searchable; wrap to avoid merging with words
            parts.append(f" $ {c} $ ")
        else:
            parts.append(str(c))
    return "".join(parts).strip()


def _extract_text(item: dict) -> str:
    t = item.get("type")
    content = item.get("content") or {}

    if t == "title":
        return _iter_rich_text(content.get("title_content") or [])
    if t == "paragraph":
        return _iter_rich_text(content.get("paragraph_content") or [])
    if t == "list":
        # reference_list or bullet list
        items = content.get("list_items") or []
        lines: list[str] = []
        for it in items:
            line = _iter_rich_text(it.get("item_content") or [])
            if line:
                lines.append(line)
        return "\n".join(lines).strip()
    if t == "table":
        cap = _iter_rich_text(content.get("table_caption") or [])
        foot = _iter_rich_text(content.get("table_footnote") or [])
        html = (content.get("html") or "").strip()
        # keep human-readable and also preserve raw html
        chunks = []
        if cap:
            chunks.append(cap)
        if html:
            chunks.append(html)
        if foot:
            chunks.append(foot)
        return "\n\n".join(chunks).strip()
    if t == "image":
        cap = _iter_rich_text(content.get("image_caption") or [])
        foot = _iter_rich_text(content.get("image_footnote") or [])
        chunks = []
        if cap:
            chunks.append(cap)
        if foot:
            chunks.append(foot)
        return "\n\n".join(chunks).strip()

    return ""


def parse_mineru_cloud_dir(
    doc_dir: str | Path, *, source_pdf_path: str | None = None, include_source_name: bool = False
) -> DocIR:
    """
    Parse a single MinerU cloud output folder (per-PDF).

    Expected files:
    - content_list_v2.json (preferred)
    - layout.json (optional)
    - images/ (optional)
    - full.md (optional)
    """
    doc_dir = Path(doc_dir)
    content_path = doc_dir / "content_list_v2.json"
    if not content_path.exists():
        raise FileNotFoundError(f"缺少 {content_path}")

    pages = _read_json(content_path)
    if not isinstance(pages, list):
        raise TypeError("content_list_v2.json 格式异常：顶层不是 list")

    # Prefer the original PDF as the content fingerprint. If MinerU output does
    # not retain it, fingerprint the canonical content list instead.
    origin_pdf = next(doc_dir.glob("*_origin.pdf"), None)
    fingerprint_path = Path(source_pdf_path) if source_pdf_path else origin_pdf or content_path
    if not fingerprint_path.is_file():
        raise FileNotFoundError(f"Document fingerprint source is not a file: {fingerprint_path}")
    doc_id = stable_doc_id(str(fingerprint_path))
    source_name = fingerprint_path.name if include_source_name else ""

    blocks: list[DocBlock] = []
    order = 0
    title: str | None = None

    for page_idx, items in enumerate(pages):
        page_no = page_idx + 1
        if not isinstance(items, list):
            continue
        for i, item in enumerate(items):
            itype = item.get("type")
            if itype in _SKIP_TYPES:
                continue

            text = _extract_text(item).strip()
            if not text:
                continue

            btype = "paragraph"
            meta: dict[str, Any] = {"mineru_type": itype}

            if itype == "title":
                # map title blocks to heading/title
                lvl = (item.get("content") or {}).get("level")
                if isinstance(lvl, int):
                    meta["level"] = lvl
                btype = "heading"
                # pick a plausible document title from first page long title
                if page_no == 1 and (title is None) and len(text) >= 20:
                    title = text
            elif itype == "table":
                btype = "table"
                meta["html"] = (item.get("content") or {}).get("html")
                meta["image_path"] = ((item.get("content") or {}).get("image_source") or {}).get("path")
            elif itype == "image":
                btype = "figure"
                meta["image_path"] = ((item.get("content") or {}).get("image_source") or {}).get("path")
            elif itype == "list":
                btype = "paragraph"
                meta["list_type"] = (item.get("content") or {}).get("list_type")

            blocks.append(
                DocBlock(
                    id=f"p{page_no}_i{i}",
                    type=btype,  # type: ignore[arg-type]
                    text=text,
                    page=page_no,
                    bbox=_bbox(item.get("bbox")),
                    order=order,
                    meta=meta,
                )
            )
            order += 1

    return DocIR(
        doc_id=doc_id,
        source_path=source_name,
        title=title,
        blocks=blocks,
        meta={"parser": "mineru_cloud"},
    )
