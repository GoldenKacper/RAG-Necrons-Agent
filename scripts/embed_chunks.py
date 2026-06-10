from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionLocal, engine
from app.models import Base, Chunk
from app.services.embeddings import embed_texts, iter_batches


def load_chunks(path: Path) -> list[dict]:
    items: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def chunk_to_row(chunk: dict, embedding: list[float]) -> dict:
    return {
        "source_file": chunk.get("source_file", "necrons.txt"),
        "source_chunk_id": chunk["chunk_id"],
        "parent_block_id": chunk["parent_block_id"],
        "parent_heading": chunk["parent_heading"],
        "heading": chunk["heading"],
        "kind": chunk["kind"],
        "text": chunk["text"],
        "start_line": chunk["start_line"],
        "end_line": chunk["end_line"],
        "token_estimate": chunk["token_estimate"],
        "source_subblock_ids": {"ids": chunk.get("source_subblock_ids", [])},
        "extra_metadata": {
            "chunk_id": chunk["chunk_id"],
            "parent_block_id": chunk["parent_block_id"],
            "parent_heading": chunk["parent_heading"],
            "heading": chunk["heading"],
            "kind": chunk["kind"],
            "start_line": chunk["start_line"],
            "end_line": chunk["end_line"],
            "token_estimate": chunk["token_estimate"],
        },
        "embedding": embedding,
    }


def reset_table(session) -> None:
    session.execute(delete(Chunk))
    session.commit()


def upsert_rows(session, rows: list[dict]) -> None:
    stmt = insert(Chunk).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["source_file", "source_chunk_id"],
        set_={
            "parent_block_id": stmt.excluded.parent_block_id,
            "parent_heading": stmt.excluded.parent_heading,
            "heading": stmt.excluded.heading,
            "kind": stmt.excluded.kind,
            "text": stmt.excluded.text,
            "start_line": stmt.excluded.start_line,
            "end_line": stmt.excluded.end_line,
            "token_estimate": stmt.excluded.token_estimate,
            "source_subblock_ids": stmt.excluded.source_subblock_ids,
            "extra_metadata": stmt.excluded.extra_metadata,
            "embedding": stmt.excluded.embedding,
        },
    )
    session.execute(stmt)
    session.commit()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Embed chunks and save them to PostgreSQL + pgvector.")
    parser.add_argument(
        "--input",
        type=Path,
        default=settings.chunks_input_path,
        help="Path to chunks JSONL.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="How many chunks to embed at once.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing rows before ingesting.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)

    chunks = load_chunks(args.input)
    if not chunks:
        print("No chunks found.")
        return

    session = SessionLocal()
    try:
        if args.reset:
            reset_table(session)
            print("Reset")

        for batch in iter_batches(chunks, args.batch_size):
            texts = [item["text"] for item in batch]
            embeddings = embed_texts(texts)
            rows = [chunk_to_row(item, emb) for item, emb in zip(batch, embeddings, strict=True)]
            upsert_rows(session, rows)
            print(f"Saved batch: {len(rows)} chunks")

        print(f"Done. Total chunks processed: {len(chunks)}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
