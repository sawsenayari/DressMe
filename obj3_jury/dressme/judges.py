"""Juges 2 et 3 : LLM seul, et hybride (LLM qui reçoit l'avis du juge à règles).
Le juge 1 (règles) est dans rules.py."""
import json

from .context import describe_context
from .rules import judge_rules
from .schema import CRITERIA, VERDICTS, piece_label, verdict_level, verdict_name

RUBRIC = """Critères (niveau 2 = convient, 1 = à améliorer, 0 = déconseillé) :
- couleurs : harmonie, pas trop de couleurs vives, motifs maîtrisés ;
- formalite : pièces homogènes entre elles ET adaptées à l'occasion ;
- meteo : chaleur des pièces adaptée à la température, pluie prise en compte ;
- coherence : tenue complète (haut, bas ou robe, chaussures), pas de doublon absurde."""

FORMAT = """Réponds UNIQUEMENT par un JSON :
{"criteres": {"couleurs": {"niveau": 0-2, "raison": "..."}, "formalite": {...},
 "meteo": {...}, "coherence": {...}},
 "verdict": "convient" | "à améliorer" | "déconseillé",
 "raisons": ["raison principale", "..."]}
Le verdict global ne peut pas être meilleur que le pire critère."""


def _outfit_text(pieces):
    return json.dumps([{k: v for k, v in p.items() if k != "id"} for p in pieces],
                      ensure_ascii=False, indent=1)


def normalize_judgment(raw, source):
    """Valide la sortie d'un juge LLM ; lève ValueError si inutilisable."""
    if not isinstance(raw, dict) or "criteres" not in raw:
        raise ValueError("Jugement LLM invalide")
    crit = {}
    for k in CRITERIA:
        c = raw["criteres"].get(k)
        if not isinstance(c, dict):
            raise ValueError(f"Critère manquant : {k}")
        crit[k] = {"niveau": max(0, min(2, int(c.get("niveau", 1)))), "raison": str(c.get("raison", ""))}
    floor = min(c["niveau"] for c in crit.values())
    lvl = verdict_level(raw.get("verdict"))
    level = floor if lvl is None else min(lvl, floor)
    raisons = raw.get("raisons") or [c["raison"] for c in crit.values() if c["niveau"] < 2]
    return {"source": source, "verdict": verdict_name(level), "niveau": level, "criteres": crit,
            "raisons": [str(r) for r in raisons] or ["Aucune réserve."]}


def judge_llm(llm, pieces, context):
    prompt = (f"Tu es un styliste expert. Évalue cette tenue.\n{RUBRIC}\n\n"
              f"Contexte : {describe_context(context)}\n"
              f"Tenue (pièces décrites) :\n{_outfit_text(pieces)}\n\n{FORMAT}")
    return normalize_judgment(llm.json_call(prompt), "llm")


def judge_hybrid(llm, pieces, context, rules_result=None):
    rules_result = rules_result or judge_rules(pieces, context)
    avis = {k: {"niveau": c["niveau"], "raison": c["raison"]} for k, c in rules_result["criteres"].items()}
    prompt = (f"Tu es un styliste expert. Un système à règles a déjà analysé la tenue ; "
              f"tu peux confirmer ou corriger son avis, mais seulement avec une raison précise.\n{RUBRIC}\n\n"
              f"Contexte : {describe_context(context)}\n"
              f"Tenue :\n{_outfit_text(pieces)}\n\n"
              f"Avis du système à règles : {json.dumps(avis, ensure_ascii=False)}\n\n{FORMAT}")
    return normalize_judgment(llm.json_call(prompt), "hybride")
