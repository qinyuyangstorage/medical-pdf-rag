from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import orjson

from medrag.schema import Chunk


_TOKEN_RX = re.compile(r"[A-Za-z][A-Za-z0-9_-]+|[\u4e00-\u9fff]")


@dataclass(frozen=True)
class SearchHit:
    score: float
    chunk: Chunk


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RX.findall(text)]


def load_chunks(chunk_dir: str | Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(Path(chunk_dir).rglob("*.jsonl")):
        for line in path.read_bytes().splitlines():
            if line.strip():
                chunks.append(Chunk.model_validate(orjson.loads(line)))
    return chunks


def search_chunks(chunks: list[Chunk], query: str, *, top_k: int = 5) -> list[SearchHit]:
    query_terms = tokenize(query)
    if not query_terms or not chunks:
        return []

    documents = [Counter(tokenize(chunk.text)) for chunk in chunks]
    document_frequency = Counter()
    for counts in documents:
        document_frequency.update(counts.keys())

    hits: list[SearchHit] = []
    n_docs = len(chunks)
    for chunk, counts in zip(chunks, documents):
        length = max(sum(counts.values()), 1)
        score = 0.0
        for term in query_terms:
            tf = counts[term] / length
            idf = math.log((n_docs + 1) / (document_frequency[term] + 1)) + 1
            score += tf * idf
        if score > 0:
            hits.append(SearchHit(score=score, chunk=chunk))

    return sorted(hits, key=lambda hit: (-hit.score, hit.chunk.chunk_id))[:top_k]
