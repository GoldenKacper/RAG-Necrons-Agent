"""
ETAP 2 — skrypt testowy petli agenta.

Uruchom: python -m scripts.test_agent   (lub bezposrednio, zaleznie od struktury)

Pytania ulozone wg rosnacej trudnosci — kazde testuje inna umiejetnosc petli.
Po kazdym uruchomieniu sprawdz w logach ReAct:
  - ile bylo wyszukiwan i JAKIE query (czy frazy, nie pytania?)
  - czy akumulator deduplikuje (te same chunk.id z roznych query)
  - czy handoff konczacy ma format Found:/Missing:
"""

from app.agent.loop import run_agent

QUESTIONS = [
    # 1. Proste, jednowatkowe — oczekiwanie: 1-2 wyszukiwania i koniec.
    "How does Reanimation Protocols work?",

    # 2. Wielowatkowe — oczekiwanie: OSOBNE wyszukiwania dla enhancementow
    #    i stratagemow (test dekompozycji).
    "What enhancements and stratagems are available in the Awakened Dynasty detachment?",

    # 3. "Ludzkie" slownictwo bez nazwy reguly — oczekiwanie: model znajdzie
    #    Reanimation Protocols mimo braku tej frazy w pytaniu, byc moze
    #    po przeformulowaniu (test reformulacji).
    "Can my destroyed Necron models come back to the battlefield?",

    # 4. Spoza bazy — oczekiwanie: model NIE wymysla odpowiedzi, w handoffie
    #    Missing: jasno mowi, ze nie znalazl (test uczciwosci przy slabych score).
    "What are the rules for Space Marines Tactical Squads?",
]

if __name__ == "__main__":
    for i, q in enumerate(QUESTIONS, start=1):
        print(f"\n{'#' * 70}")
        print(f"# QUESTION {i}: {q}")
        print(f"{'#' * 70}")

        result = run_agent(q)

        print(f"\n--- HANDOFF (final_text) ---\n{result.final_text}")
        print(f"\n--- STATS ---")
        print(f"steps_used:      {result.steps_used}")
        print(f"search_queries:  {result.search_queries}")
        print(f"collected_chunks ({len(result.collected_chunks)}): "
              f"{sorted(result.collected_chunks.keys())}")

# Results:
# ######################################################################
# # QUESTION 1: How does Reanimation Protocols work?
# ######################################################################
#
# ===== STEP 1 =====
# Thought:     (no thought)
# Action:      search_knowledge_base(query='Reanimation Protocols')
# Observation: [chunk 17] FAQ / Q: Do rules that activate Reanimation Protocols (e.g. the Protocol of the Undying Legions Stratagem) only apply to a Bodyguard unit whose attached Leader unit is on the battlefield if one or more models from that Bodyguard unit are also still on the battlefield? (score 0.74)
# Q: Do r ...
#
# --- HANDOFF (final_text) ---
# Found:
# - Reanimation Protocols activate when a Necron is slain.
# - The Protocol of the Undying Legions Stratagem applies to a Bodyguard unit whose attached Leader unit is on the battlefield if one or more models from that Bodyguard unit are also still on the battlefield.
# - Other rules applicable to Reanimation Protocols are applied when using the Protocol of the Undying Legions Stratagem.
# - The Resurrection Flux ability adds 1 to the result of a unit's Reanimation Protocols roll while it is Below Half-strength.
# - The Anastasic Contingency allows a unit to use its Reanimation Protocols ability once per battle after an enemy unit has caused it to go below its Starting Strength.
# - The Contramortis Protocol Master System ability can be used to allow a Necron unit to use its Reanimation Protocols ability once per battle.
#
# Missing:
# - A clear explanation of how Reanimation Protocols work in general.
#
# --- STATS ---
# steps_used:      2
# search_queries:  ['Reanimation Protocols']
# collected_chunks (4): [7, 17, 21, 99]
#
# ######################################################################
# # QUESTION 2: What enhancements and stratagems are available in the Awakened Dynasty detachment?
# ######################################################################
#
# ===== STEP 1 =====
# Thought:     tool call:
# Action:      search_knowledge_base(query='Awakened Dynasty enhancements')
# Observation: [chunk 125] Crusade Rules / Crusade Badges (score 0.71)
# Your dominion has moved far beyond the reclamation of lost power as your legions seize new worlds and entire planetary systems. Your nobles and Crypteks lead armies on unending campaigns of systematic conquest, eradication and enslavement, and  ...
#
# ===== STEP 2 =====
# Thought:     (no thought)
# Action:      search_knowledge_base(query='Awakened Dynasty stratagems')
# Observation: [chunk 25] Awakened Dynasty / Stratagems (score 0.72)
# Stratagems
# PROTOCOL OF THE ETERNAL REVENANT
# 1CP
# Awakened Dynasty – Epic Deed Stratagem
# Necron rulers possess enhanced self-repair systems.
# WHEN: Any phase.
#
# TARGET: One NECRONS INFANTRY CHARACTER model from your army that was just destroyed. You  ...
#
# --- HANDOFF (final_text) ---
# Found:
# - Dread Majesty (Aura) 30 pts enhancement
# - Protocol of the Eternal Revenant stratagem
# - Protocol of the Hungry Void stratagem
#
# Missing:
# - Other enhancements and stratagems available in the Awakened Dynasty detachment
#
# --- STATS ---
# steps_used:      3
# search_queries:  ['Awakened Dynasty enhancements', 'Awakened Dynasty stratagems']
# collected_chunks (6): [25, 26, 60, 98, 124, 125]
#
# ######################################################################
# # QUESTION 3: Can my destroyed Necron models come back to the battlefield?
# ######################################################################
#
# ===== STEP 1 =====
# Thought:     (no thought)
# Action:      search_knowledge_base(query='Reanimation Protocols')
# Observation: [chunk 17] FAQ / Q: Do rules that activate Reanimation Protocols (e.g. the Protocol of the Undying Legions Stratagem) only apply to a Bodyguard unit whose attached Leader unit is on the battlefield if one or more models from that Bodyguard unit are also still on the battlefield? (score 0.74)
# Q: Do r ...
#
# --- HANDOFF (final_text) ---
# Found:
# - Reanimation Protocols
# - Protocol of the Undying Legions Stratagem
# - Their Number is Legion ability
# - Resurrection Flux
# - Anastasic Contingency
# - Contramortis Protocol
# - Reanimation Master System Ability
#
# Missing:
# - How destroyed Necron models can come back to the battlefield
#
# --- STATS ---
# steps_used:      2
# search_queries:  ['Reanimation Protocols']
# collected_chunks (4): [7, 17, 21, 99]
#
# ######################################################################
# # QUESTION 4: What are the rules for Space Marines Tactical Squads?
# ######################################################################
#
# ===== STEP 1 =====
# Thought:     (no thought)
# Action:      search_knowledge_base(query='Space Marines Tactical Squad rules')
# Observation: [chunk 3] Contents / Detachment Rule (score 0.69)
# Detachment Rule
# Cosmic Distortion
# Necrodermal Binding Abilities
#
# Stratagems
#
# Crusade Rules
#
# Awakening A Tomb World
# Command System
# Reanimation System
# Translocation System
# Agendas
# Requisitions
# Battle Traits
# Battle Scars
# Crusade Relics
# Crusade Badges
# Aw ...
#
# ===== STEP 2 =====
# Thought:     (no thought)
# Action:      search_knowledge_base(query='Space Marines Tactical Squad rules')
# Observation: You already searched for this exact query. Reformulate with different terms or stop and summarize.
#
# --- HANDOFF (final_text) ---
# Found:
# - Detachment Rule
# - Cosmic Distortion
# - Necrodermal Binding Abilities
# - Stratagems
# - Boarding Actions
# - Introduction
# - Army Rules
# - Reanimation Protocols
# - Awakened Dynasty
# - Command Protocols
# - Enhancements
# - Annihilation Legion
# - Annihilation Protocol
# - Canoptek Court
# - Power Matrix
# - Obeisance Phalanx
# - Worthy Foes
# - Hypercrypt Legion
# - Hyperphasing
# - Starshatter Arsenal
#
# Missing:
# - Space Marines Tactical Squad rules
#
# --- STATS ---
# steps_used:      3
# search_queries:  ['Space Marines Tactical Squad rules']
# collected_chunks (4): [2, 3, 126, 127]


# ----------------------------------------------------------
# ----------------------------------------------------------
# ######################################################################
# # QUESTION 1: How does Reanimation Protocols work?
# ######################################################################
#
# ===== STEP 1 =====
# Thought:     (no thought)
# Action:      search_knowledge_base(query='Reanimation Protocols')
# Observation: [chunk 17] FAQ / Q: Do rules that activate Reanimation Protocols (e.g. the Protocol of the Undying Legions Stratagem) only apply to a Bodyguard unit whose attached Leader unit is on the battlefield if one or more models from that Bodyguard unit are also still on the battlefield? (score 0.74)
# Q: Do r ...
#
# --- HANDOFF (final_text) ---
# Found:
# - Reanimation Protocols FAQ / Q: Do rules that activate Reanimation Protocols (e.g. the Protocol of the Undying Legions Stratagem) only apply to a Bodyguard unit whose attached Leader unit is on the battlefield if one or more models from that Bodyguard unit are also still on the battlefield?
# - Reanimation Protocols FAQ / Q: When using the Protocol of the Undying Legions Stratagem, are any other rules that are applicable to Reanimation Protocols applied (e.g. Necron Warriors’ Their Number is Legion ability)?
# - Reanimation Protocols Army Rules
# - Reanimation Protocols Crusade Rules
#
# Missing:
# - How Reanimation Protocols work in general
#
# --- STATS ---
# steps_used:      2
# search_queries:  ['Reanimation Protocols']
# collected_chunks (4): [7, 17, 21, 99]
#
# ######################################################################
# # QUESTION 2: What enhancements and stratagems are available in the Awakened Dynasty detachment?
# ######################################################################
#
# ===== STEP 1 =====
# Thought:     tool call:
# Action:      search_knowledge_base(query='Awakened Dynasty enhancements')
# Observation: [chunk 125] Crusade Rules / Crusade Badges (score 0.71)
# Your dominion has moved far beyond the reclamation of lost power as your legions seize new worlds and entire planetary systems. Your nobles and Crypteks lead armies on unending campaigns of systematic conquest, eradication and enslavement, and  ...
#
# ===== STEP 2 =====
# Thought:     (no thought)
# Action:      search_knowledge_base(query='Awakened Dynasty stratagems')
# Observation: [chunk 25] Awakened Dynasty / Stratagems (score 0.72)
# Stratagems
# PROTOCOL OF THE ETERNAL REVENANT
# 1CP
# Awakened Dynasty – Epic Deed Stratagem
# Necron rulers possess enhanced self-repair systems.
# WHEN: Any phase.
#
# TARGET: One NECRONS INFANTRY CHARACTER model from your army that was just destroyed. You  ...
#
# --- HANDOFF (final_text) ---
# Found:
# - Dread Majesty (Aura) enhancement
# - Miniaturised Nebuloscope enhancement
# - Protocol of the Eternal Revenant stratagem
# - Protocol of the Undying Legions stratagem
# - Protocol of the Hungry Void stratagem
#
# Missing:
# - Other enhancements available in the Awakened Dynasty detachment
# - Other stratagems available in the Awakened Dynasty detachment
#
# --- STATS ---
# steps_used:      3
# search_queries:  ['Awakened Dynasty enhancements', 'Awakened Dynasty stratagems']
# collected_chunks (6): [25, 26, 60, 98, 124, 125]
#
# ######################################################################
# # QUESTION 3: Can my destroyed Necron models come back to the battlefield?
# ######################################################################
#
# ===== STEP 1 =====
# Thought:     (no thought)
# Action:      search_knowledge_base(query='Reanimation Protocols')
# Observation: [chunk 17] FAQ / Q: Do rules that activate Reanimation Protocols (e.g. the Protocol of the Undying Legions Stratagem) only apply to a Bodyguard unit whose attached Leader unit is on the battlefield if one or more models from that Bodyguard unit are also still on the battlefield? (score 0.74)
# Q: Do r ...
#
# --- HANDOFF (final_text) ---
# Found:
# - Reanimation Protocols
# - Protocol of the Undying Legions Stratagem
# - Their Number is Legion ability
# - Resurrection Flux
# - Anastasic Contingency
# - Contramortis Protocol
# - Army Faction NECRONS
#
# Missing:
# - How destroyed Necron models can come back to the battlefield.
#
# --- STATS ---
# steps_used:      2
# search_queries:  ['Reanimation Protocols']
# collected_chunks (4): [7, 17, 21, 99]
#
# ######################################################################
# # QUESTION 4: What are the rules for Space Marines Tactical Squads?
# ######################################################################
#
# ===== STEP 1 =====
# Thought:     (no thought)
# Action:      search_knowledge_base(query='Space Marines Tactical Squad rules')
# Observation: [chunk 126] Boarding Actions / Introduction (score 0.69)
# Introduction
# Within the following pages you will find numerous Boarding Actions Detachments that can be used in your Boarding Actions games. Each lists which units you can include in your army, any modifications to those units’ army rule as pr ...
#
# ===== STEP 2 =====
# Thought:     (no thought)
# Action:      search_knowledge_base(query='Space Marines Tactical Squad detachment rule')
# Observation: [chunk 80] Pantheon of Woe / Pantheon of Woe (score 0.65)
# To unleash such a power is a strategy of last resort for most Necrons, for it sees multiple C’tan shards released from tesseract oubliettes and hurled into the heart of the foe. Though the Necrons employ powerful mechanisms to control the sha ...
#
# --- HANDOFF (final_text) ---
# Found:
# - Boarding Actions rules for Space Marines Tactical Squads were not found.
# - The Reanimation Protocols ability and its effects on units were found.
#
# Missing:
# - Space Marines Tactical Squad detachment rule.
#
# --- STATS ---
# steps_used:      3
# search_queries:  ['Space Marines Tactical Squad rules', 'Space Marines Tactical Squad detachment rule']
# collected_chunks (6): [17, 20, 80, 126, 127, 134]