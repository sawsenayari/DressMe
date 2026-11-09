"""Orchestration de la styliste IA : faits -> prompt versionné -> LLM -> parsing (+ réparation) -> garde-fous -> trace.

Le score vient du modèle PairMLP (Obj2) ; ce module ne fait qu'expliquer. Le client LLM est injecté, ce qui permet
de tester toute la chaîne sans clé ni réseau.
"""
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import StylistConfig
from .guard import clean_name, ground
from .llm import image_url
from .prompts import PROMPTS
from .schema import Advice

CAT_FR = {"tops": "haut", "bottoms": "bas", "all-body": "robe / combinaison", "outerwear": "veste / manteau",
          "shoes": "chaussures", "bags": "sac", "accessories": "accessoire", "jewellery": "bijou", "hats": "chapeau",
          "scarves": "écharpe", "sunglasses": "lunettes de soleil"}


@dataclass
class AdviceResult:
    advice: Optional[Advice]
    note: Optional[str] = None                  # message à l'utilisateur quand il n'y a pas de conseil
    trace: dict = field(default_factory=dict)


def build_facts(res, by_id, name_of):
    """Faits transmis au LLM : uniquement des valeurs calculées par l'Obj2 et des fiches de garde-robe nettoyées.
    `res` = sortie de /compatibility/score ; `name_of(fiche)` = nom lisible d'une pièce."""
    suspects = []

    def piece(x):
        c = by_id.get(x["id"], {})
        fallback = CAT_FR.get(c.get("category") or "", c.get("type") or "pièce")
        name, bad = clean_name(name_of(c) if c else x["id"], fallback)
        if bad:
            suspects.append(x["id"])
        return {"id": x["id"], "nom": name, "couleurs": (c.get("colour") or [])[:2],
                "accord_pct": round(100 * x["pair_score01"])}

    dup = res.get("duplicate") or {}
    facts = {"type_de_piece": CAT_FR.get(res["category"], res["category"]), "verdict": res["verdict"],
             "score_sur_100": res["score"], "nouvelles_tenues": res["newOutfits"],
             "va_bien": [piece(x) for x in res["pairs"] if x["verdict"] == "va bien"][:6],
             "a_eviter": [piece(x) for x in res["clashing"]][:3],
             "doublon": bool(dup.get("is_duplicate")),
             "piece_semblable": piece({"id": dup["id"], "pair_score01": dup.get("similarity", 0)})
             if dup.get("is_duplicate") else None}
    return facts, suspects


class StylistAdvisor:
    def __init__(self, cfg: StylistConfig = None, client=None, api_key=None):
        self.cfg = cfg or StylistConfig()
        if client is None:
            from .llm import GeminiVision
            client = GeminiVision(api_key, self.cfg)
        self.client = client
        self.prompt = PROMPTS[self.cfg.prompt_version]

    def messages(self, image, facts):
        user = self.prompt.render(json.dumps(facts, ensure_ascii=False, indent=1))
        return [{"role": "system", "content": self.prompt.system},
                {"role": "user", "content": [{"type": "text", "text": user},
                                             {"type": "image_url",
                                              "image_url": {"url": image_url(image, self.cfg.image_max_side)}}]}]

    def advise(self, image, facts, suspects=()):
        msgs = self.messages(image, facts)
        trace = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "prompt_version": self.prompt.version,
                 "temperature": self.cfg.temperature, "verdict": facts["verdict"], "suspect_names": list(suspects),
                 "attempts": 0, "latency_ms": 0, "prompt_tokens": 0, "completion_tokens": 0}
        adv, report = None, {}
        for attempt in range(1 + self.cfg.repair_attempts):
            trace["attempts"] = attempt + 1
            try:
                r = self.client.chat(msgs)
            except Exception as e:   # quota, réseau : pas de conseil, le score reste affiché
                trace["error"] = f"{type(e).__name__}: {str(e)[:300]}"
                self._log(trace)
                return AdviceResult(None, "Conseil de l'IA momentanément indisponible.", trace)
            trace["model"] = r.model
            trace["raw"] = r.text[:1500]          # sortie brute, avant garde-fous (audit et évaluation)
            trace["latency_ms"] += r.latency_ms
            trace["prompt_tokens"] += r.prompt_tokens
            trace["completion_tokens"] += r.completion_tokens
            try:
                raw = json.loads(r.text)
            except json.JSONDecodeError as e:
                report = {"schema_ok": False, "schema_error": f"JSON invalide : {e.msg}"}
            else:
                adv, report = ground(raw, facts, self.cfg.max_words)
                if adv is not None:
                    break
            # réparation : on renvoie au modèle sa réponse et l'erreur précise, une seule fois
            msgs = msgs + [{"role": "assistant", "content": r.text},
                           {"role": "user", "content": "Ta réponse n'est pas exploitable ("
                            + report.get("schema_error", "conseil vide ou contraire aux faits")
                            + "). Renvoie uniquement le JSON demandé, en respectant les contraintes."}]
        trace.update({k: v for k, v in report.items()})
        trace["ok"] = adv is not None
        self._log(trace)
        if adv is None:
            return AdviceResult(None, "L'IA n'a pas donné de conseil exploitable.", trace)
        return AdviceResult(adv, None, trace)

    def _log(self, trace):
        """Trace JSONL d'observabilité : version du prompt, modèle, latence, jetons, corrections (ni photo ni clé)."""
        if self.cfg.trace_path:
            p = Path(self.cfg.trace_path); p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as f:
                f.write(json.dumps(trace, ensure_ascii=False) + "\n")
