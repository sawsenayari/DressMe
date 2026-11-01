"""ÉVALUATION 1 — Agent agenda : exactitude sur un jeu étiqueté, ablation règles / LLM / LLM+RAG, intervalles de confiance.
python -m training.eval_agent [--n 20]   (étiquettes écrites à la main : subjectives ; plusieurs occasions acceptées quand c'est ambigu)"""
import argparse, asyncio
from collections import defaultdict
from app import agent
from app.agent import SYSTEM_PROMPT, parse_agenda
from .evalkit import fmt, save

# (texte, occasion(s) acceptée(s), formalité, langue)
GOLD = [("je présente mon PFE devant le jury demain", "formal", 3, "fr"), ("entretien d'embauche chez une banque", "formal", 3, "fr"),
 ("cours toute la journée à l'université", {"casual", "work"}, 1, "fr"), ("réunion d'équipe interne le matin", "work", 2, "fr"),
 ("rendez-vous chez le client à Lac 2 pour signer le contrat", {"work", "formal"}, 3, "fr"), ("ftour chez ma grand-mère", {"religious", "party"}, 2, "fr"),
 ("le jour de l'aïd on rend visite à la famille", "religious", 2, "fr"), ("henné de ma cousine samedi", "wedding", 3, "fr"),
 ("enterrement d'un proche de la famille", "formal", 3, "fr"), ("padel avec des collègues après le travail", "sport", 0, "fr"),
 ("séance de gym à 18h", "sport", 0, "fr"), ("premier rendez-vous au restaurant ce soir", {"party", "casual"}, 2, "fr"),
 ("soirée d'anniversaire d'un ami", "party", 2, "fr"), ("sortie à la plage avec les enfants", "casual", 1, "fr"),
 ("je rencontre les parents de ma copine pour la première fois", {"party", "casual", "formal"}, 2, "fr"), ("présentation du projet devant le directeur", {"formal", "work"}, 3, "fr"),
 ("journée de télétravail à la maison", "casual", 1, "fr"), ("match de basket avec l'équipe", "sport", 0, "fr"), ("invitée à la zaffa de ma voisine ce soir", "wedding", 3, "fr"),
 ("chez le médecin puis quelques courses", "casual", 1, "fr"), ("on va au cinéma avec des amis", {"casual", "party"}, 1, "fr"),
 ("dîner d'affaires avec un partenaire étranger", {"work", "formal"}, 3, "fr"), ("prière du vendredi puis déjeuner en famille", "religious", 2, "fr"),
 ("voyage en train jusqu'à Sfax", "casual", 1, "fr"),
 ("عندي مقابلة عمل غدوة", "formal", 3, "ar"), ("فرح صاحبي هذا الويكاند", "wedding", 3, "ar"), ("نمشي نلعب كورة مع صحابي", "sport", 0, "ar"),
 ("اجتماع مع الكليون الصباح", {"work", "formal"}, 3, "ar"), ("عيد الأضحى عند جدتي", "religious", 2, "ar"), ("نهار كامل في الكلية", {"casual", "work"}, 1, "ar"),
 ("عزاء في دار الجيران", "formal", 3, "ar"),
 ("job interview tomorrow at 9", "formal", 3, "en"), ("birthday party at a friend's place tonight", "party", 2, "en"), ("going to the gym then grocery shopping", "sport", 0, "en"),
 ("wedding of my colleague on Saturday", "wedding", 3, "en"), ("just staying home studying for exams", "casual", 1, "en"),
 ("reunion cliant demain a 9h", {"work", "formal"}, 3, "mixte"), ("soutnance pfe lundi", "formal", 3, "mixte"), ("ftour 3and sahbi", {"religious", "party"}, 2, "mixte")]

def clean(gold):
    leaks = [g for g in gold if g[0] in SYSTEM_PROMPT]   # un exemple du prompt ne peut pas servir de test
    if leaks: print("Phrases retirées (présentes dans le prompt) :", [g[0] for g in leaks])
    return [g for g in gold if g not in leaks]

async def run(mode, gold):
    kw = dict(rules=dict(use_llm=False), llm=dict(use_rag=False), rag=dict(use_rag=True))[mode]; rows = []
    for text, occ, form, lang in gold:
        r = await parse_agenda(text, **kw)
        rows.append(dict(text=text, lang=lang, pred=r["occasion"], ok=r["occasion"] in (occ if isinstance(occ, set) else {occ}),
                         err=abs(r["formality"] - form), llm=r["source"].startswith("llm")))
    return rows

def summarize(rows):
    n, k = len(rows), sum(r["ok"] for r in rows); L = [r for r in rows if r["llm"]]; by = defaultdict(list)
    for r in rows: by[r["lang"]].append(r["ok"])
    return {"occasion_accuracy": fmt(k, n), "formality_mae": round(sum(r["err"] for r in rows) / n, 3), "answered_by_llm": f"{len(L)}/{n}",
            "accuracy_on_llm_answered": fmt(sum(r["ok"] for r in L), len(L)) if L else None,
            "by_language": {l: fmt(sum(v), len(v)) for l, v in by.items()}, "errors": [f"{r['text']} -> {r['pred']}" for r in rows if not r["ok"]][:12]}

async def amain(n=None):
    agent._CACHE.clear(); gold = clean(GOLD)[:n] if n else clean(GOLD); out = {"n": len(gold)}
    for mode in ("rules", "llm", "rag"):
        out[mode] = summarize(await run(mode, gold)); print(mode, out[mode])
    save("agent", out); return out

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=0); a = ap.parse_args(argv)
    return asyncio.run(amain(a.n or None))

if __name__ == "__main__": main()
