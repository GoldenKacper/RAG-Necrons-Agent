# Plan realizacji: Agentic RAG (Necrons)

Cel: połączenie projektu RAG (pgvector + FastAPI) z agentem w pętli tak, aby model
sam decydował o wyszukiwaniach, przeformułowywał zapytania i rozbijał złożone pytania,
a finalna odpowiedź powstawała w osobnym, czystym kroku syntezy (wariant B)
z cytowaniami [SOURCE n].

Stack: LM Studio (Llama 3.1 8B Instruct + bge-large-en-v1.5), PostgreSQL 17 + pgvector,
Python 3.14, natywny tool calling przez API OpenAI-compatible.

Zasada pracy: Claude przygotowuje szkielet etapu -> Ty uzupełniasz -> recenzja kodu ->
dopiero potem następny etap.

---

## Etap 0 — Fundament i konfiguracja

Cel: przygotować strukturę i konfigurację, zero logiki.

Zakres:
- [x] Nowy pakiet `app/agent/` z plikami: `__init__.py`, `tools.py`, `loop.py`, `synthesis.py`
- [x] Rozszerzenie `Settings` w `config.py` o sekcję agenta:
  - `agent_max_steps` (np. 8) — twardy limit kroków pętli
  - `agent_max_searches` (np. 5) — limit wywołań search_knowledge_base (niższy niż max_steps)
  - `agent_search_top_k` (np. 4) — mniej niż 7 z klasycznego RAG, bo wyników będzie kilka serii
  - `agent_observation_char_limit` (np. 500) — przycinanie tekstu chunka w obserwacji
  - `agent_system_prompt` — prompt decyzyjny pętli (EN)
  - `agent_fallback_prompt` — wrap-up po przekroczeniu limitu (adaptacja z projektu agenta)
  - `synthesis_system_prompt` — prompt syntezy (adaptacja obecnego `system_prompt`)
- [x] Decyzja: obecny `system_prompt` zostaje nietknięty dla starego `/ask` (porównania!)

Kryterium ukończenia: projekt się importuje, stary `/ask` działa jak wcześniej.

---

## Etap 1 — Narzędzia agenta

Cel: `search_knowledge_base` + `ask_user` jako narzędzia w stylu rejestru TOOLS.

Zakres:
- [x] `tools.py`:
  - `search_knowledge_base(query: str, top_k: int | None)` — wrapper na istniejący
    `search_similar_chunks`; zwraca DWIE rzeczy: sformatowaną obserwację (string dla modelu)
    oraz surowe `list[SearchResult]` (dla akumulatora w pętli)
  - format obserwacji: `[chunk_id] parent_heading / heading (score 0.72)` + przycięty tekst
  - schemat JSON z mocnym description: query po angielsku, terminologia z rulebooka,
    fraza zamiast pełnego pytania
  - `ask_user` — przeniesione z projektu agenta (input() na razie wystarczy)
  - rejestr `TOOLS = {nazwa: {"schema": ..., "function": ...}}`
- [x] Test standalone (`if __name__ == "__main__"`): wywołanie narzędzia ręcznie,
  sprawdzenie formatu obserwacji i przycinania

Pułapki:
- obserwacja musi być zwięzła — po 3-4 wyszukiwaniach kontekst 8B szybko puchnie
- score pokazujemy modelowi (potrzebny do heurystyki "szukaj inaczej")

Kryterium ukończenia: ręczne wywołanie zwraca czytelną obserwację + listę SearchResult.

---

## Etap 2 — Pętla agenta z akumulatorem wiedzy

Cel: działająca pętla decyzyjna (na razie z odpowiedzią wariantu A jako rusztowaniem
do debugowania — synteza B dochodzi w Etapie 3).

Zakres:
- [x] `loop.py`: `run_agent(question) -> AgentRunResult`
  - bazą jest `run_agent` z Etapu 0 projektu agenta (wersja BEZ referencji $1/$2)
  - logowanie ReAct: Thought / Action / Observation
  - akumulator: `collected_chunks: dict[int, SearchResult]` (klucz = chunk.id,
    deduplikacja za darmo)
  - historia zapytań: `search_queries: list[str]`
  - licznik wyszukiwań, po przekroczeniu `agent_max_searches` -> obserwacja
    "Search limit reached. Answer with what you have."
- [x] `AgentRunResult` (dataclass): `final_text`, `collected_chunks`, `search_queries`,
  `steps_used`
- [x] Skrypt testowy `scripts/test_agent.py` z 3-4 pytaniami o różnej trudności
  (proste / wymagające przeformułowania / wielowątkowe)

Pułapki (wystąpią — to nie pesymizm, to 8B):
- identyczne query w kółko -> wykrywanie powtórek w kodzie i obserwacja
  "You already searched for this exact query..."
- model odpowiada po pierwszym wyszukiwaniu mimo słabych wyników -> heurystyka score
  w system prompcie
- model wkleja całe pytanie usera jako query zamiast frazy -> poprawić description schematu

Kryterium ukończenia: na pytaniu wielowątkowym agent wykonuje >=2 różne wyszukiwania
i kończy bez zapętlenia.

---

## Etap 3 — Synteza odpowiedzi (wariant B)

Cel: finalna odpowiedź powstaje z czystego, zdeduplikowanego kontekstu, nie z historii pętli.

Zakres:
- [ ] `synthesis.py`: `synthesize_answer(question, chunks: list[SearchResult]) -> str`
  - sortowanie chunków (np. po score malejąco), opcjonalny limit łącznych tokenów
  - reuse istniejących `format_context` + konwencji [SOURCE n] i listy źródeł
  - osobne wywołanie LLM z `synthesis_system_prompt` (bez historii pętli!)
- [ ] Spięcie w `loop.py`: gdy model kończy wołać narzędzia -> jego tekst staje się
  tylko sygnałem/logiem, a odpowiedź buduje synteza z akumulatora
- [ ] Przypadek brzegowy: akumulator pusty (model nic nie wyszukał) -> co robimy?
  (propozycja: wymuszenie jednego wyszukiwania pytaniem usera jako query — decyzja Twoja)

Kryterium ukończenia: odpowiedź zawiera poprawne [SOURCE n] mapujące się na chunki
z akumulatora, a nie na kolejność obserwacji w pętli.

---

## Etap 4 — Odporność i ask_user

Cel: zabezpieczenia + human-in-the-loop.

Zakres:
- [ ] Fallback po `agent_max_steps` (adaptacja Twojego wrap-up promptu)
- [ ] `ask_user` wpięty do rejestru; reguły w prompcie: tylko gdy pytanie usera jest
  niejednoznaczne (np. nie wiadomo o który detachment chodzi), nigdy zamiast wyszukiwania
- [ ] Obsługa błędów narzędzi (wzorzec "Tool error: ..." już masz)
- [ ] Przegląd logów z testów: czy heurystyki score/powtórek faktycznie działają

Kryterium ukończenia: agent przeżywa pytania-pułapki (o rzecz spoza bazy, pytanie
niejednoznaczne, pytanie wymagające 3+ wyszukiwań) bez zapętlenia i bez halucynacji.

---

## Etap 5 — Integracja z FastAPI i porównanie

Cel: agent jako endpoint + dowód, że jest lepszy od liniowego RAG.

Zakres:
- [ ] Schematy Pydantic: `AgentAskRequest`, `AgentAskResponse` (answer, sources,
  search_queries, steps_used)
- [ ] Endpoint `POST /agent-ask` obok istniejącego `/ask`
- [ ] Mini-ewaluacja: 5-8 pytań przepuszczonych przez OBA endpointy, tabelka porównawcza
  (trafność, źródła, liczba wyszukiwań) — to będzie świetny materiał do README/portfolio

Kryterium ukończenia: przynajmniej 2-3 pytania, na których agent wyraźnie wygrywa
z liniowym RAG (typowo: pytania wielowątkowe i źle sformułowane).

---

## Etap 6 (opcjonalny) — Usprawnienia

Pomysły do wyboru, gdy podstawa działa:
- dekompozycja pytania na pod-zapytania jawnym krokiem planowania
- self-check przed syntezą: "czy zebrany kontekst odpowiada na pytanie? czego brakuje?"
- próg score odcinający śmieciowe chunki przed syntezą
- streaming logów ReAct do odpowiedzi API (debug w przeglądarce)
- drugi plik źródłowy w bazie -> filtr source_file jako parametr narzędzia

---

## Decyzje projektowe (ustalone)

1. Budujemy w kopii projektu RAG; projekt agenta to tylko źródło wzorców.
2. Bez systemu referencji $1/$2 — był pod liczby, w RAG model MA czytać obserwacje.
3. Wariant B syntezy od początku architektury (Etap 2 ma tymczasową odpowiedź A
   wyłącznie jako rusztowanie do debugowania pętli).
4. Pytania, baza i prompty: EN. Rozmowa i komentarze: PL.
5. Stary `/ask` zostaje bez zmian jako baseline do porównań.