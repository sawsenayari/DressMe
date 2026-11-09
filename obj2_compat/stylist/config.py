"""Hyperparamètres de la styliste IA, regroupés et justifiés au même endroit (lus à la création : surchargeables par
variables d'environnement sans toucher au code)."""
import os
from dataclasses import dataclass, field


def _env(name, default, cast=str):
    return field(default_factory=lambda: cast(os.environ.get(name, default)))


def _models():
    return [m.strip() for m in os.environ.get("GEMINI_VISION_MODELS", "gemini-3.5-flash-lite,gemini-3.5-flash").split(",")
            if m.strip()]


@dataclass(frozen=True)
class StylistConfig:
    # Modèles essayés dans l'ordre : flash-lite d'abord (rapide, quota gratuit plus large), flash en secours.
    models: list = field(default_factory=_models)
    base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    # Température basse : la tâche est une reformulation ancrée sur des faits, pas de la création libre.
    # 0,3 garde un ton naturel tout en limitant les écarts d'une exécution à l'autre.
    temperature: float = _env("STYLIST_TEMPERATURE", 0.3, float)
    top_p: float = 0.9
    # ~60 mots de conseil + observation + ids tiennent en ~250 jetons ; 400 laisse de la marge sans coût inutile.
    max_tokens: int = _env("STYLIST_MAX_TOKENS", 400, int)
    timeout_s: float = 20.0
    retries: int = 2                  # reprises réseau par modèle (géré par le client OpenAI)
    repair_attempts: int = 1          # JSON invalide ou conseil vide : une relance avec l'erreur précise
    image_max_side: int = 900         # photo réduite avant envoi : assez pour voir matière et couleur, moins de jetons
    prompt_version: str = _env("STYLIST_PROMPT_VERSION", "compat-conseil-v2")
    max_words: int = 60               # coupe dure côté code (le prompt demande 45)
    trace_path: str = _env("STYLIST_TRACE", "")   # fichier JSONL des appels (vide = pas de trace)
