# DressMe · Objectif 1 — service de reconnaissance (version d'intégration)

```
Photo de téléphone ─► crop partagé (Amir : SegFormer / rembg, carré 512 px, fond blanc)
                      └─► RecognitionService.recognize(image_crop)
                            ├─ FashionCLIP GELÉ ─► embedding 512-d, norme 1 ─► emb/<id>.npy        (même espace que les objectifs 2-6)
                            ├─ agent : Qwen2.5-VL ⇄ kNN / RAG (score H, repli, révision)           (cœur v1 conservé)
                            ├─ témoin de couleur par pixels (expérimental, nourrit la confiance)
                            └─ mapping 17 catégories → 7 slots ─► ItemCard v1 (JSON) + statut {ok, needs_review, unsupported}
```

## Arborescence
| Dossier | Rôle |
|---|---|
| `contracts/` | `ItemCard` v1 (Pydantic), table 17 catégories → 7 slots (+ sous-types tunisiens), schéma JSON, loader du dictionnaire d'Amir |
| `recognition/` | **crop** (SegFormer / rembg), prompts, parsing, kNN/RAG, **agent**, embedder, LLM, base catalogue, **jeu tunisien** (`tunisian.py`), fine-tuning, **builder ItemCard**, **service**, **batch** (photos → JSON), mock |
| `evaluation/` | métriques, évaluation catalogue, **évaluation tunisienne** (zéro-shot / kNN / agent, avec et sans références et prompt), 30 photos réelles |
| `tests/` | 30 tests sans GPU (faux modèles) |
| `notebooks/` | notebook autonome qui écrit tout le code dans Drive |

## Sorties JSON (dossier `store/`)
`items/it_XXXX.json` (une fiche ItemCard par pièce) · `emb/it_XXXX.npy` · `items/it_XXXX_crop.png` / `_raw.jpg` · `wardrobe.json` (liste de toutes les fiches, contrat pur) · `recognition_report.json` (statut, raisons, source, H par fiche).

## Données tunisiennes (voir `recognition/tunisian.py`)
`tunisian_dataset/images` + `labels.csv` (`category` obligatoire ; `subtype`, `colour`, `group_id`, `split`, `cropped` utiles). Split train/dev/test **par groupe**.
A) références kNN/RAG sans entraînement · B) description des pièces dans le prompt (`CFG.tunisian_prompt`, à valider avec quelqu'un qui connaît ces pièces) · C) fine-tuning d'une copie de FashionCLIP (train uniquement) · D) évaluation dev/test.

## Ce qui est conservé / corrigé / ajouté par rapport au notebook v1
**Conservé à l'identique** : prompts v1/v2, parsing, score H, politique à 4 niveaux, fusion des attributs, kNN, RAG, cache LLM, anti-fuite, mêmes échantillons (seeds 0/1).

**Corrigé**
1. *Fine-tuning* : le notebook modifiait **en place** le FashionCLIP qui sert aux embeddings → les vecteurs n'auraient plus été comparables à ceux des objectifs 2-6. Désormais l'encodeur affiné est une **copie** réservée au kNN interne ; la fiche utilise toujours l'encodeur gelé.
2. *Fine-tuning* : `autocast` fp16 sans `GradScaler` → ajouté.
3. *Base kNN* : conserve `article_type` (ex. `Jackets`) → le `type` fin de la fiche vient des voisins (même source que l'objectif 6). **`kb_meta.csv` ancien → reconstruit automatiquement une fois.**
4. *Image d'entrée* : un PNG transparent est composé sur fond blanc (le notebook convertissait en RGB et laissait du noir).
5. *Évaluation* : références simples exigées (`llm_only`, `knn_only`), IC 95 % Wilson + bootstrap, McNemar, table de calibration.

**Ajouté pour l'intégration** : contrat ItemCard validé par Pydantic, statuts, `apply_correction` (`source="user_corrected"`), contrôle qualité du crop, hook vers le script FashionCLIP de Suzana (`DRESSME_SHARED_EMBED`), loader du dictionnaire d'Amir (`DRESSME_TYPE_DICT`), mock.

## Ce que le notebook v1 montrait déjà (120 images de catalogue — pas des photos réelles)
Précision finale 0,917 [0,853 ; 0,954] ; LLM seul (1re passe) 0,833 ; **route `knn_after_rag` : 0,538 sur 13 images** (surtout blazer→jacket) ; couleur finale 0,725 ; genre 0,958. Fine-tuning **non exécuté** (pas de données tunisiennes). → `after_rag_policy="llm"` est proposé comme **ablation à mesurer**, pas comme amélioration prouvée.

## Points ouverts à valider avec l'équipe (aucune valeur inventée : tout est marqué dans `reasons`)
| Sujet | État dans le code | Avec qui |
|---|---|---|
| `traditional_garment` → slot | `onepiece` + `traditional=True`, **toujours `needs_review`** | Amir |
| `underwear` | `unsupported`, aucune fiche | Amir |
| `warmth`, `formality` | **placeholder neutre** tant que le dictionnaire d'Amir n'est pas chargé (`warmth_formality_placeholder`) | Amir |
| Noms de `type`, valeurs de `gender` (`Men/Women/Unisex`), `usage=home` → `Casual` | provisoires | Amir |
| `confidence.slot/colour/type` | **heuristiques non calibrées** (`debug.confidence_calibrated=False`) ; à calibrer sur les 30 photos | toi + Suzana |
| Checkpoint FashionCLIP | `patrickjohncyh/fashion-clip` (le PDF écrit `fashionclip`) : vérifier que c'est le même que le script commun | Suzana |
| Couleur secondaire par pixels | désactivée (`pixel_second_colour=False`) | toi |

## Limites honnêtes
- Le code de ce dépôt a été **testé uniquement avec de faux modèles** (30 tests) ; Qwen/FashionCLIP n'ont pas été exécutés ici (pas de GPU) → première exécution Colab à faire.
- Le témoin de couleur par pixels repose sur des règles HSV écrites à la main, non validées.
- Le crop (SegFormer `mattmdjaga/segformer_b2_clothes` + rembg) est un REPLI écrit sans avoir vu le `segment.py` d'Amir : identifiant du modèle et numéros de classes à vérifier à la première exécution (un message s'affiche si les classes diffèrent). Branchement du vrai crop : `DRESSME_CROP_HOOK`.
- Les descriptions des pièces tunisiennes (`taxonomy.TUNISIAN_HINTS`) et le mapping sous-type → slot sont écrits de mémoire : à faire valider.
- Le détecteur multi-articles OWL-ViT reste désactivé : le multi-articles passe par la segmentation (un crop par pièce).
- `labels_template.csv` ne contient qu'**une ligne de format**, pas une annotation réelle.

## Plan (10 jours)
| Jour | Livrable | Critère |
|---|---|---|
| J0–2 | Table de mapping validée par écrit ; contrat v1 reçu d'Amir et comparé au schéma ; mock livré ; tests verts | `pytest -q` passe ; schéma identique |
| J3–4 | Première exécution Colab ; `kb_meta` reconstruit ; embedding commun = script de Suzana | `.npy` de forme (512,), norme 1 ; cosinus ≈ 1 avec le script de Suzana sur 5 crops |
| J5 | Brancher le vrai crop d'Amir ; fiches sur 5 crops réels | fiches valides, statuts cohérents |
| J6–8 | 30 photos réelles étiquetées (2 annotateurs + arbitrage) ; `run_real_eval` | tableau slot / catégorie / couleur + F1 macro + IC |
| J9 | Analyse d'erreurs ; calibration des confiances ; choix `after_rag_policy` **sur le jeu DEV** | table de calibration, ablations |
| J10 | Livraison à l'équipe : JSON + `.npy` + notebook reproductible + mock | démo de bout en bout |

## Utilisation
```bash
pip install -r requirements.txt && pytest -q          # sans GPU
```
Puis `notebooks/obj1_integration.ipynb` (Colab T4). En Python : `RecognitionService.from_config(CFG).recognize("crop.png", item_id="it_0001", out_dir="store")`.
