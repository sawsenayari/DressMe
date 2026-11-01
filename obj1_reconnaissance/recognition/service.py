"""Service de reconnaissance (Objectif 1) : crop partagé  ->  ItemCard v1 + embedding .npy.

    svc = RecognitionService.from_config(CFG)                       # charge Qwen + FashionCLIP + base kNN (GPU)
    r = svc.recognize("crops/veste.png", item_id="it_0042", out_dir="/chemin/store")
    r.status, r.card, r.reasons
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np
from contracts import RecognitionResult
from .colour import dominant_colours
from .crop import Cropper
from .config import Config, CFG
from .imaging import load_image, normalise_crop, open_rgb, check_crop
from .itemcard_builder import build_card
from .outfit import judge_piece


class RecognitionService:
    def __init__(self, agent, shared_embedder, cfg: Config = CFG, shared_hook=None, mode: str = "full", cropper=None):
        self.agent, self.shared, self.cfg, self.hook, self.mode, self.cropper = agent, shared_embedder, cfg, shared_hook, mode, cropper

    # ---------- chargement complet (GPU) ----------
    @classmethod
    def from_config(cls, cfg: Config = CFG, mode: str = "full", use_finetuned: bool = False, load_llm: bool = True):
        from .agent import RecognitionAgent
        from .embedder import FashionClipEmbedder, load_shared_embed_hook
        from .knowledge_base import build_or_load
        from .llm import VisionLLM, JsonlCache
        from .retrieval import Retriever
        from .tunisian import add_tunisian_references
        shared = FashionClipEmbedder(cfg.embedder_id)                       # GELÉ : sert aux fiches ET (par défaut) au kNN
        cropper = Cropper.from_config(cfg)
        kb_df, E_kb, test_df, img_src = build_or_load(cfg, shared)
        retr_emb, tag = shared, "frozen"
        if use_finetuned:                                                    # l'encodeur affiné ne sert qu'au kNN interne
            from .finetune import load_finetuned_retrieval
            retr_emb, kb_df, E_kb, tag = load_finetuned_retrieval(cfg, shared, kb_df, img_src, cropper)
        retr_base = Retriever(E_kb, kb_df); retr_ref, n_tn = retr_base, 0
        if cfg.tn_refs:
            kb2, E2, n_tn = add_tunisian_references(cfg, retr_emb, kb_df, E_kb, cropper, tag)
            if n_tn: retr_ref = Retriever(E2, kb2)
        print(f"références kNN : {len(kb_df)} catalogue + {n_tn} tunisiennes (train)")
        # load_llm=False : PC sans GPU NVIDIA -> pas de Qwen ; kNN FashionCLIP seul (mode « knn_only », moins précis : voir README)
        llm = VisionLLM(cfg.llm_id, cfg.llm_4bit, cfg.max_new_tokens) if load_llm else None
        if not load_llm: mode = "knn_only"
        agent = RecognitionAgent(llm, retr_emb, retr_ref, cfg, JsonlCache(cfg.out / "llm_calls.jsonl"))
        svc = cls(agent, shared, cfg, load_shared_embed_hook(), mode)
        svc.test_df, svc.img_src, svc.kb_df, svc.cropper, svc.retr_base, svc.retr_ref, svc.n_tn_refs = test_df, img_src, kb_df, cropper, retr_base, retr_ref, n_tn
        return svc

    def enable_finetuned(self) -> bool:
        """Active l'encodeur FashionCLIP affiné (entraîné sur les photos tunisiennes `train`) POUR LE kNN INTERNE, sans recharger Qwen.
        Les fiches gardent l'embedding du FashionCLIP gelé.  Renvoie False si aucun entraînement n'a été possible (pas de photos train)."""
        from .finetune import load_finetuned_retrieval
        from .retrieval import Retriever
        from .tunisian import add_tunisian_references
        emb, kb, E, tag = load_finetuned_retrieval(self.cfg, self.shared, self.kb_df, self.img_src, self.cropper)
        if tag == "frozen": print("fine-tuning impossible : pas assez de photos tunisiennes `train` valides."); return False
        base = Retriever(E, kb); ref = base
        if self.cfg.tn_refs:
            kb2, E2, n = add_tunisian_references(self.cfg, emb, kb, E, self.cropper, tag)
            if n: ref = Retriever(E2, kb2)
        self.agent.embedder, self.agent.retriever, self.retr_base, self.retr_ref = emb, ref, base, ref
        print("encodeur affiné actif pour le kNN (", tag, ")"); return True

    # ---------- embedding commun ----------
    def embed_crop(self, crop_img) -> np.ndarray:
        v = np.asarray(self.hook(crop_img) if self.hook else self.shared.images([crop_img])[0], dtype="float32").reshape(-1)
        assert v.shape == (512,), f"embedding de forme {v.shape}, attendu (512,)"
        return v / (np.linalg.norm(v) + 1e-12)

    # ---------- reconnaissance ----------
    def recognize(self, crop_path, item_id: str | None = None, raw_path: str | None = None, out_dir: str | Path | None = None,
                  mode: str | None = None, crop_reasons: list | None = None, slot_hint: str | None = None) -> RecognitionResult:
        cfg = self.cfg; crop_path = Path(crop_path)
        item_id = item_id or "it_" + hashlib.md5(str(crop_path).encode()).hexdigest()[:8]
        quality = check_crop(crop_path); crop512 = normalise_crop(open_rgb(crop_path), cfg.crop_size)
        pixel = dominant_colours(crop512)
        shared_vec = self.embed_crop(crop512)
        same_enc = getattr(self.agent, "embedder", None) is self.shared and self.hook is None   # sinon : encodeurs différents
        res = self.agent.run(load_image(crop512, cfg.min_side), mode or self.mode, query_emb=shared_vec if same_enc else None)
        # chemins relatifs du contrat (items/… et emb/…), fichiers écrits si out_dir est fourni
        rel_crop, rel_emb = f"items/{item_id}_crop.png", f"emb/{item_id}.npy"; rel_raw = f"items/{item_id}_raw.jpg" if raw_path else rel_crop
        if out_dir:
            out_dir = Path(out_dir); (out_dir / "items").mkdir(parents=True, exist_ok=True); (out_dir / "emb").mkdir(parents=True, exist_ok=True)
            crop512.save(out_dir / rel_crop); np.save(out_dir / rel_emb, shared_vec)
            if raw_path: open_rgb(raw_path).save(out_dir / rel_raw, quality=95)
        card, status, reasons = build_card(item_id, res, image=rel_raw, image_crop=rel_crop, embedding=rel_emb, pixel_cols=pixel,
                                           crop_quality=quality, review_conf=cfg.review_conf, second_colour=cfg.pixel_second_colour, subtype_min_share=cfg.subtype_min_share, confirm_traditional=cfg.confirm_traditional)
        reasons = reasons + [f"crop:{r}" for r in (crop_reasons or []) if f"crop:{r}" not in reasons]
        fragment = False
        verdict = judge_piece(slot_hint, card.slot if card is not None else None)
        if verdict == "inconsistent":                                        # grande pièce dont le slot contredit la segmentation : à revoir
            reasons.append(f"slot_disagrees_with_segmentation:{slot_hint}->{card.slot}"); status = "needs_review" if status == "ok" else status
        elif verdict == "fragment":                                          # petite pièce reconnue comme autre chose : fragment d'un autre vêtement
            reasons.append(f"fragment_of_other_garment:{slot_hint}->{card.slot}"); fragment = True
        if crop_reasons and status == "ok": status = "needs_review"
        if card is not None and out_dir: (out_dir / "items" / f"{item_id}.json").write_text(card.model_dump_json(indent=2), encoding="utf-8")
        return RecognitionResult(status=status, card=card, category=res["category"], reasons=reasons, trace=res["trace"],
                                 debug=dict(source=res["source"], H=res["H"], flags=res["flags"], llm_calls=res["llm_calls"], latency_s=res["latency_s"],
                                            pixel_colours=pixel, crop_quality=quality, knn_dist=res["knn"]["dist"], colour_raw=res["color"],
                                            confidence_calibrated=False, fragment=fragment))
