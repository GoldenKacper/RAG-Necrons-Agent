"""
ETAP 2 — Petla decyzyjna agenta (ReAct) + akumulator wiedzy.

Baza: Twoj run_agent z Agent_With_Loop (Etap 0/1 tamtego projektu),
czyli wersja BEZ referencji $1/$2.

Nowosci wzgledem tamtej petli:
  1. narzedzia zwracaja krotke (tekst_obserwacji, dane_lub_None)
  2. akumulator collected_chunks: dict[int, SearchResult] (klucz = chunk.id
     -> deduplikacja za darmo)
  3. licznik wyszukiwan + twardy limit agent_max_searches
  4. wykrywanie POWTORZONEGO query zanim wykonamy wyszukiwanie
  5. final_text modelu to tylko handoff (Found:/Missing:) — w Etapie 3
     podmienimy koncowke na synteze; na razie zwracamy go jako odpowiedz
     (rusztowanie wariantu A do debugowania petli)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.config import settings
from app.schemas import SearchResult
from app.services.llm import get_chat_client  # reuse istniejacego klienta!
from app.agent.tools import TOOLS, build_tools_param


@dataclass
class AgentRunResult:
    final_text: str  # handoff modelu (Etap 3: log) lub odpowiedz fallbacku
    collected_chunks: dict[int, SearchResult] = field(default_factory=dict)
    search_queries: list[str] = field(default_factory=list)
    steps_used: int = 0


def describe_action(call) -> str:
    """Czytelny opis akcji do logu ReAct (zywcem z Twojego projektu)."""
    name = call.function.name
    args = json.loads(call.function.arguments)
    arg_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
    return f"{name}({arg_str})"


def _normalize_query(query: str) -> str:
    """Normalizacja query do porownywania powtorek.

    (Masz juz taki wzorzec w starym configu przy exact_markers.)
    Swiadomie NIE robimy nic madrzejszego — "Reanimation Protocols roll"
    vs "Reanimation Protocols dice roll" to ROZNE query i tak ma zostac.
    """
    return " ".join(query.lower().split())


def execute_tool_call(call) -> tuple[dict, list[SearchResult] | None]:
    """
    Wykonuje JEDNO wywolanie narzedzia.

    Zwraca: (wiadomosc_role_tool, surowe_wyniki_lub_None)
    """
    name = call.function.name
    try:
        args = json.loads(call.function.arguments)
    except json.JSONDecodeError as e:
        return {"role": "tool", "tool_call_id": call.id, "content": f"Tool error: invalid JSON arguments: {e}"}, None

    if name not in TOOLS:
        return {"role": "tool", "tool_call_id": call.id, "content": f"Unknown tool: {name}"}, None

    try:
        tool_func = TOOLS[name]["function"]
        observation_text, data = tool_func(**args)
        return {"role": "tool", "tool_call_id": call.id, "content": str(observation_text)}, data
    except Exception as e:
        return {"role": "tool", "tool_call_id": call.id, "content": f"Tool error: {e}"}, None


def run_agent(question: str, max_steps: int | None = None) -> AgentRunResult:
    if max_steps is None:
        max_steps = settings.agent_max_steps

    client = get_chat_client()

    messages = [
        {"role": "system", "content": settings.agent_system_prompt},
        {"role": "user", "content": question},
    ]

    collected_chunks: dict[int, SearchResult] = {}
    search_queries: list[str] = []
    seen_queries: set[str] = set()  # znormalizowane query do wykrywania powtorek
    searches_used: int = 0

    for step in range(1, max_steps + 1):
        response = client.chat.completions.create(
            model=settings.chat_model,
            messages=messages,
            tools=build_tools_param(),
            temperature=0.2,
        )
        msg = response.choices[0].message

        # Brak tool_calls => model konczy (handoff Found:/Missing:).
        if not msg.tool_calls:
            return AgentRunResult(
                final_text=msg.content or "",
                collected_chunks=collected_chunks,
                search_queries=search_queries,
                steps_used=step,
            )

        # ---------- LOG ReAct ----------
        print(f"\n===== STEP {step} =====")
        print("Thought:    ", msg.content if msg.content else "(no thought)")
        for call in msg.tool_calls:
            print("Action:     ", describe_action(call))

        # dopisz wiadomosc asystenta z tool_calls (boilerplate z Twojego projektu)
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {"id": c.id, "type": c.type,
                 "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in msg.tool_calls
            ],
        })

        for call in msg.tool_calls:
            # -----------------------------------------------------------
            # narzedzia, tylko od razu budujemy wiadomosc role="tool" z instrukcja.
            # (Wzorzec wiadomosci: {"role": "tool", "tool_call_id": call.id,
            #  "content": "..."} — jak w Twoim projekcie.)
            #
            # Kolejnosc sprawdzania (dla call.function.name == "search_knowledge_base"):
            #
            #   1) LIMIT WYSZUKIWAN: jesli searches_used >= settings.agent_max_searches
            #      -> content w stylu: "Search limit reached. Do not search again.
            #         Summarize what you found and what is missing."
            #
            #   2) POWTORKA: sparsuj query z call.function.arguments,
            #      znormalizuj przez _normalize_query, sprawdz w seen_queries
            #      -> content w stylu: "You already searched for this exact query.
            #         Reformulate with different terms or stop and summarize."
            #
            # Jesli zaden interceptor nie zadzialal -> normalna sciezka:
            #
            #   3) tool_msg, raw = execute_tool_call(call)
            #      - jesli to bylo wyszukiwanie: searches_used += 1,
            #        dopisz query do search_queries i seen_queries
            #      - jesli raw nie jest None: wsyp wyniki do collected_chunks
            #        (klucz = chunk.id) — TU dzieje sie deduplikacja
            #
            # Na koncu KAZDEJ sciezki: messages.append(tool_msg)
            # i print("Observation:", tool_msg["content"][:300], "...") — pelne
            # obserwacje zasmiecaja konsole, przytnij sam log (nie wiadomosc!).
            # -----------------------------------------------------------
            tool_msg = None

            if call.function.name == "search_knowledge_base":
                # 1) LIMIT WYSZUKIWAN
                if searches_used >= settings.agent_max_searches:
                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": (
                            "Search limit reached. Do not search again. "
                            "Summarize what you found and what is missing."
                        ),
                    }

                else:
                    # 2) SPRAWDŹ CZY POWTORKA
                    try:
                        args = json.loads(call.function.arguments or "{}")
                        if not isinstance(args, dict):
                            args = {}
                    except json.JSONDecodeError:
                        args = {}

                    query = args.get("query", "")
                    if not isinstance(query, str):
                        query = str(query)

                    normalized_query = _normalize_query(query)

                    if normalized_query in seen_queries:
                        tool_msg = {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": (
                                "You already searched for this exact query. "
                                "Reformulate with different terms or stop and summarize."
                            ),
                        }

                    else:
                        # 3) NORMALNA SCIEZKA
                        tool_msg, raw = execute_tool_call(call)

                        searches_used += 1
                        search_queries.append(query)
                        seen_queries.add(normalized_query)

                        if raw is not None:
                            for chunk in raw:
                                collected_chunks[chunk.id] = chunk

            else:
                # Normalna sciezka dla innych narzedzi.
                tool_msg, raw = execute_tool_call(call)

                if raw is not None:
                    for chunk in raw:
                        collected_chunks[chunk.id] = chunk

            # Na koncu KAZDEJ sciezki dopisujemy observation do historii.
            messages.append(tool_msg)

            observation = tool_msg.get("content", "")
            print(
                "Observation:",
                observation[:300],
                "..." if len(observation) > 300 else "",
            )

    # ---------- Fallback po max_steps (Twoj wzorzec) ----------
    print("[!] Reached max steps without a final answer.")
    messages.append({"role": "system", "content": settings.agent_fallback_prompt})
    response = client.chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        temperature=0.2,
    )
    return AgentRunResult(
        final_text=response.choices[0].message.content or "",
        collected_chunks=collected_chunks,
        search_queries=search_queries,
        steps_used=max_steps,
    )
