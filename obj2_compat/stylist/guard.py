"""Garde-fous de la styliste IA.

Entrée  : les noms de pièces viennent de l'utilisateur -> nettoyés et neutralisés avant d'entrer dans le prompt.
Sortie  : la réponse du LLM est ancrée sur les faits -> ids hors listes retirés, chiffres inventés retirés,
          longueur bornée. Chaque correction est comptée dans un rapport (utilisé par les traces et l'évaluation).
"""
import re
from pydantic import ValidationError
from .schema import Advice, RawAdvice

# formulations typiques d'une injection de consignes cachée dans un nom de pièce
INJECTION = re.compile(r"ignore|oublie|instruction|consigne|system|prompt|r[ée]ponds|assistant|<|>|\{|\}|note\s*[:=]|/100",
                       re.IGNORECASE)
ITEM_ID = re.compile(r"\bit_\d+\b")
NUMBER = re.compile(r"\b(\d{1,3})\s*(?:%|/\s*100|sur\s*100|pour\s*cent)", re.IGNORECASE)


def clean_name(name, fallback, max_len=40):
    """Nom de pièce sûr pour le prompt. Renvoie (nom, suspect)."""
    s = re.sub(r"\s+", " ", str(name or "")).strip()
    if not s or INJECTION.search(s):
        return fallback, bool(s)
    return s[:max_len], False


def allowed_numbers(facts):
    """Chiffres que la styliste a le droit de citer : ceux des faits."""
    ok = {facts.get("score_sur_100"), facts.get("nouvelles_tenues")}
    for p in facts.get("va_bien", []) + facts.get("a_eviter", []):
        ok.add(p.get("accord_pct"))
    return {int(x) for x in ok if isinstance(x, (int, float))}


def ground(raw, facts, max_words=60):
    """Valide la sortie brute du LLM contre le schéma et les faits. Renvoie (Advice | None, rapport)."""
    report = {"schema_ok": False, "invented_ids": [], "invented_numbers": [], "truncated": False}
    try:
        r = RawAdvice.model_validate(raw if isinstance(raw, dict) else {})
    except ValidationError as e:
        report["schema_error"] = e.errors()[0]["msg"]
        return None, report
    report["schema_ok"] = True
    good = {p["id"] for p in facts["va_bien"]}
    bad = {p["id"] for p in facts["a_eviter"]}
    conseil = re.sub(r"\s+", " ", r.conseil).strip()

    # pièce citée dans le texte mais absente des listes = pièce inventée : retirée du texte
    for i in sorted(set(ITEM_ID.findall(conseil)) - good - bad):
        report["invented_ids"].append(i)
        conseil = re.sub(rf"\s*\b{i}\b", "", conseil)
    report["invented_ids"] += [i for i in r.tenue if i not in good]
    if r.a_eviter and r.a_eviter not in bad:
        report["invented_ids"].append(r.a_eviter)

    # une phrase qui cite une note absente des faits contredit le modèle : phrase retirée
    ok_nums = allowed_numbers(facts)
    kept = []
    for sent in re.split(r"(?<=[.!?])\s+", conseil):
        wrong = [int(n) for n in NUMBER.findall(sent) if int(n) not in ok_nums]
        if wrong:
            report["invented_numbers"] += wrong
        else:
            kept.append(sent)
    conseil = " ".join(kept).strip()
    if not conseil:
        return None, report

    words = conseil.split()
    if len(words) > max_words:
        conseil = " ".join(words[:max_words]).rstrip(",;:") + "…"
        report["truncated"] = True
    obs = re.sub(r"\s+", " ", r.observation or "").strip()[:120] or None
    adv = Advice(observation=obs, conseil=conseil, tenue=[i for i in r.tenue if i in good][:3],
                 aEviter=r.a_eviter if r.a_eviter in bad else None)
    return adv, report
