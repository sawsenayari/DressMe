"""Faux module de reconnaissance (livrable « mock ») : renvoie des fiches VALIDES sans charger aucun modèle.
Déterministe (dépend du nom de fichier). Les autres objectifs l'utilisent pour tester leurs branchements."""
from __future__ import annotations
import hashlib
from pathlib import Path
import numpy as np
from contracts import RecognitionResult, ItemCard, Confidence, slot_of, default_type, warmth_formality

_POOL = [("jacket", "blue", "Casual"), ("jeans", "blue", "Casual"), ("tshirt", "white", "Casual"), ("dress", "black", "Party"),
         ("shoes", "black", "Casual"), ("shirt", "white", "Formal"), ("bag", "brown", "Casual"), ("skirt", "red", "Party"),
         ("coat", "grey", "Formal"), ("accessory", "black", "Casual")]


class MockRecognizer:
    def recognize(self, crop_path, item_id=None, raw_path=None, out_dir=None, mode=None) -> RecognitionResult:
        h = int(hashlib.md5(str(Path(crop_path).name).encode()).hexdigest(), 16); cat, col, usage = _POOL[h % len(_POOL)]
        item_id = item_id or f"it_{h % 10**6:06d}"; w, f, _ = warmth_formality(cat)
        emb_rel = f"emb/{item_id}.npy"
        if out_dir:
            rng = np.random.default_rng(h % 2**32); v = rng.normal(size=512).astype("float32"); v /= np.linalg.norm(v)
            (Path(out_dir) / "emb").mkdir(parents=True, exist_ok=True); np.save(Path(out_dir) / emb_rel, v)
        card = ItemCard(id=item_id, name=f"{col.title()} {cat}", slot=slot_of(cat), type=default_type(cat), colour=[col], usage=usage, warmth=w,
                        formality=f, gender="Unisex", image=f"items/{item_id}_raw.jpg", image_crop=f"items/{item_id}_crop.png", embedding=emb_rel,
                        confidence=Confidence(slot=0.9, colour=0.7, type=0.8), source="obj1.llm")
        return RecognitionResult(status="ok", card=card, category=cat, reasons=["MOCK"], trace=["mock"], debug={"mock": True})
