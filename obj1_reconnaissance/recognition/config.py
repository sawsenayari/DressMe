from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    # ---- chemins ----
    root: Path = field(default_factory=lambda: Path(os.environ.get("DRESSME_ROOT", "./dressme_data")))
    # ---- modèles ----
    llm_id: str = "Qwen/Qwen2.5-VL-7B-Instruct"
    llm_4bit: bool = True                      # False + Qwen2.5-VL-3B si le GPU est limité
    embedder_id: str = "patrickjohncyh/fashion-clip"   # FashionCLIP commun. A vérifier = même checkpoint que le script de Suzana
    max_new_tokens: int = 200
    # ---- politique de l'agent (valeurs de départ, à régler sur un jeu DEV, jamais sur le jeu réel final) ----
    conf_min: float = 0.70
    knn_k: int = 10
    rag_k: int = 5
    knn_min: float = 0.60
    attr_min: float = 0.70
    h_high: float = 0.50
    # "knn"  : après un RAG insuffisant, on retombe sur le kNN s'il est sûr (comportement du notebook v1)
    # "llm"  : on garde la réponse LLM+RAG si elle est valide et confiante (à comparer : la route knn_after_rag n'a fait que 53,8 %)
    after_rag_policy: str = "knn"
    # ---- base de connaissances ----
    kb_per_cat: int = 300
    n_test_per_cat: int = 8
    dup_sim: float = 0.97
    min_side: int = 384
    analyze_outfits: bool = False              # multi-articles : désactivé (le crop partagé fournit un article par image)
    # ---- intégration ItemCard ----
    crop_size: int = 512
    review_conf: float = 0.60                  # en dessous : l'appli doit demander une confirmation à l'utilisateur
    pixel_second_colour: bool = False          # couleur secondaire par pixels : expérimental, à valider sur les photos réelles
    crop_mode: str = "auto"                    # auto | worn | flat | none   (voir recognition/crop.py)
    seg_model_id: str = "mattmdjaga/segformer_b2_clothes"
    rembg_model: str = "u2net"                 # modèle rembg. (La version récente de rembg télécharge par défaut bria-rmbg-2.0, 1 Go : licence non commerciale à ma connaissance — à vérifier)
    crop_strategy: str = "outfit"              # outfit = une fiche par pièce détectée (filtrée) · main = UNE fiche par photo (la pièce la plus grande)
    crop_min_area_main: float = 0.03           # haut / bas / robe : part minimale de la photo (en dessous : fragment, ignoré)
    crop_min_area_small: float = 0.01          # chaussures / sac / accessoires
    crop_min_side: int = 96                    # côté minimal (px) de la boîte de la pièce ; en dessous : ignorée (inexploitable)
    crop_accessories: bool = True              # chapeau, écharpe, ceinture : False = ne pas les découper
    confirm_traditional: bool = True           # True : une pièce traditionnelle reste « needs_review » tant que son slot n'est pas validé avec Amir
    tn_refs: bool = True                       # ajoute les photos tunisiennes (split train) comme références kNN/RAG
    tunisian_prompt: bool = False              # ajoute au prompt la description des pièces tunisiennes (change les résultats : mesurer)
    subtype_min_share: float = 0.5             # part minimale des voisins pour annoncer un sous-type (jebba, farmla…)
    run_tag: str = "v1"
    seed: int = 42

    @property
    def out(self) -> Path:
        p = self.root / "agent_final"; p.mkdir(parents=True, exist_ok=True); return p


CFG = Config()
