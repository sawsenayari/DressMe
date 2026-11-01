"""Encodeur FashionCLIP.  RÈGLE D'OR : l'embedding écrit dans la fiche (.npy) vient d'un FashionCLIP GELÉ (identique à celui des
objectifs 2-6).  Si l'objectif 1 fait un fine-tuning, l'encodeur affiné ne sert QU'AU kNN/RAG interne (jamais à la fiche)."""
from __future__ import annotations
import copy, importlib, os
import numpy as np


class FashionClipEmbedder:
    def __init__(self, model_id: str | None = None, model=None, proc=None, device: str | None = None):
        import torch
        from transformers import CLIPModel, CLIPProcessor
        self.torch = torch; self.dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
        if model is None:
            self.proc = CLIPProcessor.from_pretrained(model_id); self.model = CLIPModel.from_pretrained(model_id).eval().to(self.dev)
        else: self.proc, self.model = proc, model

    def images(self, imgs, bs: int = 32) -> np.ndarray:
        torch = self.torch; out = []
        with torch.no_grad():
            for i in range(0, len(imgs), bs):
                inp = {k: v.to(self.dev) for k, v in self.proc(images=imgs[i:i + bs], return_tensors="pt").items()}
                f = self.model.get_image_features(**inp); f = f.pooler_output if hasattr(f, "pooler_output") else f
                out.append(torch.nn.functional.normalize(f, dim=-1).cpu().numpy())
        return np.vstack(out).astype("float32")

    def texts(self, prompts: list[str]) -> np.ndarray:
        """Vecteurs texte normalisés (sonde zéro-shot : FashionCLIP reconnaît-il une catégorie sans exemples ?)."""
        torch = self.torch
        with torch.no_grad():
            inp = {k: v.to(self.dev) for k, v in self.proc(text=prompts, return_tensors="pt", padding=True, truncation=True).items()}
            f = self.model.get_text_features(**inp); f = f.pooler_output if hasattr(f, "pooler_output") else f
        return torch.nn.functional.normalize(f, dim=-1).cpu().numpy().astype("float32")

    def clone(self) -> "FashionClipEmbedder":
        """Copie indépendante (pour le fine-tuning) : le modèle gelé de référence n'est jamais modifié."""
        return FashionClipEmbedder(model=copy.deepcopy(self.model), proc=self.proc, device=self.dev)


def load_shared_embed_hook(spec: str | None = None):
    """Branche le script commun de Suzana : DRESSME_SHARED_EMBED='package.module:function'.
    La fonction doit prendre une image PIL (le crop 512) et renvoyer un vecteur (512,) de norme 1. Sinon : None."""
    spec = spec or os.environ.get("DRESSME_SHARED_EMBED")
    if not spec: return None
    mod, fn = spec.split(":"); return getattr(importlib.import_module(mod), fn)
