from __future__ import annotations

from functools import lru_cache
from openai import OpenAI
from app.config import settings


@lru_cache(maxsize=1)
def get_chat_client() -> OpenAI:
    kwargs = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


def generate_answer(prompt: str) -> str:
    client = get_chat_client()
    response = client.chat.completions.create(
        model=settings.chat_model,
        messages=[
            {"role": "system", "content": settings.agent_system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or ""
