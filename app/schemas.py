from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List


class HealthResponse(BaseModel):
    status: str = "ok"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    id: int
    source_file: str
    source_chunk_id: int
    parent_block_id: int
    parent_heading: str
    heading: str
    kind: str
    text: str
    start_line: int
    end_line: int
    token_estimate: int
    score: float


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]


class AskRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class AskResponse(BaseModel):
    query: str
    answer: str
    results: list[SearchResult]
