"""
Etap 2 (jeszcze pusty — Etap 0 to tylko struktura).

Tu powstana:
  - AgentRunResult (dataclass): final_text, collected_chunks, search_queries, steps_used
  - run_agent(question, max_steps) -> AgentRunResult
      petla decyzyjna w stylu ReAct (Thought / Action / Observation),
      BEZ systemu referencji $1/$2,
      z akumulatorem: collected_chunks: dict[int, SearchResult] (klucz = chunk.id),
      z licznikiem wyszukiwan (agent_max_searches) i wykrywaniem powtorzonych query.
"""
