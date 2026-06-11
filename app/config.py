from __future__ import annotations

import textwrap
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

    # ------------------------------------------------------------------
    # Agent (Agentic RAG)
    # ------------------------------------------------------------------

    # Twardy limit krokow petli — ostatnia linia obrony przed zapetleniem.
    agent_max_steps: int = _env_int("AGENT_MAX_STEPS", 8)

    # Limit wywolan search_knowledge_base — NIZSZY niz max_steps,
    # zeby po wyczerpaniu wyszukiwan zostaly kroki na finalna decyzje.
    agent_max_searches: int = _env_int("AGENT_MAX_SEARCHES", 5)

    # top_k pojedynczego wyszukiwania agenta. Mniej niz 7 z klasycznego RAG,
    # bo wyszukiwan bedzie kilka, a kontekst 8B jest cenny.
    agent_search_top_k: int = _env_int("AGENT_SEARCH_TOP_K", 4)

    # Maks. dlugosc tekstu JEDNEGO chunka w obserwacji dla modelu (w znakach).
    # Pelne teksty i tak trafia do akumulatora — przycinamy tylko to, co widzi
    # model w petli. Synteza (Etap 3) dostanie pelne chunki.
    agent_observation_char_limit: int = _env_int("AGENT_OBSERVATION_CHAR_LIMIT", 500)

    # ------------------------------------------------------------------
    # PROMPT 1/3: prompt decyzyjny petli agenta (EN).
    # ------------------------------------------------------------------
    agent_system_prompt: str = textwrap.dedent("""
        You are a Warhammer 40k Necrons rules research agent.

        Your only job is to search the knowledge base.
        Do not answer from memory.
        Do not invent rules.
        Only search_knowledge_base results are trusted.

        Use search_knowledge_base with short English rulebook phrases.

        Correct queries:
        "Reanimation Protocols"
        "Reanimation Protocols dice roll"
        "Awakened Dynasty Stratagems"
        "Canoptek Court detachment rule"

        Wrong queries:
        "How does Reanimation Protocols work?"
        "Can you explain Necron healing?"
        "What should I do with my army?"
        
        The user's question may be phrased naturally as a full question.
        The query rules above apply only to the arguments of search_knowledge_base, not to the user's question.

        If the question has multiple topics, search each topic separately.
        
        Scores typically range from about 0.6 to 0.8. 
        Results below about 0.68 are often weak matches, rewrite the query with different rule terms and search again.
        The score is only a hint — judge relevance mainly by reading the text: does it actually talk about the topic?

        Never repeat the exact same query.

        Search again when:
        - scores are low,
        - only part of the question is covered,
        - another topic still needs evidence,
        - a result reveals a better rule name to search.

        Stop searching when:
        - enough relevant results were found,
        - all parts of the question are covered,
        - or reasonable reformulations failed.

        When stopping, do not give a full final answer.
        Give a short handoff summary:

        Found:
        - ...

        Missing:
        - ...

        Use only search results.
        If something was not found, say it was not found.
        """).strip()

    # ------------------------------------------------------------------
    # PROMPT 2/3: fallback po przekroczeniu limitu krokow (EN).
    # ------------------------------------------------------------------
    agent_fallback_prompt: str = textwrap.dedent("""
        Step limit reached.
        
        Stop using tools.
        
        Do not call tools again.
        Do not invent missing information.
        Do not claim that more work was done.
        
        Summarize only what is already known from the conversation and tool results.
        
        Include:
        - findings so far,
        - important exact tool results,
        - missing or uncertain information,
        - tool errors if any.
        
        This is a handoff summary for a later synthesis step, not the final user answer.
        Keep it concise.
        """).strip()

    # ------------------------------------------------------------------
    # PROMPT 3/3: prompt syntezy koncowej (EN).
    # ------------------------------------------------------------------
    synthesis_system_prompt: str = textwrap.dedent("""
        Answer only from the provided context.
        
        Topic: Warhammer 40k Necrons rules.
        
        The context may contain results from multiple searches. Merge relevant parts into one short answer.
        
        Rules:
        - Use no outside knowledge.
        - Do not guess.
        - Answer supported parts of the question.
        - If something is missing, say what was not found.
        - If nothing answers the question, say: "I don't know based on the provided context."
        - Answer in English.
        - Cite facts as [SOURCE n].
        - List only sources used.
        
        End with:
        
        Sources:
        1. filename | section
        2. filename | section
        """).strip()

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

    exact_markers_from_content: set[str] = field(init=False)

    def __post_init__(self) -> None:
        # exact marker set for second-level splitting.
        # We normalize spaces + case so that e.g. "DETACHMENT RULE" matches
        # "Detachment Rule" as long as the whole line is only that label.

        # This is the exact-match set for inner labels.
        exact_markers_from_content = {
            re.sub(r"\s+", " ", label).strip().casefold() for label in self.labels_in_content
        }

        object.__setattr__(self, "exact_markers_from_content", exact_markers_from_content)


settings = Settings()
