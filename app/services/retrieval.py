from __future__ import annotations

from sqlalchemy import select

from app.db import session_scope
from app.models import Chunk as ChunkModel
from app.services.embeddings import get_embedding
from app.schemas import SearchResult


def search_similar_chunks(
        question: str,
        top_k: int = 5,
        exclude_parents: set[str] | None = None,
) -> list[SearchResult]:
    """
    Returns top_k most similar chunks to the question.
    Uses cosine distance: the smaller the distance, the better.

    exclude_parents:
        Optional set of parent_heading values to exclude at SQL level.
        Example: {"Contents"} removes table-of-contents chunks from retrieval
        without deleting them from the database.
    """
    query_embedding = get_embedding(question)

    with session_scope() as session:
        distance = ChunkModel.embedding.cosine_distance(query_embedding).label("distance")

        stmt = select(ChunkModel, distance)

        if exclude_parents:
            stmt = stmt.where(ChunkModel.parent_heading.notin_(exclude_parents))

        stmt = (
            stmt
            .order_by(distance)
            .limit(top_k)
        )

        rows = session.execute(stmt).all()

        results: list[SearchResult] = []
        for chunk, dist in rows:
            score = float(1.0 - dist)
            results.append(
                SearchResult(
                    id=chunk.id,
                    source_file=getattr(chunk, "source_file", ""),
                    source_chunk_id=getattr(chunk, "source_chunk_id", 0),
                    parent_block_id=getattr(chunk, "parent_block_id", 0),
                    parent_heading=getattr(chunk, "parent_heading", ""),
                    heading=getattr(chunk, "heading", ""),
                    kind=getattr(chunk, "kind", ""),
                    text=getattr(chunk, "text", ""),
                    start_line=getattr(chunk, "start_line", 0),
                    end_line=getattr(chunk, "end_line", 0),
                    token_estimate=getattr(chunk, "token_estimate", 0),
                    score=float(score),
                )
            )

    return results


def format_context(chunks: list[SearchResult]) -> str:
    parts: list[str] = []

    for idx, chunk in enumerate(chunks, start=1):
        source_file = chunk.source_file or "-"
        parent_heading = chunk.parent_heading or "-"
        heading = chunk.heading or "-"
        text = chunk.text or ""
        start_line = chunk.start_line or 0
        end_line = chunk.end_line or 0

        parts.append(
            f"[SOURCE {idx}] {source_file} | {parent_heading} / {heading} | lines {start_line}-{end_line}\n"
            f"{text}"
        )

    return "\n\n".join(parts)
