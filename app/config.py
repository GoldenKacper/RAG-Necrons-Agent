from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import re

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    project_root: Path = Path(__file__).resolve().parents[1]

    # Database
    postgres_host: str = _env("POSTGRES_HOST", "localhost") or "localhost"
    postgres_port: int = _env_int("POSTGRES_PORT", 5432)
    postgres_db: str = _env("POSTGRES_DB", "rag_necrons") or "rag_necrons"
    postgres_user: str = _env("POSTGRES_USER", "rag_user") or "rag_user"
    postgres_password: str = _env("POSTGRES_PASSWORD", "rag_password") or "rag_password"
    database_url: str | None = _env("DATABASE_URL")

    # OpenAI-compatible API
    openai_api_key: str = _env("OPENAI_API_KEY", "sk-local-placeholder") or "sk-local-placeholder"
    openai_base_url: str | None = _env("OPENAI_BASE_URL")
    embedding_model: str = _env("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small") or "text-embedding-3-small"
    chat_model: str = _env("OPENAI_CHAT_MODEL", "gpt-4o-mini") or "gpt-4o-mini"
    embedding_dimension: int = _env_int("EMBEDDING_DIMENSION", 1024)

    # Files
    chunks_input_path: Path = Path(
        _env("CHUNKS_INPUT_PATH", "data/processed/necrons_chunks.jsonl") or "data/processed/necrons_chunks.jsonl")

    # Runtime
    top_k: int = _env_int("TOP_K_DEFAULT", 5)

    system_prompt: str = (
        "You are an assistant who responds solely based on the provided context, without making anything up. "
        "If the context doesn't provide an answer, just say you don't know. "
        "We'll be talking about the Warhammer 40k  and the rules for the Necrons faction. "
        "Keep your answers short, to the point, and in English. "
        "When you use information from a source, cite it exactly as [SOURCE n]. "
        "At the end of the answer, list the sources used, according to the following diagram, here is an example: "
        "\"Sources:\n"
        "1. prepared_necrons.txt | Army Rules / Reanimation Protocols\n"
        "2. prepared_necrons.txt | Awakened Dynasty / Stratagems\"\n"
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # chunking thresholds.
    chunk_max_tokens: int = _env_int("CHUNK_MAX_TOKENS", 500)
    chunk_min_tokens: int = _env_int("CHUNK_MIN_TOKENS", 150)

    top_level_selections: set[str] = field(default_factory=lambda: {
        "Necrons",
        "Contents",
        "Books",
        "FAQ",
        "Keywords",
        "Introduction",
        "Army Rules",
        "Crusade Rules",
        "Boarding Actions",
    })

    # File-specific structure. Keeping this list explicit makes stage 1 more reliable.
    detachment_names: set[str] = field(default_factory=lambda: {
        "Awakened Dynasty",
        "Annihilation Legion",
        "Canoptek Court",
        "Obeisance Phalanx",
        "Hypercrypt Legion",
        "Starshatter Arsenal",
        "Cryptek Conclave",
        "Cursed Legion",
        "Pantheon of Woe",
    })

    subsection_labels: set[str] = field(default_factory=lambda: {
        "Detachment Rule",
        "Enhancements",
        "Stratagems",
        "Army Rule",
        "Rules Adaptations",
        "Mustering a Boarding Patrol",
        "Crusade Rules",
        "Books",
        "Introduction",
        "FAQ",
        "Faction Pack",
        "Reanimation Protocols",
        "Awakening A Tomb World",
        "Tomb Ship Complement",
        "Deranged Outcasts",
        "Canoptek Harvesters",
        "Harbinger Cabal"

    })

    faq_prefixes: tuple[str] = field(default_factory=lambda: ("Q:", "A:"))

    labels_in_content: set[str] = field(default_factory=lambda: {
        "Hypercrypt Legion",
        "Agendas",
        "Pantheon of Woe",
        "Cosmic Distortion",
        "Terrifying Charge",
        "Awakening A Tomb World",
        "Worthy Foes",
        "Detachment Rule",
        "Harbinger Cabal",
        "Army Rule",
        "Command Protocols",
        "Reanimation System",
        "Crusade Relics",
        "Transdimensional Reinforcement",
        "Conquest Protocols",
        "Arcanoscientific Expertise",
        "Introduction",
        "Awakened Dynasty",
        "Crusade Rules",
        "Power Matrix",
        "Cursed Legion",
        "Crusade Badges",
        "Mustering a Boarding Patrol",
        "Obeisance Phalanx",
        "Technosorcerous Augmentations",
        "Awakening Points Remaining",
        "Cryptek Conclave",
        "Rules Adaptations",
        "Retribution Protocols",
        "Battle Scars",
        "Annihilation Protocol",
        "Deranged Outcasts",
        "Faction Pack: Necrons",
        "Enhancements",
        "Books",
        "Necrodermal Binding Abilities",
        "Boarding Actions",
        "Reanimation Protocols",
        "Requisitions",
        "Starshatter Arsenal",
        "Tomb Ship Complement",
        "Canoptek Harvesters",
        "Stratagems",
        "Battle Traits",
        "Cold Fervour",
        "Relentless Onslaught",
        "FAQ",
        "Canoptek Court",
        "Annihilation Legion",
        "Command System",
        "Hyperphasing",
        "Translocation System",
        "Army Rules",
    })

    exact_markers: set[str] = field(init=False)
    exact_markers_from_content: set[str] = field(init=False)

    def __post_init__(self) -> None:
        # exact marker set for second-level splitting.
        # We normalize spaces + case so that e.g. "DETACHMENT RULE" matches
        # "Detachment Rule" as long as the whole line is only that label.
        exact_markers = exact_markers = {
            re.sub(r"\s+", " ", marker).strip().casefold()
            for marker in (self.top_level_selections | self.detachment_names | self.subsection_labels)
        }

        # This is the exact-match set for inner labels.
        exact_markers_from_content = {
            re.sub(r"\s+", " ", label).strip().casefold() for label in self.labels_in_content
        }

        object.__setattr__(self, "exact_markers", exact_markers)
        object.__setattr__(self, "exact_markers_from_content", exact_markers_from_content)


settings = Settings()
