"""Agent de décision : Qwen2.5-VL + garde-fous kNN/RAG.  Logique du notebook v1 conservée, avec 3 ajouts :
  * `mode` : full | llm_only | knn_only  (références simples exigées par l'évaluation commune) ;
  * `after_rag_policy` : "knn" (v1) ou "llm" (ablation : la route knn_after_rag n'a fait que 53,8 % sur 13 images) ;
  * le vecteur de requête et la distribution du vote kNN sont renvoyés (confiance de la fiche)."""
from __future__ import annotations
import hashlib, time
import numpy as np
from .config import Config
from .imaging import img_key
from .parsing import parse_answer
from .prompts import prompt_v1, prompt_rag
from .retrieval import Retriever, knn_vote, consensus


def accuracy_ok(a, cfg): return a["valid"] and a["confidence"] >= cfg.conf_min


def hallucination(a, kv, nb, cfg):
    """Score H dans [0,1] : le LLM affirme-t-il des choses que les faits (vocabulaire, kNN, catalogue) contredisent ?"""
    flags, H = [], 0.0
    if not a["valid"]: return 1.0, ["invalid_output"]
    if a["issues"]: flags.append("out_of_vocabulary"); H += 0.25
    if kv["conf"] >= cfg.knn_min and kv["category"] != a["category"]: flags.append("contradicts_knn"); H += 0.60
    same = [n for n in nb if n["category"] == a["category"]] or nb
    for attr in ("color", "gender"):
        v, share = consensus(same, attr)
        if v and share >= cfg.attr_min and a[attr] not in ("unknown", v): flags.append(f"contradicts_neighbors_{attr}"); H += 0.20
    return min(H, 1.0), flags


def merge_attributes(a, nb, category, cfg):
    """season/occasion -> voisins d'abord (conventions du catalogue) ; color/gender -> LLM d'abord (visibles)."""
    same = [n for n in nb if n["category"] == category] or nb; out = {}
    for attr in ("color", "gender", "season", "occasion"):
        v, share = consensus(same, attr); x = a[attr] if a else "unknown"
        if attr in ("season", "occasion"): out[attr] = v if (v and share >= 0.5) else x
        else: out[attr] = x if (x != "unknown" and not (v and share >= cfg.attr_min and v != x)) else (v or x)
    return out


class RecognitionAgent:
    def __init__(self, llm, embedder, retriever: Retriever, cfg: Config, cache=None):
        self.llm, self.embedder, self.retriever, self.cfg, self.cache = llm, embedder, retriever, cfg, cache

    def _llm(self, image, prompt):
        key = hashlib.md5(prompt.encode()).hexdigest()[:10] + "|" + img_key(image)
        if self.cache is not None and key in self.cache: raw, lat = self.cache[key]["raw"], self.cache[key]["latency"]
        else:
            t = time.time()
            try: raw = self.llm.generate(image, prompt)
            except Exception as e:
                a = parse_answer(""); a["issues"] = ["llm_error: " + repr(e)[:80]]; return a
            lat = time.time() - t
            if self.cache is not None: self.cache.put(key, raw=raw, latency=lat)
        a = parse_answer(raw); a["latency"] = lat; return a

    def run(self, image, mode: str = "full", query_emb=None) -> dict:
        cfg = self.cfg; tr = []; t0 = time.time(); calls = 0
        q = query_emb if query_emb is not None else self.embedder.images([image])[0]
        nb = self.retriever.search(q, cfg.knn_k); kv = knn_vote(nb)
        tr.append(f"OUTIL knn_search        → {kv['category']} (sûr à {kv['conf']:.0%})")

        def done(cat, conf, source, ans, status="OK", H=0.0, flags=(), llm_attrs=True):
            r = dict(category=cat, confidence=float(conf), source=source, status=status, H=float(H), flags=list(flags), llm_calls=calls,
                     latency_s=time.time() - t0, trace=tr, first=first, neighbors=nb, knn=kv, query_emb=q, llm_conf=(ans or {}).get("confidence", 0.0),
                     evidence=(ans or {}).get("evidence", ""), candidate=(ans or {}).get("category"))
            use = ans if (llm_attrs and ans and ans["valid"]) else None
            r.update(merge_attributes(use, nb, cat if cat != "unknown" else kv["category"], cfg)); return r

        if mode == "knn_only":
            first = dict(valid=False, category="invalid", color="unknown", gender="unknown", issues=[])
            tr.append("MODE knn_only"); return done(kv["category"], kv["conf"], "knn_only", None, llm_attrs=False)

        a1 = self._llm(image, prompt_v1(cfg.tunisian_prompt)); calls += 1; H1, f1 = hallucination(a1, kv, nb, cfg); acc1 = accuracy_ok(a1, cfg)
        tr.append(f"OUTIL llm_analyze (v1)  → {a1['category']} conf={a1['confidence']:.2f} | précision_ok={acc1} | H={H1:.2f} {f1}")
        first = dict(valid=a1["valid"], category=a1["category"], color=a1["color"], gender=a1["gender"], issues=a1["issues"])

        if mode == "llm_only":
            tr.append("MODE llm_only")
            if a1["valid"]:
                r = done(a1["category"], a1["confidence"], "llm_only", a1, H=H1, flags=f1)
                for k in ("color", "gender", "season", "occasion"): r[k] = a1[k]         # pas de fusion avec les voisins
                return r
            return done("unknown", 0.0, "llm_only", a1, status="REVIEW", H=H1, flags=f1)

        if acc1 and H1 < cfg.h_high:                                           # niveau 0 : le LLM est fiable
            tr.append("DÉCISION : LLM fiable → réponse directe"); return done(a1["category"], a1["confidence"], "llm", a1, H=H1, flags=f1)
        if H1 < cfg.h_high:                                                    # niveau 1 : précision douteuse, pas d'hallucination avérée
            tr.append("précision douteuse → on interroge le kNN")
            if kv["conf"] >= cfg.knn_min:
                tr.append("DÉCISION : kNN sûr → réponse du kNN"); return done(kv["category"], kv["conf"], "knn_fallback", a1, H=H1, flags=f1)
            tr.append("kNN pas assez sûr → RAG")
        else: tr.append("hallucination élevée → RAG (voisins du catalogue injectés dans le prompt)")
        a2 = self._llm(image, prompt_rag(nb[:cfg.rag_k], a1, kv, f1, cfg.tunisian_prompt)); calls += 1; H2, f2 = hallucination(a2, kv, nb, cfg); acc2 = accuracy_ok(a2, cfg)
        tr.append(f"OUTIL llm_analyze (RAG) → {a2['category']} conf={a2['confidence']:.2f} | précision_ok={acc2} | H={H2:.2f} {f2}")
        if acc2 and H2 < cfg.h_high:
            tr.append("DÉCISION : réponse LLM + RAG validée"); return done(a2["category"], a2["confidence"], "llm+rag", a2, H=H2, flags=f2)
        if cfg.after_rag_policy == "llm" and acc2:
            tr.append("DÉCISION : LLM+RAG gardé malgré H élevé (policy=llm)"); return done(a2["category"], a2["confidence"], "llm+rag_flagged", a2, H=H2, flags=f2)
        if kv["conf"] >= cfg.knn_min:                                          # niveau 3 : arbitrage final
            tr.append("RAG insuffisant, kNN sûr → réponse du kNN"); return done(kv["category"], kv["conf"], "knn_after_rag", a2 if a2["valid"] else a1, H=H2, flags=f2)
        tr.append("DÉCISION : aucun avis fiable → REVIEW (revue humaine)")
        return done("unknown", 0.0, "review", a2 if a2["valid"] else a1, status="REVIEW", H=H2, flags=f2)
