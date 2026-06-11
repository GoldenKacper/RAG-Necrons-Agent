"""
ETAP 1 — Narzedzia agenta.

Tu zyja narzedzia + rejestr TOOLS (wzorzec z Twojego Agent_With_Loop).

KLUCZOWA ROZNICA vs Agent_With_Loop:
  search_knowledge_base zwraca KROTKE (observation_text, raw_results):
    - observation_text -> trafia do modelu jako tresc wiadomosci role="tool"
    - raw_results      -> trafia do akumulatora w petli (Etap 2), PELNE teksty
  Dlatego w rejestrze TOOLS dodajemy flage "returns_data", a executor w loop.py
  bedzie musial ja obsluzyc (zobaczysz w Etapie 2).
"""

from __future__ import annotations

from app.config import settings
from app.schemas import SearchResult
from app.services.retrieval import search_similar_chunks


# ---------------------------------------------------------------------------
# Narzedzie 1: search_knowledge_base
# ---------------------------------------------------------------------------

def _trim_text(text: str, limit: int) -> str:
    """Przycina tekst chunka do limitu znakow, z markerem, zeby model WIEDZIAL,
    ze widzi fragment (inaczej moze uznac przyciete zdanie za kompletna regule)."""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " [...truncated]"


def format_observation(results: list[SearchResult]) -> str:
    """
    Buduje tekst obserwacji DLA MODELU z listy wynikow wyszukiwania.
    Przykład:
            [chunk 42] Awakened Dynasty / Stratagems (score 0.71)
            <tekst przyciety przez _trim_text do settings.agent_observation_char_limit>

        * chunk.id w nawiasie — przyda sie w logach do sledzenia deduplikacji
        * parent_heading / heading — model czesto pozna lepsza nazwe reguly
          wlasnie z naglowka i uzyje jej w kolejnym query (to jest feature!)
        * score zaokraglony do 2 miejsc — model potrzebuje go do heurystyki 0.45
      - sekcje oddziel pusta linia
    """
    observations: list[str] = []

    for result in results:
        chunk_id = result.id
        parent_heading = result.parent_heading
        heading = result.heading
        score = result.score
        text = _trim_text(result.text, settings.agent_observation_char_limit)

        section = f"[chunk {chunk_id}] {parent_heading} / {heading} (score {score:.2f})\n{text}"
        observations.append(section)

    return "\n\n".join(observations) if observations else "No relevant chunks found. Please reformulate your query."


def search_knowledge_base(query: str, top_k: int | None = None) -> tuple[str, list[SearchResult]]:
    """
    Wrapper na retrieval dla agenta.

    Zwraca: (observation_text_dla_modelu, surowe_wyniki_dla_akumulatora)
    """
    if top_k is None:
        top_k = settings.agent_search_top_k

    chunks_found = search_similar_chunks(query, top_k)
    observation_text = format_observation(chunks_found)

    return observation_text, chunks_found


search_knowledge_base_schema = {
    "type": "function",
    "function": {
        "name": "search_knowledge_base",
        "description": (
            "Searches a Warhammer 40k 10th edition Necrons rules knowledge base. "
            "It contains Necrons army rules, detachments, stratagems, enhancements, datasheet-related rules, and FAQ-style rules text. "
            "Use short English rulebook-style search phrases, not full questions. "
            "Correct query: 'Reanimation Protocols dice roll'. "
            "Wrong query: 'How does Reanimation Protocols work?'. "
            "The tool returns matching text fragments with headings and relevance scores from 0 to 1, where higher is better."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Short English rulebook-style search phrase, for example "
                        "'Reanimation Protocols dice roll' or 'Awakened Dynasty stratagems'."
                    ),
                },
                # Swiadoma decyzja: NIE wystawiamy top_k modelowi.
                # 8B i tak nie umie go sensownie dobierac, a kazdy parametr
                # to okazja do bledu. Kod uzywa settings.agent_search_top_k.
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}


# ---------------------------------------------------------------------------
# Narzedzie 2: ask_user (human-in-the-loop)
#
# Wpinamy je do rejestru juz teraz (zeby Etap 2 mial pelny rejestr),
# ale REGULY jego uzycia w system prompcie dopisujemy dopiero w Etapie 4 —
# najpierw chcemy zobaczyc czysta petle wyszukiwania.
# ---------------------------------------------------------------------------

def ask_user(question: str) -> tuple[str, None]:
    """
    zwroc krotke (odpowiedz_uzytkownika, None) — None, bo to narzedzie nie
    produkuje chunkow do akumulatora. Dzieki temu executor w petli obsluzy
    oba narzedzia tym samym kodem.
    """
    print(f"\n[THE AGENT ASKS] {question}")
    answer = input("[YOUR ANSWER] ")
    return answer, None


ask_user_schema = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": (
            "Asks the user one missing required detail. "
            "Use only when the task cannot continue without information that the user did not provide "
            "and no other tool can calculate or look up. "
            "Do not use for normal chat. "
            "Do not ask for information already given. "
            "Never ask the user what a rule says - search the knowledge base instead. "
            "Ask one short, specific question only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "One short, specific question asking only for the missing required detail.",
                },
            },
            "required": ["question"],
            "additionalProperties": False,
        },
    },
}

# ---------------------------------------------------------------------------
# Rejestr — jedyne zrodlo prawdy (Twoj wzorzec z Agent_With_Loop)
# ---------------------------------------------------------------------------

TOOLS = {
    "search_knowledge_base": {
        "schema": search_knowledge_base_schema,
        "function": search_knowledge_base,
    },
    "ask_user": {
        "schema": ask_user_schema,
        "function": ask_user,
    },
}


def build_tools_param() -> list:
    """Lista schematow dla parametru tools= (zywcem z Twojego projektu)."""
    return [tool["schema"] for tool in TOOLS.values()]


# ---------------------------------------------------------------------------
# Test standalone — kryterium ukonczenia Etapu 1
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Wymaga dzialajacej bazy + LM Studio (embeddingi).
    for q in [
        "Reanimation Protocols",  # powinno trafic z wysokim score
        "Awakened Dynasty Stratagems",  # j.w.
        "necron healing recovery",  # celowo "ludzkie" slowa — zobacz score
        "space marines bolter",  # spoza bazy — jak wyglada obserwacja?
    ]:
        print(f"\n{'=' * 60}\nQUERY: {q}\n{'=' * 60}")
        observation, raw = search_knowledge_base(q)
        print(observation)
        print(f"\n--- raw: {len(raw)} chunks, ids: {[r.id for r in raw]} ---")

# Results:
# ============================================================
# QUERY: Reanimation Protocols
# ============================================================
# [chunk 17] FAQ / Q: Do rules that activate Reanimation Protocols (e.g. the Protocol of the Undying Legions Stratagem) only apply to a Bodyguard unit whose attached Leader unit is on the battlefield if one or more models from that Bodyguard unit are also still on the battlefield? (score 0.74)
# Q: Do rules that activate Reanimation Protocols (e.g. the Protocol of the Undying Legions Stratagem) only apply to a Bodyguard unit whose attached Leader unit is on the battlefield if one or more models from that Bodyguard unit are also still on the battlefield?
#
# A:
# Yes.
#
# [chunk 7] FAQ / Q: When using the Protocol of the Undying Legions Stratagem, are any other rules that are applicable to Reanimation Protocols applied (e.g. Necron Warriors’ Their Number is Legion ability)? (score 0.72)
# Q: When using the Protocol of the Undying Legions Stratagem, are any other rules that are applicable to Reanimation Protocols applied (e.g. Necron Warriors’ Their Number is Legion ability)?
#
# A:
# Yes.
#
# [chunk 99] Crusade Rules / Reanimation System (score 0.71)
# 2. RESURRECTION FLUX
# While a unit is Below Half-strength, add 1 to the result of that unit’s Reanimation Protocols roll.
#
# 3. ANASTASIC CONTINGENCY
# Once per battle, after an enemy unit has caused a unit from your Crusade army to go below its Starting Strength, that unit can use its Reanimation Protocols ability.
#
# REANIMATION MASTER SYSTEM ABILITY
# CONTRA-MORTIS PROTOCOL
# If you have access to this Master System ability, you can use it in one of the following ways:
#
# Once per battle, when a NECRONS u [...truncated]
#
# [chunk 21] Army Rules / Reanimation Protocols (score 0.71)
# Reanimation Protocols
#
# The Necron dynasties benefit from the nigh-on supernatural technologies that once saw them dominate the galaxy, perhaps the most unsettling of which are their reanimation protocols. Should a Necron be slain, its body becomes wreathed in an eerie glow. Crawling limbs reattach. Sundered torsos and smashed skulls reform amidst emerald sparks. Witch lights flare back to life within dead eye-lenses and the Necron rises again, shambling back into their battle line. Those Necrons [...truncated]
#
# --- raw: 4 chunks, ids: [17, 7, 99, 21] ---
#
# ============================================================
# QUERY: Awakened Dynasty Stratagems
# ============================================================
# [chunk 25] Awakened Dynasty / Stratagems (score 0.72)
# Stratagems
# PROTOCOL OF THE ETERNAL REVENANT
# 1CP
# Awakened Dynasty – Epic Deed Stratagem
# Necron rulers possess enhanced self-repair systems.
# WHEN: Any phase.
#
# TARGET: One NECRONS INFANTRY CHARACTER model from your army that was just destroyed. You can use this Stratagem on that model even though it was just destroyed.
#
# EFFECT: At the end of the phase, set your model back up on the battlefield as close as possible to where it was destroyed and not within Engagement Range of any enemy units, with ha [...truncated]
#
# [chunk 124] Crusade Rules / Crusade Badges (score 0.71)
# The ancient stasis-crypts and darkened cities of your tomb world actuate with increasing frequency. Your dynastic legions enlarge day by day, fresh phalanxes of metallic soldiery awoken to serve your ambitions. Pulses of esoteric energy surge through newly activated systems that empower greater campaigns of conquest. None can resist your inexorable rise, not savage hordes, nor youthful and naive empires, nor dishonourable thieves and assassins. All will cower in obeisance, or be cast into oblivi [...truncated]
#
# [chunk 125] Crusade Rules / Crusade Badges (score 0.7)
# Your dominion has moved far beyond the reclamation of lost power as your legions seize new worlds and entire planetary systems. Your nobles and Crypteks lead armies on unending campaigns of systematic conquest, eradication and enslavement, and your tomb world stands as a linchpin of the wider dynasty’s expansion. The stars themselves will be shackled to your will as you eclipse your dynastic rivals in an immortal reign of subjugation!
#
# You have used a Master System ability ten or more times.
# At [...truncated]
#
# [chunk 26] Awakened Dynasty / Stratagems (score 0.69)
# TARGET: One NECRONS unit from your army that had one or more of its models destroyed as a result of the attacking unit’s attacks.
#
# EFFECT: Your unit activates its Reanimation Protocols and reanimates D3 wounds (or D3+1 wounds if a NECRONS CHARACTER is leading your unit].
# PROTOCOL OF THE HUNGRY VOID
# 1CP
# Awakened Dynasty – Battle Tactic Stratagem
# Necrons strike with data-augmented accuracy.
# WHEN: Fight phase.
#
# TARGET: One NECRONS unit from your army that has not been selected to fight this phase. [...truncated]
#
# --- raw: 4 chunks, ids: [25, 124, 125, 26] ---
#
# ============================================================
# QUERY: necron healing recovery
# ============================================================
# [chunk 21] Army Rules / Reanimation Protocols (score 0.75)
# Reanimation Protocols
#
# The Necron dynasties benefit from the nigh-on supernatural technologies that once saw them dominate the galaxy, perhaps the most unsettling of which are their reanimation protocols. Should a Necron be slain, its body becomes wreathed in an eerie glow. Crawling limbs reattach. Sundered torsos and smashed skulls reform amidst emerald sparks. Witch lights flare back to life within dead eye-lenses and the Necron rises again, shambling back into their battle line. Those Necrons [...truncated]
#
# [chunk 31] Annihilation Legion / Enhancements (score 0.71)
# Enhancements
#
# Eternal Madness 25 pts
#
# This Necrons sanity suffered during the Great Sleep. Now they are driven by a wrathful zeal, one which has seeped through the carrier waves of their commandments and into their followers.
#
# NECRONS model only. In the Fight phase, each time a model in the bearer’s unit is destroyed, if that model has not fought this phase, roll one D6: on a 4+, do not remove the destroyed model from play; it can fight after the attacking models unit has finished making its att [...truncated]
#
# [chunk 111] Crusade Rules / Requisitions (score 0.71)
# Many afflicted with the Destroyer curse have awoken from the Great Sleep that way, yet more frightening is for the nihilistic madness to find purchase within the personality engrams of formerly stable Necrons. Their ambition and psyche atrophies until all that remains is the cold-hearted desire for annihilation.
# Purchase this Requisition when a NOBLE model would gain a third Battle Scar. Instead of gaining a third Battle Scar, that unit instead gains the DESTROYER CULT keyword and loses all of i [...truncated]
#
# [chunk 131] Boarding Actions / Detachment Rule (score 0.71)
# Detachment Rule
# Conquest Protocols
#
# The Necron commander seeks to regain lost ground from their upstart foe. Those who seek to prevent the dynasty from reclaiming that which is rightfully theirs are marked for immediate termination.
# Each time a NECRONS model from your army makes an attack, if that model is within range of an objective marker or the target of that attack is within range of an objective marker, on a Critical Wound, improve the Armour Penetration characteristic of that attack by 1. [...truncated]
#
# --- raw: 4 chunks, ids: [21, 31, 111, 131] ---
#
# ============================================================
# QUERY: space marines bolter
# ============================================================
# [chunk 60] Starshatter Arsenal / Enhancements (score 0.65)
# Enhancements
#
# Dread Majesty (Aura) 30 pts
#
# When this noble unleashes the might of their cosmic armoury, their followers are left in no doubt as to the importance of the battle at hand. If they do not strive to live up to the lethal effectiveness of the dynasty’s war engines, their Overlord’s wrath will be terrible.
#
# OVERLORD or CATACOMB COMMAND BARGE model only. While a friendly NECRONS unit (excluding MONSTER and TITANIC units) is within 6" of the bearer, each time a model in that unit makes an [...truncated]
#
# [chunk 3] Contents / Detachment Rule (score 0.64)
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
# Awakening Points Remaining
#
# Boarding Actions
#
# Tomb Ship Complement
#
# Mustering a Boarding Patrol
#
# Rules Adaptations
#
# Army Rule
# Transdimensional Reinforcement
#
# Detachment Rule
# Conquest Protocols
#
# Enhancements
#
# Stratagems
#
# Deranged Outcasts
#
# Army Rule
# Tra [...truncated]
#
# [chunk 114] Crusade Rules / Battle Traits (score 0.64)
# INFANTRY Units
# D6
# Excluding CHARACTER units
# THE WILL TO SERVE
#
# These combatants have developed a truly indomitable will, rapidly recovering from even the most catastrophic damage in their determination to serve their masters.
# Out of Action tests taken for this unit are automatically passed.
# ENGRAMMATIC IMPRINTING
#
# The soldiers in this unit are receptive to the desires and commands of their betters even at great distances.
# While this unit is within 6" of one or more CHARACTER models from your Cru [...truncated]
#
# [chunk 134] Boarding Actions / Army Rule (score 0.64)
# Army Rule
# Transdimensional Reinforcement
#
# Necron voidships possess dimensional translocators that allow Cryptek engineers to withdraw damaged assets from the field and replace them in short order.
# Units from your army with the Reanimation Protocols ability lose that ability. Such units, if they are not CHARACTER units, then gain this one.
#
# Once per battle, in your Command phase, this unit can request reinforcement. When it does, roll one D6 for each destroyed model in this unit: for each 5+, ret [...truncated]
#
# --- raw: 4 chunks, ids: [60, 3, 114, 134] ---