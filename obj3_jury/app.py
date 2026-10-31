"""DressMe : interface web (Gradio) du jury de tenues.

Photos -> descriptions (déjà calculées par CLIP) -> juges (règles, LLM, hybride) -> arbitre -> réparateur.
Lancement local :  python app.py        (ouvre http://127.0.0.1:7860)
Variables d'environnement (toutes facultatives) :
  APP_DATA          dossier de données (défaut : ./app_data ; sinon mode démo avec données fictives)
  GEMINI_API_KEY    clé Gemini gratuite  -> active le jury complet (règles + LLM + hybride)
  LLM_API_KEY       clé Groq gratuite    -> repli si Gemini est indisponible
  GEMINI_MODELS     modèles Gemini séparés par des virgules (défaut : gemini-3.5-flash-lite,gemini-3.1-flash)
  MAX_LLM_PER_HOUR  plafond d'appels LLM par heure pour toute l'application (défaut : 40)
"""
import json
import os
import sys
import time
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gradio as gr  # noqa: E402

from dressme.arbiter import arbitrate  # noqa: E402
from dressme.context import fetch_weather, make_context  # noqa: E402
from dressme.judges import judge_hybrid  # noqa: E402
from dressme.judges2 import judge_text_v3, select_shots  # noqa: E402
from dressme.repair import propose_repairs  # noqa: E402
from dressme.rules import combine_levels, judge_rules  # noqa: E402
from dressme.schema import CRITERIA, OCCASIONS, VERDICTS, piece_label, verdict_name  # noqa: E402

MAX_PIECES = 6
MAX_LLM_PER_HOUR = int(os.environ.get("MAX_LLM_PER_HOUR", "40"))
ICON = ["⛔", "⚠️", "✅"]
CRIT_NAMES = {"couleurs": "Couleurs", "formalite": "Formalité", "meteo": "Météo", "coherence": "Cohérence"}
GROUP_NAMES = {"Ladieswear": "Femme", "Menswear": "Homme", "Divided": "Mixte (Divided)"}
CAT_NAMES = {"haut": "Hauts", "bas": "Bas", "robe": "Robes", "veste": "Vestes",
             "chaussures": "Chaussures", "sac": "Sacs", "accessoire": "Accessoires"}
COLORS_RGB = {"black": (35, 35, 35), "white": (240, 240, 240), "grey": (140, 140, 140), "navy blue": (30, 40, 90),
              "blue": (50, 100, 200), "light blue": (140, 190, 235), "red": (200, 40, 40), "maroon": (110, 25, 40),
              "pink": (240, 150, 190), "orange": (240, 140, 30), "yellow": (240, 210, 50), "green": (50, 150, 70),
              "olive": (110, 120, 40), "teal": (30, 130, 130), "purple": (130, 60, 160), "brown": (120, 80, 50),
              "beige": (225, 205, 170), "cream": (245, 235, 210), "khaki": (170, 160, 100), "gold": (210, 170, 50),
              "silver": (190, 190, 200), "multi": (200, 120, 200)}


# ------------------------------------------------------------------ données
def _build_demo_data(dst):
    """Données fictives (tuiles de couleur) pour tester l'interface sans les vraies photos."""
    from PIL import Image, ImageDraw
    os.makedirs(os.path.join(dst, "wardrobe"), exist_ok=True)
    pieces = json.load(open(os.path.join(HERE, "data", "demo_wardrobe.json"), encoding="utf-8"))
    perc, truth = {}, {}
    for p in pieces:
        fn = p["id"] + ".jpg"
        img = Image.new("RGB", (240, 300), COLORS_RGB.get(p["couleur"].lower(), (180, 180, 180)))
        d = ImageDraw.Draw(img)
        d.text((12, 12), p["type"], fill=(255, 255, 255))
        d.text((12, 30), p["couleur"], fill=(255, 255, 255))
        img.save(os.path.join(dst, "wardrobe", fn), quality=85)
        perc[fn] = {k: p[k] for k in ("categorie", "type", "couleur", "formalite", "chaleur", "motif")}
        truth[fn] = {"articleType": p["type"], "categorie": p["categorie"], "gender": "Ladieswear"}
    for name, obj in (("perception_clip.json", perc), ("truth.json", truth), ("shots.json", [])):
        with open(os.path.join(dst, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)


def load_data():
    root, demo = os.environ.get("APP_DATA", os.path.join(HERE, "app_data")), False
    if not os.path.exists(os.path.join(root, "perception_clip.json")):
        root, demo = os.path.join(HERE, "app_data_demo"), True
        if not os.path.exists(os.path.join(root, "perception_clip.json")):
            _build_demo_data(root)
    def _load(name, default):
        path = os.path.join(root, name)
        if not os.path.exists(path):
            return default
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    perc, truth, shots = _load("perception_clip.json", {}), _load("truth.json", {}), _load("shots.json", [])
    desc = {fn: {"id": fn, **perc[fn]} for fn in perc
            if fn in truth and os.path.exists(os.path.join(root, "wardrobe", fn))}
    return root, demo, desc, truth, shots


ROOT, DEMO, DESC, TRUTH, SHOTS = load_data()
WARDROBE = os.path.join(ROOT, "wardrobe")


# ------------------------------------------------------------------ LLM (facultatif)
def build_llm():
    """Gemini d'abord, Groq en repli ; None si aucune clé (l'application marche alors avec les règles seules)."""
    from dressme.llm2 import GEMINI_URL, GROQ_URL, FallbackLLM, OpenAICompatClient2
    cache = os.path.join(ROOT, "llm_cache")
    clients = []
    gem = os.environ.get("GEMINI_API_KEY")
    if gem:
        for m in os.environ.get("GEMINI_MODELS", "gemini-3.5-flash-lite,gemini-3.1-flash").split(","):
            clients.append(OpenAICompatClient2(gem, m.strip(), GEMINI_URL, vision=False, cache_dir=cache, name=m.strip()))
    groq = os.environ.get("LLM_API_KEY")
    if groq:
        for m in ("openai/gpt-oss-120b", "openai/gpt-oss-20b"):
            clients.append(OpenAICompatClient2(groq, m, GROQ_URL, vision=False, reasoning_effort="medium",
                                               tpm_limit=8000, cache_dir=cache, name=m.split("/")[-1]))
    return FallbackLLM(clients) if clients else None


try:
    LLM = build_llm()
except Exception as e:  # ex. paquet openai absent : on continue sans LLM
    print("LLM désactivé :", type(e).__name__)
    LLM = None

_calls = deque()


def llm_budget_ok(n=2):
    """Plafond d'appels par heure pour protéger le quota gratuit."""
    now = time.time()
    while _calls and now - _calls[0] > 3600:
        _calls.popleft()
    if len(_calls) + n > MAX_LLM_PER_HOUR:
        return False
    _calls.extend([now] * n)
    return True


# ------------------------------------------------------------------ catalogue
def img(pid):
    return os.path.join(WARDROBE, pid)


def caption(pid):
    d = DESC[pid]
    return f"{d['type']} · {d['couleur']}"


def groups_available():
    keys = sorted({TRUTH[i].get("gender", "Divided") for i in DESC})
    return [(GROUP_NAMES.get(k, k), k) for k in keys]


def categories_available():
    cats = sorted({d["categorie"] for d in DESC.values()}, key=lambda c: list(CAT_NAMES).index(c) if c in CAT_NAMES else 99)
    return [("Toutes les catégories", "*")] + [(CAT_NAMES.get(c, c), c) for c in cats]


def catalogue(group, cat):
    ids = [i for i, d in DESC.items() if TRUTH[i].get("gender", "Divided") == group and (cat == "*" or d["categorie"] == cat)]
    ids.sort(key=lambda i: (list(CAT_NAMES).index(DESC[i]["categorie"]) if DESC[i]["categorie"] in CAT_NAMES else 99,
                            DESC[i]["type"], i))
    ids = ids[:240]
    return [(img(i), caption(i)) for i in ids], ids


def outfit_items(sel):
    return [(img(i), caption(i)) for i in sel]


# ------------------------------------------------------------------ interactions
def on_filter(group, cat):
    items, ids = catalogue(group, cat)
    return items, ids


def on_add(sel, visible, evt: gr.SelectData):
    sel = list(sel)
    if evt.index is None or evt.index >= len(visible):
        return sel, outfit_items(sel)
    pid = visible[evt.index]
    if pid in sel:
        gr.Info("Cette pièce est déjà dans la tenue.")
    elif len(sel) >= MAX_PIECES:
        gr.Warning(f"Une tenue contient au plus {MAX_PIECES} pièces.")
    else:
        sel.append(pid)
    return sel, outfit_items(sel)


def on_remove(sel, evt: gr.SelectData):
    sel = list(sel)
    if evt.index is not None and evt.index < len(sel):
        sel.pop(evt.index)
    return sel, outfit_items(sel)


def on_clear():
    return [], []


def on_weather():
    try:
        w = fetch_weather()
        gr.Info(f"Tunis : {w['temperature']:g} °C, {'pluie' if w['pluie'] else 'pas de pluie'}.")
        return round(w["temperature"]), bool(w["pluie"])
    except Exception:
        gr.Warning("Météo indisponible : règle la température à la main.")
        return gr.update(), gr.update()


def _rederive(j, source):
    """Même combinaison des critères pour tous les juges (politique de l'annotateur)."""
    lvl = combine_levels([c["niveau"] for c in j["criteres"].values()])
    return {"source": source, "niveau": lvl, "verdict": verdict_name(lvl), "criteres": j["criteres"],
            "raisons": [f"{k} : {c['raison']}" for k, c in j["criteres"].items() if c["niveau"] < 2]
            or ["Tous les critères sont satisfaisants."]}


def _cell(j, c):
    if not j:
        return "—"
    n = j["criteres"][c]["niveau"]
    return f"{ICON[n]} {VERDICTS[n]}"


def _card(verdict, level, note):
    colors = {2: "46,125,50", 1: "245,124,0", 0: "198,40,40"}[level]
    return (f"<div style='padding:16px 20px;border-radius:14px;border:2px solid rgb({colors});"
            f"background:rgba({colors},.12)'><div style='font-size:1.6em;font-weight:700'>"
            f"{ICON[level]} {verdict.capitalize()}</div><div style='margin-top:6px;opacity:.85'>{note}</div></div>")


def evaluate(sel, temperature, pluie, occasion, mode):
    empty = ("", [], "", "", [])
    if not sel:
        gr.Warning("Ajoute d'abord des pièces à la tenue.")
        return empty
    pieces = [DESC[i] for i in sel]
    ctx = make_context(float(temperature), bool(pluie), occasion)
    rules = judge_rules(pieces, ctx)
    judges, notes = {"regles": rules}, []
    if mode.startswith("Jury complet"):
        if LLM is None:
            notes.append("Aucune clé LLM configurée : verdict basé sur les règles seules.")
        elif not llm_budget_ok():
            notes.append("Plafond d'appels LLM atteint pour cette heure : verdict basé sur les règles seules.")
        else:
            try:
                shots = select_shots("__ui__", SHOTS, k=6, occasion=occasion)
                judges["llm"] = _rederive(judge_text_v3(LLM, pieces, ctx, shots), "llm")
            except Exception as e:
                notes.append(f"Juge LLM indisponible ({type(e).__name__}).")
            try:
                judges["hybride"] = _rederive(judge_hybrid(LLM, pieces, ctx, rules), "hybride")
            except Exception as e:
                notes.append(f"Juge hybride indisponible ({type(e).__name__}).")
    final = arbitrate({k: judges.get(k) for k in ("regles", "llm", "hybride")})

    votes = " · ".join(f"{name} : {ICON[j['niveau']]} {j['verdict']}" for name, j in
                       (("Règles", judges["regles"]), ("LLM", judges.get("llm")), ("Hybride", judges.get("hybride"))) if j)
    card_note = votes + ("<br><b>Les juges ne sont pas d'accord.</b>" if final["desaccord"] else "")
    rows = [[CRIT_NAMES[c], _cell(judges["regles"], c), _cell(judges.get("llm"), c), _cell(judges.get("hybride"), c),
             f"{ICON[final['criteres'][c]['niveau']]} {VERDICTS[final['criteres'][c]['niveau']]}",
             final["criteres"][c]["raison"] or "—"] for c in CRITERIA]
    details = "\n".join(f"- {r}" for r in final["raisons"]) if final["raisons"] else ""
    details = "**Raisons principales**\n" + details
    if notes:
        details += "\n\n" + "\n".join(f"*{n}*" for n in notes)

    rep_md, rep_items = "", []
    if final["niveau"] < 2:
        group = TRUTH[sel[0]].get("gender", "Divided")
        pool = [d for i, d in DESC.items() if TRUTH[i].get("gender", "Divided") == group]
        reps = propose_repairs(pieces, ctx, pool, top=3)
        if reps:
            rep_md = "**Correction minimale proposée** (une seule modification, vérifiée par les règles)\n" + "\n".join(
                f"{'→ ' if i == 0 else '- '}{r['explication']}" for i, r in enumerate(reps))
            best = reps[0]
            if best["piece_retiree"]:
                rep_items.append((img(best["piece_retiree"]["id"]), "À retirer : " + piece_label(best["piece_retiree"])))
            if best["piece_ajoutee"]:
                rep_items.append((img(best["piece_ajoutee"]["id"]), "À ajouter : " + piece_label(best["piece_ajoutee"])))
        else:
            rep_md = "Aucune correction d'une seule pièce n'améliore cette tenue : essaie de changer deux pièces."
    return _card(final["verdict"], final["niveau"], card_note), rows, details, rep_md, rep_items


# ------------------------------------------------------------------ pages d'information
ABOUT = """
### Comment ça marche
1. **Tu choisis des photos** (vraies photos du catalogue H&M) pour composer une tenue.
2. **Perception** : CLIP (modèle vision-langage, zero-shot) a décrit chaque photo : type, couleur, motif ; la formalité et la chaleur viennent d'une table par type.
3. **Contexte** : température, pluie, occasion.
4. **Trois juges** notent 4 critères (couleurs, formalité, météo, cohérence) de 0 à 2 : des **règles** écrites à la main, un **LLM** stylisé avec 6 exemples de jugements humains, et un juge **hybride** (LLM qui voit l'avis des règles).
5. **Arbitre** : médiane des trois verdicts, désaccords signalés.
6. **Réparateur** : propose de retirer, remplacer ou ajouter **une** pièce.

Sans clé LLM, seuls les règles tournent (gratuit, instantané).
"""

LIMITS = """
### Évaluation et limites (prototype)
Mesures faites contre les verdicts d'**un seul évaluateur humain**, sur 40 à 60 tenues :

| Élément | Résultat |
|---|---|
| Perception, catégorie (331 photos) | accuracy 0,86 |
| Perception, couleur (famille) | accuracy 0,61 |
| Juges sur 40 tenues | accuracy 0,55 à 0,60 (référence « toujours la classe la plus fréquente » : 0,475) |

- Aucun juge n'est **significativement** meilleur qu'un autre avec si peu de tenues.
- Environ **23 % des pièces** sont mal décrites par la perception (robes, noir lu comme bleu marine…).
- Les règles actuelles ont été écrites après avoir vu des erreurs : elles doivent encore être mesurées sur un jeu de test neuf.
- Catalogue H&M 2018-2020 : peu représentatif de la mode tunisienne actuelle.
- Ne traite pas ce verdict comme une vérité : c'est un avis de démonstration.
"""


# ------------------------------------------------------------------ interface
def build_ui():
    groups, cats = groups_available(), categories_available()
    default_group = groups[0][1]
    first_items, first_ids = catalogue(default_group, "*")
    has_llm = LLM is not None
    modes = ["Jury complet (règles + LLM + hybride)", "Règles seules (gratuit, instantané)"]

    with gr.Blocks(title="DressMe · jury de tenues") as demo:
        gr.Markdown("# 👗 DressMe — le jury de tenues\n"
                    "Compose une tenue avec de vraies photos, choisis la météo et l'occasion : trois juges et un arbitre "
                    "donnent un verdict, puis proposent une correction.")
        if DEMO:
            gr.Markdown("> ⚠️ **Mode démo** : données fictives (tuiles de couleur). Lance `prepare_app_data.py` pour utiliser tes vraies photos.")
        sel = gr.State([])
        visible = gr.State(first_ids)
        with gr.Tab("Composer et juger"):
            with gr.Row():
                with gr.Column(scale=5):
                    with gr.Row():
                        group = gr.Dropdown(groups, value=default_group, label="Garde-robe")
                        cat = gr.Dropdown(cats, value="*", label="Catégorie")
                    cat_gallery = gr.Gallery(first_items, label="Clique sur une photo pour l'ajouter", columns=5, height=480,
                                             allow_preview=False, object_fit="cover")
                with gr.Column(scale=4):
                    out_gallery = gr.Gallery([], label=f"Ma tenue (clique pour retirer, {MAX_PIECES} pièces max)", columns=3,
                                             height=230, allow_preview=False, object_fit="cover")
                    with gr.Row():
                        temp = gr.Slider(-5, 40, value=18, step=1, label="Température (°C)")
                        rain = gr.Checkbox(False, label="Il pleut")
                    with gr.Row():
                        occ = gr.Dropdown(list(OCCASIONS), value="décontracté", label="Occasion")
                        weather_btn = gr.Button("🌤️ Météo de Tunis", size="sm")
                    mode = gr.Radio(modes, value=modes[0] if has_llm else modes[1], label="Mode")
                    if not has_llm:
                        gr.Markdown("*Aucune clé LLM détectée : seul le mode « règles » donne un résultat complet.*")
                    with gr.Row():
                        go = gr.Button("⚖️ Faire juger la tenue", variant="primary")
                        clear = gr.Button("Vider")
            verdict = gr.HTML()
            table = gr.Dataframe(headers=["Critère", "Règles", "LLM", "Hybride", "Final (arbitre)", "Raison"],
                                 interactive=False, wrap=True, label="Détail par critère")
            details = gr.Markdown()
            rep_md = gr.Markdown()
            rep_gallery = gr.Gallery([], label="Correction proposée", columns=2, height=220, allow_preview=False, object_fit="cover")
        with gr.Tab("Comment ça marche"):
            gr.Markdown(ABOUT)
        with gr.Tab("Évaluation et limites"):
            gr.Markdown(LIMITS)

        group.change(on_filter, [group, cat], [cat_gallery, visible])
        cat.change(on_filter, [group, cat], [cat_gallery, visible])
        cat_gallery.select(on_add, [sel, visible], [sel, out_gallery])
        out_gallery.select(on_remove, [sel], [sel, out_gallery])
        clear.click(on_clear, None, [sel, out_gallery])
        weather_btn.click(on_weather, None, [temp, rain])
        go.click(evaluate, [sel, temp, rain, occ, mode], [verdict, table, details, rep_md, rep_gallery], api_name="juger")
    return demo


demo = build_ui()

if __name__ == "__main__":
    demo.queue(max_size=16).launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", "7860")))
