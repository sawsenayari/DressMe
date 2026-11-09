"""Styliste IA de l'Obj2 : couche LLM qui EXPLIQUE le score de compatibilité sans jamais le calculer.

Organisation (une responsabilité par fichier) :
    config.py   hyperparamètres de génération et choix du modèle (surchargeables par variables d'environnement)
    prompts.py  registre des prompts versionnés (v1 gelée, v2 en production) + journal des changements
    schema.py   contrat de sortie (Pydantic) : ce que le LLM a le droit de renvoyer
    guard.py    garde-fous : nettoyage des entrées (injection), ancrage de la sortie sur les faits
    llm.py      client Gemini (API compatible OpenAI) : mode JSON, repli de modèle, mesure latence / jetons
    advisor.py  orchestration : faits -> prompt -> LLM -> parsing -> validation -> trace
    evaluate.py banc d'évaluation hors ligne des versions de prompt sur eval_cases.json
"""
from .advisor import StylistAdvisor, AdviceResult
from .config import StylistConfig
from .prompts import PROMPTS, DEFAULT_VERSION

__all__ = ["StylistAdvisor", "AdviceResult", "StylistConfig", "PROMPTS", "DEFAULT_VERSION"]
