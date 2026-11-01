# Passerelle DressMe (provisoire, avant l'objectif 6)
Un seul backend (port 8000) pour le front. Lancement depuis la racine du dépôt : `run_all.bat`
(ou `python -m uvicorn app:app --app-dir gateway --port 8000`), puis http://127.0.0.1:8000/docs.

| Route du front | Source | État |
|---|---|---|
| GET /wardrobe/items | catalogue de fiches (Obj5 `data/wardrobe.json`) | lecture seule |
| POST /wardrobe/items | Obj1 | 501 (non branché) |
| POST /compatibility/score | photo -> FashionCLIP -> Obj2 | OK si catalogue avec embeddings + modèle téléchargé |
| GET /gaps | Obj4 `gap_report.json` (liste ou contrat v1 `{gaps: [...]}`) | rapport statique (repli) ; slots Polyvore ramenés aux slots du front |
| GET/PUT /profile | Obj5 | OK (espace « attributs » tant que les embeddings manquent) |
| GET /outfits/today | Obj6 | 501 (non branché) |

Limites : `newOutfits` vaut 0 (à fournir par l'Obj4) ; la garde-robe est plafonnée à 40 articles (MAX_WARDROBE) car le
temps de calcul croît avec son carré (~3 s à 40 articles sur CPU) ; le premier appel de /compatibility/score télécharge FashionCLIP (~600 Mo).
Test : `python -m pytest -q gateway/tests` (catalogue synthétique, FashionCLIP remplacé ; le modèle Obj5 est réentraîné dans un dossier temporaire, pas dans `obj5_profil/models`). Lancer chaque dossier de tests séparément (ils s'appellent tous `tests`).
