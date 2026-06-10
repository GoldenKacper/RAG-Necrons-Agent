from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.config import settings


class Base(DeclarativeBase):
    pass


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("source_file", "source_chunk_id", name="uq_chunks_source_file_source_chunk_id"),
        Index("ix_chunks_source_file", "source_file"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_chunk_id: Mapped[int] = mapped_column(Integer, nullable=False)

    parent_block_id: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_heading: Mapped[str] = mapped_column(Text, nullable=False)
    heading: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)

    source_subblock_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dimension), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
