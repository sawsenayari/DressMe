"""Service DressMe : le jury sans interface.

Pièces décrites -> juges (règles, LLM, hybride) -> arbitre -> réparateur.
Tout est appelable depuis n'importe quelle interface ou API :

    from dressme.service import DressMeService
    svc = DressMeService.from_folder("app_data")            # perception_clip.json + truth.json (+ shots.json)
    res = svc.judge(["TN_H_0001.jpg", "TN_H_0002.jpg", "TN_H_0003.jpg"], temperature=18, pluie=False, occasion="travail")
    print(res["verdict"], res["criteres"], res["reparations"])

Variables d'environnement (facultatives) : GEMINI_API_KEY, LLM_API_KEY, GEMINI_MODELS, MAX_LLM_PER_HOUR.
Sans clé : seules les règles tournent.
"""
import json
import os
import time
from collections import deque

from .arbiter import arbitrate
from .compat_bridge import CompatBridge
from .context import make_context
from .judges import judge_hybrid
from .judges2 import judge_text_v3, select_shots
from .repair import propose_repairs
from .rules import combine_levels, judge_rules
from .schema import CRITERIA, OCCASIONS, piece_label, verdict_name

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIECE_FIELDS = ("categorie", "type", "couleur", "formalite", "chaleur", "motif")


def build_llm(cache_dir=None):
    """Gemini d'abord, Groq en repli. Renvoie None si aucune clé (ou si le paquet openai manque)."""
    try:
        from .llm2 import GEMINI_URL, GROQ_URL, FallbackLLM, OpenAICompatClient2
    except Exception:
        return None
    clients = []
    gem = os.environ.get("GEMINI_API_KEY")
    if gem:
        for m in os.environ.get("GEMINI_MODELS", "gemini-3.5-flash-lite,gemini-3.1-flash").split(","):
            clients.append(OpenAICompatClient2(gem, m.strip(), GEMINI_URL, vision=False, cache_dir=cache_dir, name=m.strip()))
    groq = os.environ.get("LLM_API_KEY")
    if groq:
        for m in ("openai/gpt-oss-120b", "openai/gpt-oss-20b"):
            clients.append(OpenAICompatClient2(groq, m, GROQ_URL, vision=False, reasoning_effort="medium",
                                               tpm_limit=8000, cache_dir=cache_dir, name=m.split("/")[-1]))
    return FallbackLLM(clients) if clients else None


class DressMeService:
    def __init__(self, pieces, genders=None, shots=None, llm=None, max_llm_per_hour=None, compat=None):
        """pieces : {id: {"categorie", "type", "couleur", "formalite", "chaleur", "motif"}}
        genders : {id: "Ladieswear" | "Menswear" | "Divided"} (limite les corrections au même genre ; facultatif)
        shots   : tenues annotées par un humain, exemples du prompt LLM (facultatif)
        llm     : client LLM, ou None (règles seules)."""
        self.pieces = {i: {"id": i, **{k: p[k] for k in PIECE_FIELDS}} for i, p in pieces.items()}
        self.genders, self.shots, self.llm = genders or {}, shots or [], llm
        self.max_llm = int(max_llm_per_hour or os.environ.get("MAX_LLM_PER_HOUR", "40"))
        self._calls = deque()
        self.compat = compat   # CompatBridge (objectif 2) ou None

    # ------------------------------------------------------------ construction
    @classmethod
    def from_folder(cls, root=None, llm="auto"):
        """Charge perception_clip.json + truth.json (+ shots.json) d'un dossier (défaut : APP_DATA ou ./app_data)."""
        root = root or os.environ.get("APP_DATA", os.path.join(HERE, "app_data"))

        def load(name, default=None):
            path = os.path.join(root, name)
            if not os.path.exists(path):
                if default is None:
                    raise FileNotFoundError(f"Fichier introuvable : {path}")
                return default
            with open(path, encoding="utf-8") as f:
                return json.load(f)

        perc, truth, shots = load("perception_clip.json"), load("truth.json"), load("shots.json", [])
        pieces = {fn: perc[fn] for fn in perc if fn in truth}
        genders = {fn: truth[fn].get("gender", "Divided") for fn in pieces}
        if llm == "auto":
            llm = build_llm(os.path.join(root, "llm_cache"))
        return cls(pieces, genders, shots, llm, compat=CompatBridge.from_folder(root))

    @classmethod
    def from_demo(cls, llm=None):
        """Garde-robe fictive du dépôt (data/demo_wardrobe.json), sans photo : pour tester."""
        with open(os.path.join(HERE, "data", "demo_wardrobe.json"), encoding="utf-8") as f:
            data = json.load(f)
        pieces = {p["id"] + ".jpg": p for p in data}
        return cls(pieces, {i: "Ladieswear" for i in pieces}, [], llm)

    # ------------------------------------------------------------ catalogue
    def list_pieces(self, categorie=None, gender=None):
        """Pièces disponibles, filtrables par catégorie (haut, bas, robe, veste, chaussures...) et par genre."""
        return [p for i, p in self.pieces.items()
                if (categorie is None or p["categorie"] == categorie)
                and (gender is None or self.genders.get(i, "Divided") == gender)]

    # ------------------------------------------------------------ budget LLM
    def _budget_ok(self, n=2):
        now = time.time()
        while self._calls and now - self._calls[0] > 3600:
            self._calls.popleft()
        if len(self._calls) + n > self.max_llm:
            return False
        self._calls.extend([now] * n)
        return True

    @staticmethod
    def _rederive(j, source):
        lvl = combine_levels([c["niveau"] for c in j["criteres"].values()])
        return {"source": source, "niveau": lvl, "verdict": verdict_name(lvl), "criteres": j["criteres"],
                "raisons": [f"{k} : {c['raison']}" for k, c in j["criteres"].items() if c["niveau"] < 2]
                or ["Tous les critères sont satisfaisants."]}

    def _compat(self, pieces, notes):
        if self.compat is None:
            return None
        try:
            return self.compat.score(pieces)
        except Exception as e:
            notes.append(f"Compatibilité Obj2 indisponible ({type(e).__name__}).")
            return None

    # ------------------------------------------------------------ jugement
    def judge(self, piece_ids, temperature, pluie=False, occasion="décontracté", mode="complet", repair=True):
        """mode : "complet" (règles + LLM + hybride si un LLM est disponible) ou "regles" (règles seules).
        Lève ValueError si la liste est vide, si un id est inconnu ou si l'occasion n'existe pas."""
        ids = list(piece_ids or [])
        if not ids:
            raise ValueError("Aucune pièce sélectionnée.")
        unknown = [i for i in ids if i not in self.pieces]
        if unknown:
            raise ValueError("Pièce(s) inconnue(s) : " + ", ".join(unknown))
        ctx = make_context(float(temperature), bool(pluie), occasion)   # ValueError si occasion inconnue
        pieces = [self.pieces[i] for i in ids]

        rules = judge_rules(pieces, ctx)
        judges, notes = {"regles": rules}, []
        if mode == "complet":
            if self.llm is None:
                notes.append("Aucune clé LLM configurée : verdict basé sur les règles seules.")
            elif not self._budget_ok():
                notes.append("Plafond d'appels LLM atteint pour cette heure : verdict basé sur les règles seules.")
            else:
                try:
                    shots = select_shots("__service__", self.shots, k=6, occasion=occasion)
                    judges["llm"] = self._rederive(judge_text_v3(self.llm, pieces, ctx, shots), "llm")
                except Exception as e:
                    notes.append(f"Juge LLM indisponible ({type(e).__name__}).")
                try:
                    judges["hybride"] = self._rederive(judge_hybrid(self.llm, pieces, ctx, rules), "hybride")
                except Exception as e:
                    notes.append(f"Juge hybride indisponible ({type(e).__name__}).")
        final = arbitrate({k: judges.get(k) for k in ("regles", "llm", "hybride")})

        reps = []
        if repair and final["niveau"] < 2:
            gender = self.genders.get(ids[0], "Divided")
            pool = [p for i, p in self.pieces.items() if self.genders.get(i, "Divided") == gender]
            for r in propose_repairs(pieces, ctx, pool, top=3):
                reps.append({"action": r["action"],
                             "retirer": (r["piece_retiree"] or {}).get("id"),
                             "ajouter": (r["piece_ajoutee"] or {}).get("id"),
                             "explication": r["explication"]})
        return {
            "tenue": [{"id": p["id"], "description": piece_label(p)} for p in pieces],
            "contexte": ctx,
            "verdict": final["verdict"], "niveau": final["niveau"],
            "criteres": {c: {"niveau": final["criteres"][c]["niveau"], "raison": final["criteres"][c]["raison"],
                             "par_juge": {k: j["criteres"][c]["niveau"] for k, j in judges.items()}}
                         for c in CRITERIA},
            "votes": {k: j["verdict"] for k, j in judges.items()},
            "desaccord": final["desaccord"], "juges_dissidents": final["juges_dissidents"],
            "raisons": final["raisons"], "reparations": reps, "notes": notes,
            "mode_utilise": "complet" if len(judges) > 1 else "regles",
            "compatibilite": self._compat(pieces, notes),
        }
