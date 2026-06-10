from __future__ import annotations

from functools import lru_cache
from typing import Iterable

from openai import OpenAI

from app.config import settings


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    kwargs = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    client = get_openai_client()
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]


def get_embedding(text: str) -> list[float]:
    vectors = embed_texts([text])
    return vectors[0]


def normalize_input_text(text: str) -> str:
    return " ".join(text.split()).strip()


def iter_batches(items: list[dict], batch_size: int) -> Iterable[list[dict]]:
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]
