from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

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
    # Use basename + size + mtime as a simple stable id without hashing huge files.
    st = os.stat(source_path)
    base = Path(source_path).name
    return f"{base}__{st.st_size}__{int(st.st_mtime)}"
