from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

import orjson


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def dump_json(path: str | Path, obj) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(orjson.dumps(obj, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS))


def write_jsonl(path: str | Path, rows: Iterable[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("wb") as f:
        for r in rows:
            f.write(orjson.dumps(r))
            f.write(b"\n")


def stable_doc_id(source_path: str) -> str:
    path = Path(source_path)
    if not path.is_file():
        raise ValueError(f"Document fingerprint source must be a file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return f"doc_{digest.hexdigest()[:16]}"
