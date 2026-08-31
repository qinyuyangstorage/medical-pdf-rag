from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


BlockType = Literal["title", "heading", "paragraph", "list_item", "table", "figure", "caption", "footer", "header"]


class CitationSpan(BaseModel):
    page: int = Field(ge=1, description="1-based page number")
    bbox: BBox | None = None
    text_snippet: str | None = None


class DocBlock(BaseModel):
    id: str
    type: BlockType
    text: str = ""
    page: int = Field(ge=1)
    bbox: BBox | None = None
    order: int = Field(ge=0, description="reading order index within document")
    meta: dict = Field(default_factory=dict)


class DocIR(BaseModel):
    doc_id: str
    source_path: str
    title: str | None = None
    blocks: list[DocBlock]
    meta: dict = Field(default_factory=dict)


ChunkType = Literal["text", "table", "figure"]


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    chunk_type: ChunkType
    section_path: list[str] = Field(default_factory=list)
    clinical_tags: list[str] = Field(default_factory=list)
    text: str
    citations: list[CitationSpan] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)
