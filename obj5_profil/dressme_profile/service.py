"""Point d'entrée unique pour l'intégration (API, CLI ou import Python)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import config
from .clustering import StyleModel, train
from .contracts import ItemCard, ProfileRequest, RecommendRequest, RecommendResponse, StyleProfile
from .features import fashionclip_coverage
from .profile import build_profile
from .recommend import recommend


def load_items(path: Path) -> List[ItemCard]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):            # accepte {"items": [...]}
        data = data.get("items", [])
    return [ItemCard.model_validate(d) for d in data]


def choose_space(catalog: Sequence[ItemCard], assets_dir: Optional[Path] = None) -> str:
    """FashionCLIP si ≥ 90 % des fiches ont leur .npy, sinon repli sur les attributs."""
    return "fashionclip" if fashionclip_coverage(catalog, assets_dir) >= 0.9 else "attributes"


class ProfileService:
    def __init__(self, catalog_path: Path = config.CATALOG_PATH,
                 model_path: Path = config.MODEL_PATH,
                 assets_dir: Path = config.ASSETS_DIR, retrain: bool = False):
        self.assets_dir = Path(assets_dir)
        self.catalog: List[ItemCard] = load_items(catalog_path)
        self.by_id: Dict[str, ItemCard] = {i.id: i for i in self.catalog}
        space = choose_space(self.catalog, self.assets_dir)
        model_path = Path(model_path)
        model = None
        if model_path.exists() and not retrain:
            try:
                model = StyleModel.load(model_path)
            except Exception as e:        # ex. version de scikit-learn différente
                print(f"[obj5] modèle illisible ({type(e).__name__}), réentraînement.", file=sys.stderr)
                model = None
            if model is not None and model.space != space:      # les .npy sont arrivés (ou ont disparu) : on réentraîne
                model = None
        if model is None:
            model = train(self.catalog, space=space, assets_dir=self.assets_dir)
            model.save(model_path)
        self.model = model

    # -- helpers ---------------------------------------------------------------
    def resolve(self, ids: Sequence[str]) -> List[ItemCard]:
        unknown = [i for i in ids if i not in self.by_id]
        if unknown:
            raise KeyError(f"Identifiants inconnus du catalogue : {', '.join(unknown[:10])}")
        return [self.by_id[i] for i in ids]

    # -- API métier ---------------------------------------------------------------
    def profile(self, req: ProfileRequest) -> StyleProfile:
        if req.items:
            items = list(req.items)
        elif req.item_ids:
            items = self.resolve(req.item_ids)
        else:
            raise ValueError("Fournir 'items' (fiches) ou 'item_ids'.")
        return build_profile(items, self.model, req.user_id, self.assets_dir)

    def recommend(self, req: RecommendRequest) -> RecommendResponse:
        wardrobe = self.resolve(req.wardrobe_ids)
        prof = build_profile(wardrobe, self.model, req.user_id, self.assets_dir)
        cands = self.resolve(req.candidate_ids) if req.candidate_ids else self.catalog
        recs = recommend(prof, wardrobe, cands, self.model, req.k, req.slot, self.assets_dir)
        return RecommendResponse(profile=prof, items=recs)
