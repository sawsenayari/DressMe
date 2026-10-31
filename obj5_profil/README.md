# DressMe — Objectif 5 : profil de style (service d'intégration)

Auteur : Ahmed Ayari · Version : `obj5-profile-v1` · Contrat : fiche d'orchestration DressMe (29 oct. 2026)

Ce dossier remplace le notebook Colab pour l'intégration. Il lit des **fiches article v1**
(ItemCard) et renvoie un **profil de style v1** (StyleProfile) au format du contrat, lu par
les objectifs 6, 3 et 4. Tout est déterministe, tourne sur CPU en quelques secondes et ne
demande aucun GPU ni aucune API externe.

## Démarrage rapide (3 commandes)

```bash
pip install -r requirements.txt
python -m pytest -q                                 # 11 tests de conformité
uvicorn dressme_profile.api:app --port 8005         # service HTTP
```

Mode **mock** (réponse valide et constante, sans données ni modèle) :
`DRESSME_PROFILE_MOCK=1 uvicorn dressme_profile.api:app --port 8005`

## Ce que lit et renvoie le module

| Endpoint | Entrée | Sortie |
|---|---|---|
| `GET /health` | — | statut, modèle chargé, taille du catalogue |
| `POST /profile` | `{"user_id": "u1", "item_ids": ["it_0653", ...]}` ou `{"items": [ItemCard, ...]}` | `StyleProfile` |
| `POST /recommend` | `{"wardrobe_ids": [...], "k": 10, "slot": "top"}` (option `candidate_ids`) | profil + articles classés |
| `GET /schema/profile` | — | schéma JSON du profil |

Erreurs : `404` identifiant inconnu du catalogue, `422` requête vide ou garde-robe inexploitable.

### Profil renvoyé (champs du contrat)

```json
{
  "version": "obj5-profile-v1",
  "user_id": "demo_homme",
  "persona": "mixte",                         // efficacite | economie | image | mixte
  "scores": {"efficacite": 0.503, "economie": null, "image": 0.449},
  "palette": [{"colour": "beige", "weight": 0.31}, ...],   // 5 couleurs max, poids qui somment à 1
  "formality_pref": 2.08,                     // 0 à 3
  "price_percentile": null,                   // 0 à 1, null si prix inconnus
  "dominant_cluster": {"id": 1, "name": "onepiece · Ethnic · beige · traditionnel", "share": 0.30},
  "diversity": 0.79,                          // entropie normalisée des clusters, 0 à 1
  "slot_counts": {...}, "n_items": 223, "n_items_used": 195,
  "embedding_space": "attributes",            // ou "fashionclip"
  "model": "obj5-style-model-v1:attributes:k16",
  "warnings": ["..."]
}
```

**Point d'attention pour l'objectif 6 (fonction `adj()`) :** `scores.economie` et
`price_percentile` valent `null` quand moins de 30 % des pièces ont un prix. C'est le cas
de tout le catalogue actuel (`price_dt` vide partout). Je renvoie `null` plutôt qu'une
valeur inventée ; il faut donc tester `is None` avant d'utiliser ces deux champs.

Exemples complets : `examples/profile_homme.json`, `examples/profile_femme.json`,
`examples/recommend_casual.json`. Schémas : `contracts/*.schema.json`.

## Utilisation sans HTTP

```python
from dressme_profile import ProfileService, ProfileRequest
svc = ProfileService()                     # charge data/wardrobe.json et models/
profil = svc.profile(ProfileRequest(user_id="u1", item_ids=["it_0653", "it_0700"]))
print(profil.model_dump())
```

En ligne de commande :

```bash
python -m dressme_profile profile --ids it_0653,it_0700,it_0889 --user u1
python -m dressme_profile profile --gender Women --out profil.json
python -m dressme_profile recommend --ids-file garde_robe.json -k 10 --slot top
python -m dressme_profile train            # réentraîne la taxonomie de styles
python -m dressme_profile export-schemas
```

Variables d'environnement : `DRESSME_CATALOG` (catalogue de fiches), `DRESSME_ASSETS_DIR`
(dossier de base des chemins `emb/*.npy`), `DRESSME_PROFILE_MODEL`, `DRESSME_PROFILE_MOCK`.

## Comment le profil est calculé

1. **Filtrage** : fiches avec `confidence.slot < 0,3` ignorées ; doublons retirés (même
   photo traitée deux fois, par ex. `it_0751` et `it_0796`). Tout est signalé dans `warnings`.
2. **Vecteurs** : FashionCLIP (décision n°1 de l'orchestration) si les `.npy` existent pour
   au moins 90 % du catalogue, sinon repli sur un vecteur d'attributs (emplacement, type,
   couleur, usage, formalité, chaleur, traditionnel, genre, saison). Le service choisit
   l'espace tout seul et réentraîne si l'espace change.
3. **Taxonomie** : PCA (64) + K-Means, k ∈ [6, 16] choisi par silhouette, `n_init = 10`,
   `seed = 42` (hyperparamètres de la fiche obj. 5). Le modèle est appris une fois sur le
   catalogue, puis le profil ne fait qu'assigner les pièces.
4. **Scores de persona** (la plus forte gagne ; écart < 0,08 → « mixte ») :
   - efficacité = 0,5 × part de couleurs neutres + 0,3 × part de basiques + 0,2 × (1 − diversité)
   - économie = 1 − percentile du prix médian dans le catalogue (null si prix inconnus)
   - image = 0,4 × part du cluster dominant + 0,35 × formalité/3 + 0,25 × part de couleurs fortes
5. **Re-ranking** (`/recommend`) : cosinus au centre de la garde-robe, puis bonus de la fiche
   obj. 5 : efficacité (neutre +0,10, basique +0,05), économie (−0,15 × percentile de prix),
   image (cluster dominant +0,10). Persona « mixte » : les deux meilleurs, chacun à moitié.

## Passer à FashionCLIP (étape prévue par l'orchestration)

Dès que les images découpées (`image_crop`) sont disponibles :

```bash
pip install -r requirements-embed.txt
python scripts/compute_fashionclip_embeddings.py --catalog data/wardrobe.json --assets data
python -m dressme_profile train            # le modèle passe en "fashionclip"
```

Si le script commun de Suzana produit déjà les `.npy`, il suffit de pointer
`DRESSME_ASSETS_DIR` vers leur dossier : rien d'autre à changer.

## Limites connues (à citer dans le rapport)

- **Espace actuel = attributs, pas FashionCLIP.** Les `.npy` du catalogue ne sont pas encore
  fournis. Le repli est déterministe et utilisable, mais il ne voit ni la coupe ni la matière.
- **k = 16 est la borne haute** de l'intervalle de la fiche : la silhouette monte encore avec
  k (0,28 à k=6, 0,44 à k=16). La taxonomie est donc fine ; à revoir avec FashionCLIP.
- **Économie non évaluable** tant que `price_dt` reste vide.
- **Catalogue majoritairement traditionnel** (59 % des fiches) et mélangeant homme/femme :
  les profils « par genre » des exemples sont des démonstrations, pas de vrais utilisateurs.
- **Formules de persona** : reprises du principe de la fiche obj. 5 (trois formules simples,
  marge 0,08) ; les coefficients sont à aligner sur le notebook si l'équipe veut une
  équivalence exacte, et à valider sur les garde-robes réelles du jeu de test commun.

## Arborescence

```
dressme_profile/   contracts.py (ItemCard v1, StyleProfile v1), features.py, clustering.py,
                   profile.py, recommend.py, service.py, api.py, cli.py, mock.py, config.py
contracts/         schémas JSON exportés
data/wardrobe.json catalogue de fiches article v1 (423 fiches)
models/            taxonomie entraînée (réentraînée automatiquement si besoin)
scripts/           calcul des embeddings FashionCLIP
examples/          sorties réelles du module
tests/             11 tests pytest (contrat, déterminisme, API, mock, FashionCLIP)
```
