from __future__ import annotations

import re
from dataclasses import dataclass

from medrag.schema import Chunk, CitationSpan, DocBlock, DocIR

_SECTION_RX = re.compile(
    r"^\s*(abstract|background|methods?|materials and methods|results?|discussion|conclusions?|references?)\s*$",
    re.IGNORECASE,
)

_OUTCOME_RX = re.compile(
    r"(primary end point|primary endpoint|secondary end point|secondary endpoint|subgroup analysis|sensitivity analysis|safety|adverse events?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ChunkOptions:
    max_chars: int = 1400
    min_chars: int = 300


def _normalize_heading(h: str) -> str:
    h2 = re.sub(r"\s+", " ", h).strip()
    h2 = re.sub(r"^\d+(\.\d+)*\s*", "", h2)  # drop numbering
    return h2


def _heading_level(block: DocBlock) -> int:
    # very rough: larger font => higher level
    fs = float(block.meta.get("font_size_max") or 0.0)
    if fs >= 18:
        return 1
    if fs >= 15:
        return 2
    if fs >= 13:
        return 3
    return 4


def _derive_tags(text: str) -> list[str]:
    tags: list[str] = []
    if _OUTCOME_RX.search(text):
        m = _OUTCOME_RX.search(text)
        if m:
            tags.append(m.group(1).lower())
    # quick PICO-ish cues
    if re.search(r"\brandomi[sz]ed\b|\btrial\b", text, re.IGNORECASE):
        tags.append("study_design:trial")
    if re.search(r"\bhazard ratio\b|\bHR\b|\bOR\b|\bRR\b|95%\s*CI|confidence interval|p\s*=\s*", text, re.IGNORECASE):
        tags.append("stats:effect")
    if re.search(r"\badverse\b|\bsafety\b|\bbleeding\b|\bmortality\b", text, re.IGNORECASE):
        tags.append("outcome:clinical")
    return sorted(set(tags))


def chunk_docir(doc: DocIR, *, options: ChunkOptions | None = None) -> list[Chunk]:
    options = options or ChunkOptions()

    # Build a simple section stack based on heading blocks.
    stack: list[tuple[int, str]] = []  # (level, heading)

    chunks: list[Chunk] = []
    buf_blocks: list[DocBlock] = []
    buf_text_parts: list[str] = []
    buf_citations: list[CitationSpan] = []
    chunk_idx = 0

    def flush():
        nonlocal chunk_idx, buf_blocks, buf_text_parts, buf_citations
        text = "\n\n".join([t for t in buf_text_parts if t.strip()]).strip()
        if not text:
            buf_blocks, buf_text_parts, buf_citations = [], [], []
            return
        if len(text) < options.min_chars and chunks:
            # attach to previous if too small
            prev = chunks[-1]
            prev.text = (prev.text + "\n\n" + text).strip()
            prev.citations.extend(buf_citations)
        else:
            section_path = [h for _, h in stack]
            tags = _derive_tags(text)
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}__c{chunk_idx}",
                    doc_id=doc.doc_id,
                    chunk_type="text",
                    section_path=section_path,
                    clinical_tags=tags,
                    text=text,
                    citations=list(buf_citations),
                    meta={"n_blocks": len(buf_blocks)},
                )
            )
            chunk_idx += 1
        buf_blocks, buf_text_parts, buf_citations = [], [], []

    for b in sorted(doc.blocks, key=lambda x: x.order):
        if b.type == "heading":
            flush()
            h = _normalize_heading(b.text)
            lvl = _heading_level(b)

            # try to map common IMRaD headings even if noisy
            if _SECTION_RX.match(h):
                h = h.title()

            while stack and stack[-1][0] >= lvl:
                stack.pop()
            stack.append((lvl, h))
            continue

        # main text
        buf_blocks.append(b)
        buf_text_parts.append(b.text)
        buf_citations.append(CitationSpan(page=b.page, bbox=b.bbox, text_snippet=b.text[:200]))

        if sum(len(x) for x in buf_text_parts) >= options.max_chars:
            flush()

    flush()
    return chunks
