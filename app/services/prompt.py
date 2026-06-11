from __future__ import annotations

from app.config import settings
from app.schemas import SearchResult
from app.services.retrieval import format_context


def build_prompt(question: str, chunks: list[SearchResult]) -> str:
    context = format_context(chunks)
    return (
        f"SYSTEM:\n"
        f"{settings.agent_system_prompt}\n\n"
        f"CONTEXT:\n"
        f"{context}\n\n"
        f"QUESTION:\n"
        f"{question}\n\n"
        f"ANSWER:\n"
    )
