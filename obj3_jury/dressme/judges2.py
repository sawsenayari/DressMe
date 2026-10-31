"""Juges v3 : prompt analytique, exemples (few-shot « leave-one-out »), juge VISUEL, boucle reprenable.

Idées de prompt engineering utilisées (toutes gratuites, aucune ne demande plus d'appels) :
1. Rubrique avec des ANCRES chiffrées par niveau (le modèle n'a plus à deviner où placer « à améliorer »).
2. La RAISON avant le niveau (« evidence first ») : meilleur que verdict puis justification.
3. Exemples de TES jugements dans le prompt (few-shot), choisis sans jamais inclure la tenue évaluée.
4. Le verdict final n'est plus imposé par le LLM (« pire critère ») : on garde niveaux par critère + verdict global
   du LLM, et l'agrégation se choisit/calibre ensuite (voir calibrate.py).
5. Prompt compact (≈ 600 tokens) : le quota gratuit Groq est de 200 000 tokens/jour et 8 000/minute.
6. Juge VISUEL : un modèle multimodal regarde la même planche que l'humain a vue (supprime les erreurs de Perception).
"""
import json
import os
import time
import unicodedata

import numpy as np

from .context import describe_context
from .llm2 import QuotaExhausted
from .schema import CRITERIA, VERDICTS

RUBRIC_V3 = """Tu es styliste. Tu juges UNE tenue pour UNE situation (météo + occasion).
Note chaque critère : 2 = convient, 1 = à améliorer (défaut mineur ou discutable), 0 = déconseillé (défaut net).
- couleurs : 0 = 4 couleurs vives ou association criarde (rouge+rose, orange+violet...) ; 1 = association risquée, 3 couleurs vives ou plusieurs motifs ; 2 = neutres, ou 1-2 couleurs harmonieuses.
- formalite : adéquation à l'OCCASION d'abord, puis cohérence entre les pièces. Attendu : sport = vêtements ET chaussures de sport ; décontracté = tout sauf très habillé ; travail = ni sport ni très décontracté ; soirée = habillé ou soigné ; cérémonie = habillé, aucune pièce très décontractée (sweat, doudoune, baskets). Décalage net = 0, léger = 1.
- meteo : chaleur adaptée à la température. Sous 10 °C une couche chaude est nécessaire ; entre 10 et 18 °C une couche de mi-saison ; au-dessus de 25 °C tenue très légère, ni manteau ni pull épais. Sous la pluie : chaussures fermées, une veste est utile. Écart net = 0, léger = 1.
- coherence : tenue complète (haut + bas, ou robe, + chaussures), sans doublon absurde (2 bas, 2 paires de chaussures, robe + pantalon).
Pour chaque critère, écris d'abord la raison (10 mots max), puis le niveau. « verdict » = ton jugement global honnête (pas forcément le pire critère)."""

LEGENDE = "Légende : f = formalité 1-5 (1 sport, 3 smart casual, 5 cérémonie) ; c = chaleur 1-5 (1 été, 5 grand froid)."

FORMAT_V3 = """Réponds UNIQUEMENT par ce JSON :
{"criteres": {"couleurs": {"raison": "...", "niveau": 0}, "formalite": {"raison": "...", "niveau": 0},
 "meteo": {"raison": "...", "niveau": 0}, "coherence": {"raison": "...", "niveau": 0}},
 "verdict": "convient" | "à améliorer" | "déconseillé"}"""


# ---------- lecture robuste des niveaux ----------
def _strip(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn").strip()


_VERDICT_KEYS = {_strip(v): i for i, v in enumerate(VERDICTS)}     # 'deconseille' -> 0, 'a ameliorer' -> 1, 'convient' -> 2


def parse_level(x):
    """0/1/2 depuis un entier, un flottant, « 2 » ou un nom de verdict (accents facultatifs) ; None sinon."""
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return max(0, min(2, int(round(float(x)))))
    s = _strip(x)
    if s in _VERDICT_KEYS:
        return _VERDICT_KEYS[s]
    try:
        return max(0, min(2, int(round(float(s)))))
    except ValueError:
        return None


def normalize_v3(raw, source):
    """Valide la sortie d'un juge. Contrairement à la v2, le verdict n'est PAS plafonné par le pire critère."""
    if not isinstance(raw, dict) or not isinstance(raw.get("criteres"), dict):
        raise ValueError("Jugement LLM invalide : champ « criteres » absent")
    crit = {}
    for k in CRITERIA:
        c = raw["criteres"].get(k)
        if not isinstance(c, dict):
            c = {"niveau": c}                           # tolère {"couleurs": 2}
        lvl = parse_level(c.get("niveau"))
        if lvl is None:
            raise ValueError(f"Critère manquant ou illisible : {k}")
        crit[k] = {"niveau": lvl, "raison": str(c.get("raison", ""))[:160]}
    return {"source": source, "criteres": crit, "niveau_min": min(c["niveau"] for c in crit.values()),
            "niveau_llm": parse_level(raw.get("verdict")), "modele": raw.get("_modele")}


# ---------- prompt texte ----------
def pieces_line(pieces):
    out = []
    for p in pieces:
        motif = f" {p['motif']}" if p.get("motif") not in (None, "uni") else ""
        out.append(f"{p.get('categorie', '?')} {p.get('type', '?')} {p.get('couleur', '')} "
                   f"f{p.get('formalite', '?')}/c{p.get('chaleur', '?')}{motif}")
    return "; ".join(out)


def select_shots(target_id, labeled, k=6, occasion=None):
    """k exemples étiquetés par l'humain, classes équilibrées autant que possible, même occasion en priorité.
    La tenue évaluée (target_id) est TOUJOURS exclue : sinon l'évaluation serait truquée (fuite d'étiquette)."""
    pool = [x for x in labeled if x["outfit_id"] != target_id and x.get("humain") is not None]
    by = {0: [], 1: [], 2: []}
    for x in pool:
        by[int(x["humain"])].append(x)
    for lvl in by:
        by[lvl].sort(key=lambda x: (x["contexte"].get("occasion") != occasion, x["outfit_id"]))
    picked, rnd = [], 0
    while len(picked) < min(k, len(pool)):
        added = False
        for lvl in (0, 1, 2):
            if rnd < len(by[lvl]) and len(picked) < k:
                picked.append(by[lvl][rnd])
                added = True
        if not added:
            break
        rnd += 1
    return picked


def shots_text(shots):
    if not shots:
        return ""
    lines = [f"- {describe_context(s['contexte'])} | {pieces_line(s['pieces'])} -> {VERDICTS[int(s['humain'])]}"
             for s in shots]
    return "Exemples de jugements de l'utilisateur (à imiter, sans les recopier) :\n" + "\n".join(lines) + "\n\n"


def prompt_text(pieces, context, shots=None):
    return (f"{RUBRIC_V3}\n{LEGENDE}\n\n{shots_text(shots)}"
            f"Situation : {describe_context(context)}\nTenue : {pieces_line(pieces)}\n\n{FORMAT_V3}")


def judge_text_v3(llm, pieces, context, shots=None):
    return normalize_v3(llm.json_call(prompt_text(pieces, context, shots)), "llm3")


# ---------- juge visuel ----------
def prompt_vision(context):
    return (f"{RUBRIC_V3}\n\nL'image montre, de gauche à droite, les pièces de la tenue (légende en haut : "
            f"numéro de tenue, météo, occasion). Juge ce que tu VOIS : vraies couleurs, matières, coupes.\n"
            f"Situation : {describe_context(context)}\n\n{FORMAT_V3}")


def judge_vision_v3(llm, image, context):
    """image : chemin ou PIL.Image de la planche (survey/planches/Txx.png)."""
    return normalize_v3(llm.json_call(prompt_vision(context), images=[image]), "vision3")


# ---------- boucle reprenable (quotas gratuits) ----------
def run_batch(items, call, log_path, key="outfit_id", pause=0.0, verbose=True, only_model=None):
    """Applique call(item) -> dict à chaque tenue ; un JSONL garde les résultats déjà obtenus.
    S'arrête proprement si le quota gratuit est épuisé : relancer la cellule plus tard reprend là où on s'est arrêté.
    only_model : n'accepte, dans le journal, que les réponses de CE modèle (les autres sont refaites) : évite de mélanger
    sans le voir les réponses d'un modèle de secours avec celles du modèle principal."""
    done = {}
    if os.path.exists(log_path):
        for line in open(log_path, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                if "res" in r and (only_model is None or r["res"].get("modele") == only_model):
                    done[r[key]] = r["res"]             # les lignes « erreur » seront retentées
    todo = [it for it in items if it[key] not in done]
    if verbose:
        print(f"{len(done)} déjà faites, {len(todo)} à faire")
    for n, it in enumerate(todo, 1):
        try:
            res = call(it)
        except QuotaExhausted as e:
            print(f"⏸  Quota épuisé après {n - 1} nouvelles tenues : {e}\n"
                  f"   Relance la cellule plus tard (ou demain) : la reprise est automatique.")
            break
        except Exception as e:
            print(f"⚠️  {it[key]} : {str(e)[:120]} (sera retentée)")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({key: it[key], "erreur": str(e)[:300]}, ensure_ascii=False) + "\n")
            continue
        done[it[key]] = res
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({key: it[key], "res": res}, ensure_ascii=False) + "\n")
        if pause:
            time.sleep(pause)
    return done


# ---------- passage résultats -> matrices de niveaux ----------
def levels_matrix(results, ids):
    """N x 4 niveaux par critère (ordre CRITERIA) ; NaN si la tenue n'a pas (encore) de résultat."""
    X = np.full((len(ids), len(CRITERIA)), np.nan)
    for i, oid in enumerate(ids):
        r = results.get(oid)
        if r:
            X[i] = [r["criteres"][c]["niveau"] for c in CRITERIA]
    return X


def holistic_levels(results, ids):
    """Verdict global donné par le LLM (repli : pire critère si absent)."""
    out = np.full(len(ids), np.nan)
    for i, oid in enumerate(ids):
        r = results.get(oid)
        if r:
            out[i] = r["niveau_llm"] if r.get("niveau_llm") is not None else r["niveau_min"]
    return out


def rules_results(outfits):
    """Résultats du juge à règles au même format (gratuit, instantané)."""
    from .rules import judge_rules
    res = {}
    for o in outfits:
        j = judge_rules(o["pieces"], o["contexte"])
        res[o["outfit_id"]] = {"source": "regles", "criteres": {c: {"niveau": j["criteres"][c]["niveau"],
                               "raison": j["criteres"][c]["raison"]} for c in CRITERIA},
                               "niveau_min": j["niveau"], "niveau_llm": j["niveau"], "modele": None}
    return res
